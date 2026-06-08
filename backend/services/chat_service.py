"""Professional AI Chat Service for natural language procurement analysis."""

from __future__ import annotations
import json
import asyncio
from decimal import Decimal
from typing import Any, List, Dict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from groq import AsyncGroq
from core.logger import get_logger
from backend.core.config import settings

logger = get_logger("services.chat")

class AuditChatService:
    """Service to handle natural language queries over the procurement database using Groq."""

    SCHEMA_CONTEXT = """
    Tabelas disponíveis para consulta:
    
    1. 'users': Dados de usuários do sistema.
    2. 'departments': Unidades (id, name). Valores comuns: 'Institucional'.
    3. 'fornecedores': Empresas vendedoras (id, cnpj, razao_social). Ex: 'ATACADAO DIA A DIA S.A'.
    4. 'produtos': Catálogo (ean, nome_limpo, marca, categoria). Categorias: 'LIMPEZA', 'ALIMENTOS BÁSICOS', 'BEBIDAS', etc.
    5. 'notas_fiscais': Documentos (id, fornecedor_id, department_id, valor_total, data_emissao).
    6. 'itens_notas_fiscais': Detalhes (nota_fiscal_id, ean, valor_unitario, valor_total, quantidade).
    7. 'historico_precos': Histórico de preços por EAN.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        # Use a chave do Groq que já validamos como funcional
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model_name = "llama-3.3-70b-versatile"

    async def chat(self, message: str, department_id: Any | None = None) -> Dict[str, Any]:
        """Processes a natural language message and returns an AI-powered answer or performs an action."""
        logger.info(f"Chat request via Groq: '{message}' (Dept: {department_id})")

        # 1. Identificar Intenção (Pergunta vs Ação de Correção)
        intent = await self._identify_intent(message)
        
        if intent.get("action") == "UPDATE_CATEGORY":
            return await self._handle_category_correction(intent, message, department_id)

        # 2. Se for uma pergunta, segue o fluxo normal de SQL
        sql_query = await self._generate_sql(message, department_id)
        logger.debug(f"Generated SQL: {sql_query}")

        # 2. Execute SQL (ReadOnly)
        try:
            result = await self.db.execute(text(sql_query))
            # Converte Decimal para float para serialização JSON
            data = []
            for row in result.fetchall():
                row_dict = dict(row._mapping)
                for k, v in row_dict.items():
                    if isinstance(v, Decimal):
                        row_dict[k] = float(v)
                data.append(row_dict)
        except Exception as e:
            logger.error(f"SQL Execution failed: {e}")
            return {
                "answer": "Desculpe, tive um problema técnico ao consultar os dados. Pode tentar reformular a pergunta?",
                "error": str(e),
                "query_used": sql_query
            }

        # 3. Explain result
        answer = await self._explain_data(message, data)
        
        return {
            "answer": answer,
            "query_used": sql_query,
            "data_summary": data[:5]
        }

    async def _generate_sql(self, prompt: str, department_id: Any | None) -> str:
        tenant_constraint = f"Filtre os dados SEMPRE pelo department_id = '{department_id}' se a tabela possuir essa coluna." if department_id else ""
        
        system_prompt = f"""
        Você é um Especialista em Banco de Dados PostgreSQL da Auditoria Governamental.
        Seu objetivo é traduzir a pergunta do usuário para uma ÚNICA query SQL SELECT válida.

        {self.SCHEMA_CONTEXT}

        REGRAS CRÍTICAS:
        1. Use APENAS SELECT. Nunca use comandos de modificação.
        2. {tenant_constraint}
        3. Retorne EXCLUSIVAMENTE o código SQL, sem markdown, sem explicações.
        4. Sempre limite a 50 resultados para performance.
        """
        
        chat_completion = await self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            model=self.model_name,
            temperature=0.1,
        )
        
        sql = chat_completion.choices[0].message.content.replace("```sql", "").replace("```", "").strip()
        return sql

    async def _explain_data(self, question: str, data: List[Dict]) -> str:
        if not data:
            return "Não encontrei nenhum registro que corresponda à sua pergunta no banco de dados."

        system_prompt = """
        Você é um Auditor Sênior amigável e especialista em análise de compras governamentais.
        Sua tarefa é explicar os resultados de uma consulta ao banco de dados de forma clara e profissional.
        Seja conciso e use português do Brasil.
        """
        
        user_prompt = f"""
        A pergunta feita foi: "{question}"
        
        Os dados encontrados no banco foram:
        {json.dumps(data[:20], ensure_ascii=False, indent=2)}

        Explique o que esses dados significam em relação à pergunta.
        """
        
        chat_completion = await self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model_name,
            temperature=0.5,
        )
        return chat_completion.choices[0].message.content.strip()

    async def _identify_intent(self, message: str) -> Dict[str, Any]:
        """Identifica se o usuário quer apenas perguntar (SELECT) ou corrigir algo (UPDATE)."""
        prompt = f"""
        Analise a mensagem do usuário e identifique a intenção.
        MENSAGEM: "{message}"

        OPÇÕES DE INTENÇÃO:
        1. QUERY: Pergunta geral sobre dados.
        2. UPDATE_CATEGORY: O usuário quer mudar a categoria de um produto.
           Campos extraídos: {{"ean": "...", "nova_categoria": "..."}}

        Retorne APENAS um JSON no formato: {{"action": "QUERY" | "UPDATE_CATEGORY", "ean": "...", "nova_categoria": "..."}}
        """
        
        chat_completion = await self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Responda apenas JSON válido."},
                {"role": "user", "content": prompt},
            ],
            model=self.model_name,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        return json.loads(chat_completion.choices[0].message.content)

    async def _handle_category_correction(self, intent: Dict[str, Any], original_message: str, department_id: Any | None = None) -> Dict[str, Any]:
        """Executa a atualização da categoria no banco e no cache."""
        from backend.core.classification_cache import upsert_classification_cache_entry
        from backend.models.compras import Produto, ItemNotaFiscal, NotaFiscal
        from sqlalchemy import update, select
        from core.classificador_regras import _normalizar

        ean = intent.get("ean")
        nova_cat = intent.get("nova_categoria")

        if not ean or not nova_cat:
            return {
                "answer": "Não consegui identificar qual produto ou qual a nova categoria. Pode repetir especificando o código (EAN) e a categoria?",
                "intent_detected": intent
            }

        try:
            # 1. Atualiza Produto
            stmt_prod = update(Produto).where(Produto.ean == ean).values(categoria=nova_cat)
            await self.db.execute(stmt_prod)

            # 2. Atualiza Cache de todas as descrições que levam a este EAN
            stmt_items = (
                select(ItemNotaFiscal.descricao_original)
                .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
                .where(ItemNotaFiscal.ean == ean)
                .distinct()
            )
            if department_id is not None:
                stmt_items = stmt_items.where(NotaFiscal.department_id == department_id)
            res_items = await self.db.execute(stmt_items)
            descricoes = res_items.scalars().all()

            stmt_p = select(Produto.nome_limpo).where(Produto.ean == ean)
            p_res = await self.db.execute(stmt_p)
            p_nome = p_res.scalar()

            for desc in descricoes:
                desc_norm = _normalizar(desc)
                # Sincroniza cache com flag de verificado
                await upsert_classification_cache_entry(
                    self.db,
                    department_id=department_id,
                    descricao_original=desc_norm,
                    categoria=nova_cat,
                    verificado_usuario=True,
                    produto_canonico=p_nome or desc_norm,
                )

            await self.db.commit()
            
            return {
                "answer": f"✅ Entendido! Atualizei a categoria do produto (EAN: {ean}) para **{nova_cat}**. Agora eu já aprendi e as próximas importações deste item serão classificadas corretamente.",
                "action_performed": "UPDATE_CATEGORY",
                "ean": ean,
                "category": nova_cat
            }
        except Exception as e:
            logger.error(f"Erro ao processar correção via Chat: {e}")
            return {
                "answer": "Houve um erro técnico ao tentar atualizar a categoria. Por favor, tente novamente mais tarde.",
                "error": str(e)
            }

"""Professional AI Chat Service for natural language procurement analysis."""

from __future__ import annotations
import json
from typing import Any, List, Dict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import google.generativeai as genai
from core.logger import get_logger
from backend.core.config import settings

logger = get_logger("services.chat")

class AuditChatService:
    """Service to handle natural language queries over the procurement database."""

    SCHEMA_CONTEXT = """
    Tabelas disponíveis para consulta:
    
    1. 'users': Dados de usuários do sistema.
    2. 'departments': Instituições/unidades (id, name).
    3. 'produtos': Catálogo de produtos (ean, nome_limpo, marca, categoria).
    4. 'notas_fiscais': Documentos fiscais (id, department_id, numero_nota, chave_acesso, data_emissao, valor_total).
    5. 'itens_notas_fiscais': Detalhes dos itens das notas (nota_fiscal_id, ean, descricao_original, quantidade, valor_unitario, valor_total).
    6. 'historico_precos': Registro histórico de preços para análise de volatilidade.
    7. 'audit_logs': Trilha de auditoria das operações.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def chat(self, message: str, department_id: Any | None = None) -> Dict[str, Any]:
        """Processes a natural language message and returns an AI-powered answer."""
        logger.info(f"Chat request: '{message}' (Dept: {department_id})")

        # 1. Generate SQL
        sql_query = await self._generate_sql(message, department_id)
        logger.debug(f"Generated SQL: {sql_query}")

        # 2. Execute SQL (ReadOnly)
        try:
            result = await self.db.execute(text(sql_query))
            data = [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"SQL Execution failed: {e}")
            return {
                "answer": "Desculpe, tive um problema técnico ao consultar os dados. Pode tentar reformular a pergunta?",
                "error": str(e)
            }

        # 3. Explain result
        answer = await self._explain_data(message, data)
        
        return {
            "answer": answer,
            "query_used": sql_query,
            "data_summary": data[:5] # Retorna uma amostra dos dados
        }

    async def _generate_sql(self, prompt: str, department_id: Any | None) -> str:
        tenant_constraint = f"Filtre os dados SEMPRE pelo department_id = '{department_id}' se a tabela possuir essa coluna." if department_id else ""
        
        full_prompt = f"""
        Você é um Especialista em Banco de Dados PostgreSQL da Auditoria Governamental.
        Seu objetivo é traduzir a pergunta do usuário para uma ÚNICA query SQL SELECT válida.

        {self.SCHEMA_CONTEXT}

        REGRAS CRÍTICAS:
        1. Use APENAS SELECT. Nunca use comandos de modificação.
        2. {tenant_constraint}
        3. Retorne EXCLUSIVAMENTE o código SQL, sem markdown, sem explicações.
        4. Sempre limite a 50 resultados para performance.

        PERGUNTA: {prompt}
        """
        
        response = await asyncio.to_thread(self.model.generate_content, full_prompt)
        # Limpa possível markdown do Gemini
        sql = response.text.replace("```sql", "").replace("```", "").strip()
        return sql

    async def _explain_data(self, question: str, data: List[Dict]) -> str:
        if not data:
            return "Não encontrei nenhum registro que corresponda à sua pergunta."

        prompt = f"""
        Você é um Auditor Sênior amigável.
        A pergunta feita foi: "{question}"
        
        Os dados encontrados no banco foram:
        {json.dumps(data[:20], ensure_ascii=False, indent=2)}

        Explique o que esses dados significam em relação à pergunta. 
        Seja conciso, profissional e use português do Brasil.
        """
        
        response = await asyncio.to_thread(self.model.generate_content, prompt)
        return response.text.strip()

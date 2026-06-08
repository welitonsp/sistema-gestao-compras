# ia_groq_utils.py
# ==========================================================
# FACHADA DE IA + INFRA — GROQ / LLAMA
# ==========================================================

import json
from datetime import datetime

from groq import Groq, AsyncGroq
from sqlalchemy import select

from backend.core.classification_cache import (
    get_classification_cache_entry,
    upsert_classification_cache_entry,
)
from backend.core.database import SessionLocal
from backend.models.compras import Produto, HistoricoPreco, ClassificacaoCache
from core.classificador_regras import aplicar_regras_nome_categoria, _normalizar
from core.logger import get_logger
from backend.core.config import settings

logger = get_logger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"


class GroqNotConfiguredError(RuntimeError):
    """Raised when a Groq call is attempted without runtime credentials."""


_groq_client: Groq | None = None
_async_groq_client: AsyncGroq | None = None
_groq_client_api_key: str | None = None
_async_groq_client_api_key: str | None = None


def _get_groq_api_key() -> str:
    api_key = settings.groq_api_key
    if hasattr(api_key, "get_secret_value"):
        api_key = api_key.get_secret_value()
    api_key = str(api_key).strip() if api_key else ""
    if not api_key:
        raise GroqNotConfiguredError("GROQ_API_KEY not configured")
    return api_key


def get_groq_client() -> Groq:
    """Return a lazily initialized Groq client."""

    global _groq_client, _groq_client_api_key
    api_key = _get_groq_api_key()
    if _groq_client is None or _groq_client_api_key != api_key:
        _groq_client = Groq(api_key=api_key)
        _groq_client_api_key = api_key
    return _groq_client


def get_async_groq_client() -> AsyncGroq:
    """Return a lazily initialized async Groq client."""

    global _async_groq_client, _async_groq_client_api_key
    api_key = _get_groq_api_key()
    if _async_groq_client is None or _async_groq_client_api_key != api_key:
        _async_groq_client = AsyncGroq(api_key=api_key)
        _async_groq_client_api_key = api_key
    return _async_groq_client

# ==========================================
# 2. BANCO DE DADOS (UNIFICADO COM ORM)
# ==========================================

async def buscar_no_cache(descricao: str, department_id=None) -> dict | None:
    """Busca uma classificação prévia no cache do banco."""
    async with SessionLocal() as session:
        desc_norm = _normalizar(descricao)
        cached = await get_classification_cache_entry(
            session,
            descricao_original=desc_norm,
            department_id=department_id,
        )
        
        if cached:
            logger.info(f"Cache hit para: {desc_norm}")
            return {
                "produto": cached.produto_canonico,
                "marca": cached.marca,
                "categoria": cached.categoria,
                "unidade": cached.unidade
            }
    return None

async def obter_exemplos_verificados(limit: int = 10, department_id=None) -> str:
    """Busca as classificações verificadas por humanos para injetar no prompt."""
    async with SessionLocal() as db:
        from backend.core.classification_cache import (
            classification_cache_scope_filter,
            classification_cache_scope_order,
        )

        stmt = (
            select(ClassificacaoCache)
            .where(
                ClassificacaoCache.verificado_usuario == True,
                classification_cache_scope_filter(department_id),
            )
            .order_by(*classification_cache_scope_order(department_id))
            .limit(limit)
        )
        res = await db.execute(stmt)
        exemplos = res.scalars().all()
        
        if not exemplos:
            return ""
            
        texto = "\nEXEMPLOS DE CLASSIFICAÇÕES CORRETAS (CONFIRMADAS POR HUMANO):\n"
        for ex in exemplos:
            texto += f"- \"{ex.descricao_original}\" -> PRODUTO: {ex.produto_canonico}, CATEGORIA: {ex.categoria}\n"
        return texto

async def salvar_no_cache(descricao_original: str, dados: dict, department_id=None):
    """Salva o resultado da IA no cache."""
    async with SessionLocal() as session:
        desc_norm = _normalizar(descricao_original)
        await upsert_classification_cache_entry(
            session,
            department_id=department_id,
            descricao_original=desc_norm,
            produto_canonico=dados["produto"],
            marca=dados.get("marca"),
            categoria=dados["categoria"],
            unidade=dados.get("unidade", "un"),
        )
        await session.commit()

async def produto_ja_existe(id_produto: str) -> bool:
    async with SessionLocal() as session:
        stmt = select(Produto.ean).where(Produto.ean == id_produto)
        result = await session.execute(stmt)
        return result.fetchone() is not None

async def salvar_produto(id_produto, original, limpo, marca, categoria, unidade):
    """Salva um produto no catálogo canônico usando o ORM."""
    async with SessionLocal() as session:
        # Nota: O campo 'original' agora é guardado na instância da compra (ItemNotaFiscal)
        # No catálogo canônico (Produto), guardamos apenas os dados limpos.
        produto = Produto(
            ean=id_produto,
            nome_limpo=limpo,
            marca=marca,
            categoria=categoria,
            unidade=unidade
        )
        await session.merge(produto) # Merge faz o papel do 'ON CONFLICT DO UPDATE/NOTHING'
        await session.commit()

async def salvar_compra(id_produto, data, mercado, preco, qtd):
    """Salva um registro no histórico de preços usando o ORM."""
    async with SessionLocal() as session:
        if isinstance(data, str):
            data_dt = datetime.strptime(data, "%Y-%m-%d").date()
        else:
            data_dt = data
            
        historico = HistoricoPreco(
            ean=id_produto,
            data_compra=data_dt,
            local=mercado,
            preco_pago=preco,
            quantidade=qtd
        )
        session.add(historico)
        await session.commit()

# ==========================================
# 3. IA — FUNÇÕES (MANTIDAS)
# ==========================================

async def consultar_ia_async(nome_sujo: str, department_id=None) -> dict:
    # 1. Tentar Cache
    cached = await buscar_no_cache(nome_sujo, department_id=department_id)
    if cached:
        return cached

    # 2. Se não houver cache, chamar IA
    prompt = (
        "Você é um especialista em classificação de produtos de supermercado brasileiro.\n"
        f"DESCRIÇÃO ORIGINAL: \"{nome_sujo}\"\n\n"
        "Sua tarefa é extrair:\n"
        "1. PRODUTO: Nome simplificado e genérico (ex: ARROZ, LEITE INTEGRAL).\n"
        "2. MARCA: Nome CANÔNICO da marca. Unifique variações (ex: 'Coca-Cola', 'Coca Cola' e 'Coke' devem ser 'COCA-COLA'). Se não houver marca clara, retorne vazio.\n"
        "3. CATEGORIA: Use estritamente as categorias do padrão IBGE/POF (ex: ALIMENTAÇÃO - GRÃOS, LIMPEZA - LAVANDERIA, etc).\n"
        "4. UNIDADE: A unidade de medida (un, kg, g, l, ml, pct).\n\n"
        "Retorne APENAS um JSON válido."
    )
    try:
        async_groq_client = get_async_groq_client()
        resposta = await async_groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Responda apenas JSON válido."},
                {"role": "user", "content": prompt},
            ],
            model=GROQ_MODEL,
            temperature=0.2,
            max_tokens=250,
            response_format={"type": "json_object"},
        )
        dados = json.loads(resposta.choices[0].message.content)
        produto_final, categoria_final = aplicar_regras_nome_categoria(
            nome_original=nome_sujo,
            nome_ia=dados.get("produto", nome_sujo),
            categoria_ia=dados.get("categoria", "Outros"),
        )
        resultado = {
            "produto": produto_final,
            "marca": dados.get("marca", ""),
            "categoria": categoria_final,
            "unidade": dados.get("unidade", "un"),
        }
        
        # 3. Salvar no Cache
        await salvar_no_cache(nome_sujo, resultado, department_id=department_id)
        
        return resultado
    except GroqNotConfiguredError:
        raise
    except Exception as e:
        logger.error(f"Erro na IA (async): {type(e).__name__}")
        return {"produto": nome_sujo, "marca": "", "categoria": "Outros", "unidade": "un"}

async def extrair_json_com_groq_async(
    *, conteudo: str, prompt_sistema: str, model: str | None = None,
    max_tokens: int = 6000, temperature: float = 0.1,
) -> dict:
    try:
        async_groq_client = get_async_groq_client()
        resposta = await async_groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": conteudo},
            ],
            model=model or GROQ_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return json.loads(resposta.choices[0].message.content)
    except GroqNotConfiguredError:
        raise
    except Exception as e:
        logger.error(f"Erro ao extrair JSON assincronamente com Groq: {type(e).__name__}")
        raise

# ==========================================
# 4. COMPATIBILIDADE E INFRA
# ==========================================

async def classificar_produto_async(descricao: str, contexto: dict | None = None) -> dict:
    department_id = (contexto or {}).get("department_id")
    return await consultar_ia_async(descricao, department_id=department_id)

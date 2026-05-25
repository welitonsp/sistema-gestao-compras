# ia_groq_utils.py
# ==========================================================
# FACHADA DE IA + INFRA — GROQ / LLAMA
# ==========================================================

import json
import os
import asyncio
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq, AsyncGroq
from sqlalchemy import select, text

from backend.core.database import SessionLocal
from backend.models.compras import Produto, HistoricoPreco, ClassificacaoCache
from core.classificador_regras import aplicar_regras_nome_categoria, _normalizar
from core.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY não encontrada no .env")

groq_client = Groq(api_key=GROQ_API_KEY)
async_groq_client = AsyncGroq(api_key=GROQ_API_KEY)

# ==========================================
# 2. BANCO DE DADOS (UNIFICADO COM ORM)
# ==========================================

async def buscar_no_cache(descricao: str) -> dict | None:
    """Busca uma classificação prévia no cache do banco."""
    async with SessionLocal() as session:
        desc_norm = _normalizar(descricao)
        stmt = select(ClassificacaoCache).where(ClassificacaoCache.descricao_original == desc_norm)
        result = await session.execute(stmt)
        cached = result.scalar_one_or_none()
        
        if cached:
            logger.info(f"Cache hit para: {desc_norm}")
            return {
                "produto": cached.produto_canonico,
                "marca": cached.marca,
                "categoria": cached.categoria,
                "unidade": cached.unidade
            }
    return None

async def salvar_no_cache(descricao_original: str, dados: dict):
    """Salva o resultado da IA no cache."""
    async with SessionLocal() as session:
        desc_norm = _normalizar(descricao_original)
        cache_entry = ClassificacaoCache(
            descricao_original=desc_norm,
            produto_canonico=dados["produto"],
            marca=dados.get("marca"),
            categoria=dados["categoria"],
            unidade=dados.get("unidade", "un")
        )
        await session.merge(cache_entry)
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

async def consultar_ia_async(nome_sujo: str) -> dict:
    # 1. Tentar Cache
    cached = await buscar_no_cache(nome_sujo)
    if cached:
        return cached

    # 2. Se não houver cache, chamar IA
    prompt = (
        "Você é um especialista em classificação de produtos de supermercado brasileiro.\n"
        f"DESCRIÇÃO ORIGINAL: \"{nome_sujo}\"\n\n"
        "Sua tarefa é extrair:\n"
        "1. PRODUTO: Nome simplificado e genérico (ex: ARROZ, LEITE INTEGRAL).\n"
        "2. MARCA: Nome CANÔNICO da marca. Unifique variações (ex: 'Coca-Cola', 'Coca Cola' e 'Coke' devem ser 'COCA-COLA'). Se não houver marca clara, retorne vazio.\n"
        "3. CATEGORIA: Escolha entre [ALIMENTOS BÁSICOS, LATICÍNIOS, CARNES, HORTIFRUTI, BEBIDAS, LIMPEZA, HIGIENE PESSOAL, LANCHE, OUTROS].\n"
        "4. UNIDADE: A unidade de medida (un, kg, g, l, ml, pct).\n\n"
        "Retorne APENAS um JSON válido."
    )
    try:
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
        await salvar_no_cache(nome_sujo, resultado)
        
        return resultado
    except Exception as e:
        logger.error(f"Erro na IA (async): {e}")
        return {"produto": nome_sujo, "marca": "", "categoria": "Outros", "unidade": "un"}

async def extrair_json_com_groq_async(
    *, conteudo: str, prompt_sistema: str, model: str | None = None,
    max_tokens: int = 2000, temperature: float = 0.1,
) -> dict:
    try:
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
    except Exception as e:
        logger.error(f"Erro ao extrair JSON assincronamente com Groq: {e}")
        raise

# ==========================================
# 4. COMPATIBILIDADE E INFRA
# ==========================================

async def classificar_produto_async(descricao: str, contexto: dict | None = None) -> dict:
    return await consultar_ia_async(descricao)




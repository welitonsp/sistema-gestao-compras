# sistema_completo.py
# Versão 2.0 - Processador de XML NFC-e com logging, validação e cache de IA

import os
import glob
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any

import psycopg2
import google.generativeai as genai

from config import get_settings
from logger_config import setup_logger


logger = setup_logger("xml_processor", "xml_processor.log")


# ------------------------ Funções de Infraestrutura ------------------------ #

def conectar_banco(database_url: str) -> psycopg2.extensions.connection:
    """
    Abre conexão com o PostgreSQL (Neon, no seu caso).
    """
    logger.info("Conectando ao banco de dados...")
    conn = psycopg2.connect(database_url)
    conn.autocommit = False  # controle manual de commit
    logger.info("Conexão com o banco estabelecida com sucesso.")
    return conn


def garantir_tabelas(conn: psycopg2.extensions.connection) -> None:
    """
    Cria as tabelas 'produtos' e 'historico_precos' se ainda não existirem.
    """
    logger.info("Garantindo existência das tabelas no banco...")
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS produtos (
                ean TEXT PRIMARY KEY,
                nome_original TEXT NOT NULL,
                nome_limpo   TEXT,
                marca        TEXT,
                categoria    TEXT,
                unidade      TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS historico_precos (
                id SERIAL PRIMARY KEY,
                ean         TEXT NOT NULL REFERENCES produtos(ean),
                data_compra DATE NOT NULL,
                mercado     TEXT NOT NULL,
                preco_pago  NUMERIC(10, 2) NOT NULL,
                quantidade  NUMERIC(10, 3) NOT NULL
            );
            """
        )
    conn.commit()
    logger.info("Tabelas checadas/criadas com sucesso.")


def configurar_modelo_gemini(api_key: str) -> genai.GenerativeModel:
    """
    Configura o cliente do Google Gemini e devolve o modelo.
    """
    logger.info("Configurando modelo Gemini...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    logger.info("Modelo Gemini configurado.")
    return model


# ------------------------ Utilidades de Dados ------------------------ #

def remover_namespaces(tree: ET.ElementTree) -> ET.ElementTree:
    """
    Remove namespaces dos elementos XML para simplificar os XPath.
    """
    for elem in tree.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]
    return tree


def parse_data_emissao(dh_emissao: str) -> Optional[datetime.date]:
    """
    Converte a string da data de emissão em um objeto date.
    Aceita formatos do tipo:
        2024-03-15T10:00:00-03:00
        2024-03-15
    """
    if not dh_emissao:
        return None

    dh_emissao = dh_emissao.strip()

    # Tenta truncar timezone se existir
    if "T" in dh_emissao and "+" in dh_emissao:
        # Ex: 2024-03-15T10:00:00-03:00 -> 2024-03-15T10:00:00
        dh_emissao = dh_emissao.split("+", 1)[0]

    formatos = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formatos:
        try:
            dt = datetime.strptime(dh_emissao, fmt)
            return dt.date()
        except ValueError:
            continue

    logger.warning("Não foi possível converter data de emissão '%s'.", dh_emissao)
    return None


def gerar_ean_generico(nome_produto: str) -> str:
    """
    Gera um EAN genérico e estável baseado no nome do produto.
    """
    base = abs(hash(nome_produto or "SEM_NOME")) % 1_000_000_000
    return f"GEN_{base:09d}"


# ------------------------ Acesso a Produtos / IA ------------------------ #

def buscar_produto_por_ean(
    conn: psycopg2.extensions.connection, ean: str
) -> Optional[Dict[str, Any]]:
    """
    Procura um produto pelo EAN na tabela 'produtos'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT nome_limpo, marca, categoria, unidade
            FROM produtos
            WHERE ean = %s
            """,
            (ean,),
        )
        row = cur.fetchone()

    if row:
        return {
            "nome_limpo": row[0],
            "marca": row[1],
            "categoria": row[2],
            "unidade": row[3],
        }
    return None


def salvar_produto(
    conn: psycopg2.extensions.connection,
    ean: str,
    nome_original: str,
    info: Dict[str, str],
) -> None:
    """
    Cria ou atualiza um produto na tabela 'produtos'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO produtos (ean, nome_original, nome_limpo, marca, categoria, unidade)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ean) DO UPDATE
            SET nome_original = EXCLUDED.nome_original,
                nome_limpo   = EXCLUDED.nome_limpo,
                marca        = EXCLUDED.marca,
                categoria    = EXCLUDED.categoria,
                unidade      = EXCLUDED.unidade;
            """,
            (
                ean,
                nome_original,
                info.get("nome_limpo") or nome_original,
                info.get("marca") or "",
                info.get("categoria") or "Outros",
                info.get("unidade") or "",
            ),
        )
    conn.commit()


def salvar_historico_preco(
    conn: psycopg2.extensions.connection,
    ean: str,
    data_compra: datetime.date,
    mercado: str,
    preco_pago: Decimal,
    quantidade: Decimal,
) -> None:
    """
    Insere um registro na tabela 'historico_precos'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO historico_precos (ean, data_compra, mercado, preco_pago, quantidade)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (ean, data_compra, mercado, preco_pago, quantidade),
        )
    conn.commit()


def enriquecer_produto_com_ia(
    model: genai.GenerativeModel,
    nome_original: str,
) -> Dict[str, str]:
    """
    Usa o Gemini para padronizar o nome do produto, inferir marca, categoria e unidade.
    Retorna um dicionário com as chaves:
      - nome_limpo
      - marca
      - categoria
      - unidade
    Em caso de erro, retorna um fallback.
    """
    prompt = f"""
Você é um sistema que padroniza nomes de produtos de supermercado.

Entrada: um nome de produto exatamente como aparece no cupom fiscal (abreviado, bagunçado).

Saída: um JSON COMPACTO, SEM textos extras, no formato:
{{
  "produto": "NOME_PADRONIZADO",
  "marca": "MARCA_SE_HOUVER",
  "categoria": "Ex: Alimentos, Limpeza, Higiene, Bebidas, Açougue, Hortifruti, Padaria, Outros",
  "unidade": "Ex: un, kg, L, ml, pacote, caixa, bandeja"
}}

IMPORTANTE:
- Responda APENAS o JSON.
- Se não souber algum campo, deixe como string vazia ("") ou categoria "Outros".

Nome do produto:
"{nome_original}"
    """.strip()

    try:
        resposta = model.generate_content(prompt)
        texto = resposta.text.strip()

        # Tenta isolar o JSON
        inicio = texto.find("{")
        fim = texto.rfind("}")
        if inicio != -1 and fim != -1:
            json_bruto = texto[inicio : fim + 1]
        else:
            json_bruto = texto

        dados = json.loads(json_bruto)

        nome_limpo = dados.get("produto") or nome_original
        marca = dados.get("marca") or ""
        categoria = dados.get("categoria") or "Outros"
        unidade = dados.get("unidade") or ""

        return {
            "nome_limpo": nome_limpo,
            "marca": marca,
            "categoria": categoria,
            "unidade": unidade,
        }

    except Exception as e:
        logger.warning(
            "Falha ao chamar IA para o produto '%s': %s. Usando fallback.",
            nome_original,
            e,
        )
        return {
            "nome_limpo": nome_original,
            "marca": "",
            "categoria": "Outros",
            "unidade": "",
        }


# ------------------------ Processamento de Arquivo XML ------------------------ #

def processar_xml(
    caminho_arquivo: str,
    conn: psycopg2.extensions.connection,
    model: genai.GenerativeModel,
    cache_ia: Dict[str, Dict[str, str]],
) -> int:
    """
    Processa um arquivo XML de NFC-e, insere/atualiza produtos e histórico no banco.
    Retorna a quantidade de itens válidos processados.
    """
    logger.info("Processando arquivo XML: %s", caminho_arquivo)

    try:
        tree = ET.parse(caminho_arquivo)
    except Exception as e:
        logger.error("Erro ao abrir/parsing do XML '%s': %s", caminho_arquivo, e)
        return 0

    root = remover_namespaces(tree).getroot()

    dh_emissao = root.findtext(".//ide/dhEmi") or ""
    data_compra = parse_data_emissao(dh_emissao)
    if not data_compra:
        logger.warning(
            "Data de emissão não encontrada/ inválida em '%s'. Arquivo ignorado.",
            caminho_arquivo,
        )
        return 0

    mercado = (root.findtext(".//emit/xNome") or "").strip()
    if not mercado:
        mercado = "MERCADO DESCONHECIDO"

    itens_processados = 0

    for det in root.findall(".//det"):
        prod = det.find("prod")
        if prod is None:
            continue

        ean = (prod.findtext("cEAN") or "").strip()
        nome_original = (prod.findtext("xProd") or "").strip()

        # Quantidade e valor unitário
        q_com_str = (prod.findtext("qCom") or "1").replace(",", ".")
        v_un_str = (prod.findtext("vUnCom") or "0").replace(",", ".")

        try:
            quantidade = Decimal(q_com_str)
            preco_unitario = Decimal(v_un_str)
        except InvalidOperation:
            logger.warning(
                "Valores inválidos (qCom=%s, vUnCom=%s) no produto '%s' do arquivo '%s'.",
                q_com_str,
                v_un_str,
                nome_original,
                caminho_arquivo,
            )
            continue

        if quantidade <= 0 or preco_unitario <= 0:
            logger.warning(
                "Quantidade ou preço não positivos (qCom=%s, vUnCom=%s) no produto '%s'. Ignorando.",
                q_com_str,
                v_un_str,
                nome_original,
            )
            continue

        if not ean or ean.upper() in ("SEM GTIN", "SEM_GTIN"):
            ean = gerar_ean_generico(nome_original)

        # Tenta buscar produto no banco
        info_produto = buscar_produto_por_ean(conn, ean)

        # Se não achou, tenta cache de IA por nome_original
        if not info_produto:
            if nome_original in cache_ia:
                info_produto = cache_ia[nome_original]
            else:
                info_produto = enriquecer_produto_com_ia(model, nome_original)
                cache_ia[nome_original] = info_produto

            salvar_produto(conn, ean, nome_original, info_produto)

        # Salva histórico
        salvar_historico_preco(
            conn=conn,
            ean=ean,
            data_compra=data_compra,
            mercado=mercado,
            preco_pago=preco_unitario,
            quantidade=quantidade,
        )

        itens_processados += 1

    logger.info(
        "Arquivo '%s' processado com sucesso. Itens válidos: %d.",
        caminho_arquivo,
        itens_processados,
    )
    return itens_processados


# ------------------------ Função Principal ------------------------ #

def main() -> None:
    logger.info("Iniciando processamento de XML NFC-e na pasta atual...")

    settings = get_settings()

    # Conecta no banco e garante schema
    conn = conectar_banco(settings.database_url)
    garantir_tabelas(conn)

    # Configura o modelo IA
    model = configurar_modelo_gemini(settings.gemini_api_key)

    # Cache em memória para reduzir chamadas repetidas à IA pelo mesmo nome_original
    cache_ia: Dict[str, Dict[str, str]] = {}

    # Procura todos arquivos .xml na pasta atual
    xml_files = sorted(
        f for f in os.listdir(".") if f.lower().endswith(".xml")
    )

    if not xml_files:
        logger.info("Nenhum arquivo XML encontrado na pasta atual.")
        return

    logger.info("Foram encontrados %d arquivo(s) XML.", len(xml_files))

    total_itens = 0
    for nome_arquivo in xml_files:
        caminho = os.path.join(".", nome_arquivo)
        itens = processar_xml(caminho, conn, model, cache_ia)
        total_itens += itens

    logger.info("Processamento concluído. Total de itens gravados: %d", total_itens)


if __name__ == "__main__":
    main()

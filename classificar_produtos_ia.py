# classificar_produtos_ia.py
# Classificação de produtos usando IA (Groq / Llama 3.2)
#
# Fluxo:
#   - Lê a conexão do banco de dados a partir do .env (DATABASE_URL)
#   - Lê a chave da API Groq a partir do .env (GROQ_API_KEY)
#   - Ajusta a tabela 'produtos' para garantir colunas de classificação
#   - Busca produtos pendentes de classificação
#   - Usa o modelo Llama 3.2 via Groq para padronizar nome, marca, categoria e unidade
#   - Atualiza a tabela 'produtos' com as informações limpas
#
# Requisitos:
#   pip install psycopg2-binary pandas python-dotenv groq

import os
import json
import logging
from typing import Dict, Any, List, Tuple, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from groq import Groq

# ---------------------------------------------------------------------
# CONFIGURAÇÃO INICIAL
# ---------------------------------------------------------------------

# Carrega variáveis do arquivo .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("classificador_ia")

if not DATABASE_URL:
    raise RuntimeError(
        "Variável de ambiente DATABASE_URL não configurada. "
        "Defina no arquivo .env antes de rodar o script."
    )

if not GROQ_API_KEY:
    raise RuntimeError(
        "Variável de ambiente GROQ_API_KEY não configurada. "
        "Defina no arquivo .env com a sua chave do Groq."
    )

# Cliente Groq (Llama 3.2)
_groq_client = Groq(api_key=GROQ_API_KEY)

# Nome do modelo que será usado
GROQ_MODEL = "llama-3.1-8b-instant"  # você pode trocar por outro modelo suportado

# ---------------------------------------------------------------------
# FUNÇÕES DE BANCO DE DADOS
# ---------------------------------------------------------------------


def get_db_connection():
    """
    Abre uma conexão com o banco de dados usando DATABASE_URL.
    """
    logger.info("Conectando ao banco de dados Neon...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    logger.info("Conexão estabelecida.")
    return conn


def ensure_produtos_schema(conn) -> None:
    """
    Garante que a tabela 'produtos' possua as colunas necessárias
    para armazenar a classificação da IA.
    """
    logger.info("Verificando/ajustando colunas da tabela 'produtos'...")

    required_columns = {
        "produto_limpo": "TEXT",
        "marca": "TEXT",
        "categoria": "TEXT",
        "unidade": "TEXT",
        "nome_canonico": "TEXT",
        "classificacao_ia_json": "JSONB",
        "classificado_por_ia": "BOOLEAN DEFAULT FALSE",
        "ultima_classificacao_em": "TIMESTAMP",
    }

    with conn.cursor() as cur:
        # Descobrir colunas existentes
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'produtos'
            """
        )
        existentes = {row[0] for row in cur.fetchall()}

        # Adicionar colunas que faltam
        for col, col_type in required_columns.items():
            if col not in existentes:
                logger.info(f" - Adicionando coluna '{col}' ({col_type})...")
                cur.execute(
                    f"ALTER TABLE produtos ADD COLUMN {col} {col_type};"
                )

    conn.commit()
    logger.info("Tabela 'produtos' ajustada com sucesso.")


def buscar_produtos_pendentes(conn, limite: int = 200) -> List[Dict[str, Any]]:
    """
    Busca produtos que ainda não foram classificados pela IA.
    Critério: classificado_por_ia = FALSE ou colunas de classificação vazias.
    """
    logger.info(f"Buscando até {limite} produtos pendentes de classificação...")

    sql = """
        SELECT
            id_produto,
            descricao,
            produto_limpo,
            marca,
            categoria,
            unidade,
            nome_canonico,
            classificado_por_ia
        FROM produtos
        WHERE
            classificado_por_ia IS DISTINCT FROM TRUE
            OR produto_limpo IS NULL
            OR produto_limpo = ''
        ORDER BY id_produto
        LIMIT %s
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (limite,))
        rows = cur.fetchall()

    logger.info(f"Encontrados {len(rows)} produto(s) pendente(s).")
    return rows


def atualizar_produto_classificado(
    conn, id_produto: Any, dados: Dict[str, Any]
) -> None:
    """
    Atualiza um produto com as informações classificadas pela IA.
    """
    sql = """
        UPDATE produtos
        SET
            produto_limpo = %s,
            marca = %s,
            categoria = %s,
            unidade = %s,
            nome_canonico = %s,
            classificacao_ia_json = %s,
            classificado_por_ia = TRUE,
            ultima_classificacao_em = NOW()
        WHERE id_produto = %s
    """

    produto_limpo = dados.get("produto") or dados.get("produto_limpo") or ""
    marca = dados.get("marca") or ""
    categoria = dados.get("categoria") or ""
    unidade = dados.get("unidade") or ""
    nome_canonico = dados.get("nome_canonico") or produto_limpo

    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                produto_limpo,
                marca,
                categoria,
                unidade,
                nome_canonico,
                json.dumps(dados, ensure_ascii=False),
                id_produto,
            ),
        )

# ---------------------------------------------------------------------
# FUNÇÃO DE CHAMADA À IA (GROQ / LLAMA 3.2)
# ---------------------------------------------------------------------


def chamar_groq_para_produto(descricao_bruta: str) -> Dict[str, Any]:
    """
    Chama o modelo Llama 3.2 no Groq para padronizar a descrição de produto.

    Retorna sempre um dicionário Python.
    Em caso de erro, devolve uma estrutura mínima usando a própria descrição.
    """
    logger.info(f"Chamando IA para descrição: {descricao_bruta!r}")

    prompt = (
        "Você é um especialista em produtos de supermercado e varejo.\n\n"
        "Receberá o nome de um produto exatamente como está na nota fiscal. "
        "Sua tarefa é extrair e padronizar as seguintes informações:\n"
        "- produto: nome limpo e curto do item (ex: ARROZ, FEIJAO, LEITE INTEGRAL)\n"
        "- marca: marca principal (ex: TIROLEZ, ITAIPAVA). Se não souber, deixe vazio.\n"
        "- categoria: categoria geral (ex: ALIMENTO, LIMPEZA, HIGIENE, BEBIDA, CARNES, LATICINIOS, PADARIA etc.)\n"
        "- unidade: unidade principal (ex: kg, g, un, L, ml, pacote, cx)\n"
        "- nome_canonico: nome padronizado para agrupar produtos similares. "
        "Se não tiver certeza, use o mesmo valor de 'produto'.\n\n"
        "IMPORTANTE:\n"
        "- Responda APENAS um JSON VÁLIDO.\n"
        "- Não escreva explicações, apenas o objeto JSON.\n\n"
        f'Descrição do produto: "{descricao_bruta}"\n\n'
        'Formato de saída (exemplo):\n'
        '{"produto": "ARROZ", "marca": "TIO JOAO", "categoria": "ALIMENTO", "unidade": "kg", "nome_canonico": "ARROZ"}'
    )

    try:
        completion = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Você responde somente em JSON válido."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=256,
            response_format={"type": "json_object"},
        )

        content = completion.choices[0].message.content
        logger.debug(f"Resposta bruta da IA: {content!r}")

        # Garantir que é JSON
        dados = json.loads(content)
        if not isinstance(dados, dict):
            raise ValueError("Resposta da IA não é um objeto JSON.")

        return dados

    except Exception as e:
        logger.error(
            "Erro ao chamar Groq/Llama para descrição %r: %s",
            descricao_bruta,
            e,
        )
        # Fallback: devolve algo mínimo para não travar o processo
        return {
            "produto": descricao_bruta,
            "marca": "",
            "categoria": "OUTROS",
            "unidade": "",
            "nome_canonico": descricao_bruta,
            "erro_ia": str(e),
        }


# ---------------------------------------------------------------------
# FUNÇÃO PRINCIPAL
# ---------------------------------------------------------------------


def classificar_produtos_pendentes(lote: int = 200) -> None:
    """
    Fluxo principal da classificação:
    - Conecta ao banco
    - Garante schema
    - Busca produtos pendentes
    - Chama a IA para cada um
    - Atualiza a tabela
    """
    logger.info(
        "Iniciando classificação de produtos com IA (Groq/Llama) (lote=%d)...",
        lote,
    )

    conn = None
    try:
        conn = get_db_connection()
        ensure_produtos_schema(conn)

        pendentes = buscar_produtos_pendentes(conn, limite=lote)
        if not pendentes:
            logger.info("Nenhum produto pendente. Encerrando.")
            print("✅ Nenhum produto pendente de classificação. Tudo organizado!")
            return

        print(f"\n🧠 Classificando {len(pendentes)} produto(s) com IA (Groq)...\n")

        for idx, prod in enumerate(pendentes, start=1):
            id_prod = prod["id_produto"]
            descricao = prod["descricao"]

            print(f"[{idx}/{len(pendentes)}] Produto ID={id_prod}")
            print(f"   Descrição bruta: {descricao}")

            dados_ia = chamar_groq_para_produto(descricao)
            atualizar_produto_classificado(conn, id_prod, dados_ia)
            conn.commit()

        logger.info("Classificação concluída com sucesso.")
        print("\n✅ Classificação concluída com sucesso.")

    except Exception as e:
        logger.error("Erro geral ao rodar o classificador de IA: %s", e, exc_info=True)
        print(f"❌ Erro ao rodar o classificador de IA: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            logger.info("Conexão com o banco encerrada.")


# ---------------------------------------------------------------------
# EXECUÇÃO DIRETA
# ---------------------------------------------------------------------

if __name__ == "__main__":
    # Você pode ajustar o tamanho do lote aqui, se quiser
    classificar_produtos_pendentes(lote=200)

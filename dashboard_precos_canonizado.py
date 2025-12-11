# dashboard_precos_canonizado.py
# Dashboard avançado em Streamlit para explorar o histórico de preços
# com sistema de canonização de nomes de produtos.
#
# Requisitos principais:
#   pip install streamlit psycopg2-binary pandas numpy
#   pip install fuzzywuzzy python-Levenshtein   (opcional, melhora similaridade)
#
# Execução:
#   1) Configure a variável de ambiente DATABASE_URL
#   2) No PowerShell:
#        cd C:\GestaoCompras
#        streamlit run dashboard_precos_canonizado.py

import os
import re
import json
from datetime import date, datetime
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
import hashlib

import psycopg2
import pandas as pd
import numpy as np
import streamlit as st

# Tentar importar bibliotecas para similaridade (opcionais)
try:
    from fuzzywuzzy import fuzz, process
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False
    # Aviso leve – não para a execução
    st.warning(
        "Biblioteca de similaridade (fuzzywuzzy) não instalada.\n"
        "Para melhor precisão na canonização, rode:\n"
        "  pip install fuzzywuzzy python-Levenshtein"
    )

# ----------------------------------------------------------------------
# CONFIGURAÇÃO DO SISTEMA - DICIONÁRIOS BÁSICOS
# ----------------------------------------------------------------------

# Dicionário de produtos principais e suas variações (pode futuramente vir de JSON)
PRODUTOS_REFERENCIA: Dict[str, List[str]] = {
    "ARROZ": ["arroz branco", "arroz tipo 1", "arroz tipo 2", "arroz integral", "arroz parboilizado"],
    "FEIJÃO": ["feijão carioca", "feijão preto", "feijão mulatinho", "feijão"],
    "AÇÚCAR": ["açúcar cristal", "açúcar refinado", "açúcar mascavo", "açúcar"],
    "CAFÉ": ["café em pó", "café torrado", "café moído", "café solúvel"],
    "ÓLEO": ["óleo de soja", "óleo de girassol", "óleo", "óleo vegetal"],
    "LEITE": ["leite integral", "leite desnatado", "leite em pó", "leite condensado"],
    "FARINHA": ["farinha de trigo", "farinha de mandioca", "farinha de milho", "farinha"],
    "MACARRÃO": ["macarrão espaguete", "macarrão parafuso", "macarrão", "massa"],
    "BOLACHA": ["bolacha água e sal", "bolacha doce", "biscoito", "bolacha"],
    "SAL": ["sal refinado", "sal grosso", "sal"],
    "AZEITE": ["azeite de oliva", "azeite"],
    "VINAGRE": ["vinagre de álcool", "vinagre de maçã", "vinagre"],
    "MOLHO": ["molho de tomate", "molho shoyu", "molho"],
    "SABONETE": ["sabonete em barra", "sabonete líquido", "sabonete"],
    "SHAMPOO": ["shampoo", "condicionador"],
    "PAPEL HIGIÊNICO": ["papel higiênico", "papel"],
    "DETERGENTE": ["detergente líquido", "detergente em pó", "detergente"],
    "DESINFETANTE": ["desinfetante", "álcool em gel", "álcool"],
    "AMACIANTE": ["amaciante", "amaciante de roupas"],
    "SABÃO": ["sabão em pó", "sabão em barra", "sabão"],
    "CARNE": ["carne bovina", "carne suína", "carne de frango", "carne"],
    "FRANGO": ["frango", "peito de frango", "coxa de frango"],
    "PEIXE": ["peixe", "sardinha", "atum"],
    "OVOS": ["ovos", "ovo"],
    "QUEIJO": ["queijo mussarela", "queijo prato", "queijo", "requeijão"],
    "PRESUNTO": ["presunto", "mortadela", "apresuntado"],
    "MANTEIGA": ["manteiga", "margarina"],
    "IOGURTE": ["iogurte", "iogurte natural", "iogurte com frutas"],
    "REFRIGERANTE": ["refrigerante", "coca-cola", "guaraná", "pepsi"],
    "SUCO": ["suco de laranja", "suco de uva", "suco", "néctar"],
    "ÁGUA": ["água mineral", "água com gás", "água"],
    "CERVEJA": ["cerveja", "cerveja lata", "cerveja long neck"],
    "VINHO": ["vinho tinto", "vinho branco", "vinho"],
    "PÃO": ["pão francês", "pão de forma", "pão"],
    "BOLO": ["bolo", "bolo pronto"],
    "BISCOITO": ["biscoito", "biscoito recheado", "biscoito água e sal"],
    "CHOCOLATE": ["chocolate", "chocolate em barra", "bombom"],
    "BALAS": ["balas", "pirulitos", "gomas"],
    "SORVETE": ["sorvete", "picolé", "sundae"],
    "TEMPERO": ["tempero", "caldo de carne", "caldo de galinha"],
    "ALHO": ["alho", "alho poró"],
    "CEBOLA": ["cebola", "cebola roxa"],
    "TOMATE": ["tomate", "tomate italiano"],
    "BATATA": ["batata", "batata inglesa", "batata doce"],
    "CENOURA": ["cenoura", "cenoura baby"],
    "ALFACE": ["alface", "alface americana", "alface crespa"],
    "BANANA": ["banana", "banana nanica", "banana prata"],
    "MAÇÃ": ["maçã", "maçã fuji", "maçã gala"],
    "LARANJA": ["laranja", "laranja pera", "laranja lima"],
    "LIMÃO": ["limão", "limão taiti", "limão siciliano"],
}

# Palavras a serem ignoradas na canonização
PALAVRAS_IGNORAR = {
    "de", "da", "do", "das", "dos", "com", "sem", "para", "por", "em", "no", "na",
    "tipo", "kg", "g", "mg", "ml", "l", "lt", "cm", "mm", "un", "und", "pct", "pc",
    "cx", "caixa", "pacote", "embalagem", "saco", "lata", "garrafa", "frasco",
    "pote", "tablete", "barra", "unidade", "gramas", "quilos", "litros", "mililitros",
    "extra", "especial", "premium", "tradicional", "original", "light", "diet",
    "zero", "integral", "desnatado", "natural", "fresco", "congelado", "seco"
}

# ----------------------------------------------------------------------
# CONEXÃO COM O BANCO
# ----------------------------------------------------------------------

@st.cache_resource
def get_connection():
    """Abre e cacheia a conexão com o banco Neon usando DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        st.error(
            "⚠️ DATABASE_URL não configurada.\n\n"
            "Defina a URL de conexão do Neon antes de rodar o dashboard."
        )
        st.stop()

    try:
        conn = psycopg2.connect(database_url)
        # Teste simples
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar no banco: {e}")
        st.stop()


def run_query(sql: str, params=None) -> pd.DataFrame:
    """Executa uma consulta SQL e retorna um DataFrame."""
    conn = get_connection()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Erro ao executar consulta SQL: {e}")
        st.code(sql[:200] + "..." if len(sql) > 200 else sql)
        return pd.DataFrame()


def execute_sql(sql: str, params=None) -> Tuple[bool, str]:
    """Executa uma instrução SQL (INSERT, UPDATE, DELETE)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
        conn.commit()
        return True, "Operação realizada com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao executar SQL: {e}"

# ----------------------------------------------------------------------
# SISTEMA AVANÇADO DE CANONIZAÇÃO
# ----------------------------------------------------------------------

class CanonizadorProdutos:
    """Classe para canonização avançada de nomes de produtos."""

    def __init__(self):
        self.produtos_referencia = PRODUTOS_REFERENCIA
        self.palavras_ignorar = PALAVRAS_IGNORAR
        self.cache_canonizacao: Dict[str, str] = {}

    def preprocessar_texto(self, texto: str) -> str:
        """Normaliza texto: minúsculas, remove especiais, compacta espaços."""
        if not texto:
            return ""
        texto = texto.lower().strip()
        texto = re.sub(r"[^\w\s]", " ", texto)
        texto = re.sub(r"\s+", " ", texto)
        return texto

    def extrair_palavras_chave(self, texto: str) -> List[str]:
        """Extrai palavras-chave relevantes."""
        texto = self.preprocessar_texto(texto)
        palavras = texto.split()
        return [
            p
            for p in palavras
            if p not in self.palavras_ignorar
            and len(p) > 2
            and not p.isdigit()
        ]

    def encontrar_produto_por_palavras_chave(self, texto: str) -> Optional[str]:
        """Encontra o produto principal usando palavras-chave nas variações."""
        palavras = self.extrair_palavras_chave(texto)

        for produto_ref, variacoes in self.produtos_referencia.items():
            for variacao in variacoes:
                variacao_palavras = set(variacao.split())
                if any(p in variacao_palavras for p in palavras):
                    return produto_ref

        for produto_ref in self.produtos_referencia.keys():
            produto_ref_lower = produto_ref.lower()
            if any(p in produto_ref_lower for p in palavras):
                return produto_ref

        return None

    def encontrar_produto_por_similaridade(
        self, texto: str, threshold: int = 70
    ) -> Optional[str]:
        """Encontra produto por similaridade usando fuzzy matching."""
        if not FUZZYWUZZY_AVAILABLE:
            return None

        texto = self.preprocessar_texto(texto)

        todas_variacoes: List[Tuple[str, str]] = []
        for produto_ref, variacoes in self.produtos_referencia.items():
            todas_variacoes.extend([(v, produto_ref) for v in variacoes])
            todas_variacoes.append((produto_ref.lower(), produto_ref))

        melhor_match = process.extractOne(
            texto, [v[0] for v in todas_variacoes], scorer=fuzz.token_sort_ratio
        )
        if melhor_match and melhor_match[1] >= threshold:
            for variacao, produto_ref in todas_variacoes:
                if variacao == melhor_match[0]:
                    return produto_ref

        return None

    def canonizar_descricao(self, descricao: str) -> str:
        """Canoniza uma descrição de produto em um nome padrão (string)."""
        if not descricao:
            return "PRODUTO_NAO_IDENTIFICADO"

        cache_key = hashlib.md5(descricao.lower().encode()).hexdigest()
        if cache_key in self.cache_canonizacao:
            return self.cache_canonizacao[cache_key]

        # 1. Palavras-chave
        produto = self.encontrar_produto_por_palavras_chave(descricao)

        # 2. Similaridade (se disponível)
        if not produto and FUZZYWUZZY_AVAILABLE:
            produto = self.encontrar_produto_por_similaridade(descricao)

        # 3. Fallback: primeira palavra relevante
        if not produto:
            palavras = self.extrair_palavras_chave(descricao)
            if palavras:
                produto = palavras[0].upper()
            else:
                produto = descricao[:30].strip().upper()
                if len(descricao) > 30:
                    produto += "..."

        self.cache_canonizacao[cache_key] = produto
        return produto

    def batch_canonizar_descricoes(self, descricoes: List[str]) -> Dict[str, str]:
        """Canoniza várias descrições de uma vez."""
        return {desc: self.canonizar_descricao(desc) for desc in descricoes}

    def analisar_padroes_descricao(self, df_produtos: pd.DataFrame) -> pd.DataFrame:
        """Analisa padrões nas descrições para sugerir regras de canonização."""
        todas_descricoes = " ".join(
            df_produtos["descricao"].astype(str).str.lower()
        ).split()

        palavras_frequentes = Counter(
            [
                p
                for p in todas_descricoes
                if p not in self.palavras_ignorar and len(p) > 2
            ]
        ).most_common(50)

        df_produtos = df_produtos.copy()
        df_produtos["tamanho_descricao"] = df_produtos["descricao"].str.len()

        produtos_sem_canonico = df_produtos[
            df_produtos["nome_canonico"].isna()
            | (df_produtos["nome_canonico"] == "")
        ]

        prefixos_comuns = defaultdict(int)
        for desc in df_produtos["descricao"]:
            palavras = desc.lower().split()[:3]
            if palavras:
                prefixo = " ".join(palavras[:2])
                prefixos_comuns[prefixo] += 1

        sugestoes = []
        for prefixo, count in sorted(
            prefixos_comuns.items(), key=lambda x: x[1], reverse=True
        )[:10]:
            if count > 2:
                sugestoes.append(f"Prefixo comum: '{prefixo}' ({count} ocorrências)")

        analise = {
            "total_produtos": len(df_produtos),
            "produtos_sem_canonico": len(produtos_sem_canonico),
            "palavras_frequentes": palavras_frequentes[:20],
            "tamanho_medio_descricao": df_produtos["tamanho_descricao"].mean(),
            "sugestoes_regras": sugestoes[:5],
        }
        return pd.DataFrame([analise])

# ----------------------------------------------------------------------
# BANCO: FUNÇÕES PARA CANONIZAÇÃO
# ----------------------------------------------------------------------

def carregar_produtos_para_canonizacao() -> pd.DataFrame:
    """Carrega produtos com quantidade de compras, para análise/canonização."""
    sql = """
        SELECT 
            p.id_produto,
            p.descricao,
            p.nome_canonico,
            p.categoria,
            COUNT(h.id) as total_compras
        FROM produtos p
        LEFT JOIN historico_precos h ON p.id_produto = h.id_produto
        GROUP BY p.id_produto, p.descricao, p.nome_canonico, p.categoria
        ORDER BY total_compras DESC, p.descricao;
    """
    return run_query(sql)


def atualizar_nome_canonico_batch(df_produtos_atualizar: pd.DataFrame) -> Tuple[bool, str]:
    """Atualiza nomes canônicos em lote na tabela produtos."""
    if df_produtos_atualizar.empty:
        return True, "Nenhum produto para atualizar."

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            for _, row in df_produtos_atualizar.iterrows():
                sql = """
                    UPDATE produtos 
                    SET nome_canonico = %s
                    WHERE id_produto = %s
                """
                cursor.execute(sql, (row["nome_canonico_novo"], row["id_produto"]))
        conn.commit()
        return True, f"Atualizados {len(df_produtos_atualizar)} produtos com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao atualizar produtos: {e}"


def criar_tabela_canonizacao_regras() -> Tuple[bool, str]:
    """Cria tabela de regras de canonização (se não existir)."""
    sql = """
        CREATE TABLE IF NOT EXISTS canonizacao_regras (
            id SERIAL PRIMARY KEY,
            padrao_descricao TEXT,
            nome_canonico TEXT,
            tipo_regra VARCHAR(50),
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ativo BOOLEAN DEFAULT TRUE,
            usuario_criacao VARCHAR(100)
        );
        
        CREATE INDEX IF NOT EXISTS idx_canonizacao_padrao 
        ON canonizacao_regras(padrao_descricao);
        
        CREATE INDEX IF NOT EXISTS idx_canonizacao_ativo 
        ON canonizacao_regras(ativo);
    """
    return execute_sql(sql)


def salvar_regra_canonizacao(padrao: str, nome_canonico: str, tipo: str = "regex") -> Tuple[bool, str]:
    """Insere uma regra de canonização na tabela canonizacao_regras."""
    sql = """
        INSERT INTO canonizacao_regras 
        (padrao_descricao, nome_canonico, tipo_regra, usuario_criacao)
        VALUES (%s, %s, %s, %s)
    """
    return execute_sql(sql, (padrao, nome_canonico, tipo, "dashboard"))


def carregar_regras_canonizacao(ativas: bool = True) -> pd.DataFrame:
    """Carrega regras de canonização do banco."""
    sql = """
        SELECT id, padrao_descricao, nome_canonico, tipo_regra, 
               data_criacao, ativo
        FROM canonizacao_regras
        WHERE ativo = %s
        ORDER BY data_criacao DESC;
    """
    return run_query(sql, (ativas,))


def aplicar_regras_canonizacao(descricao: str, regras_df: pd.DataFrame) -> Optional[str]:
    """Aplica regras de canonização à descrição."""
    for _, regra in regras_df.iterrows():
        padrao = regra["padrao_descricao"]
        nome_canonico = regra["nome_canonico"]

        if regra["tipo_regra"] == "regex":
            try:
                if re.search(padrao, descricao, re.IGNORECASE):
                    return nome_canonico
            except re.error:
                continue
        elif regra["tipo_regra"] == "exato":
            if descricao.lower() == padrao.lower():
                return nome_canonico
        elif regra["tipo_regra"] == "contem":
            if padrao.lower() in descricao.lower():
                return nome_canonico
    return None

# ----------------------------------------------------------------------
# FUNÇÕES DE CARREGAMENTO PARA DASHBOARD (AGRUPADO POR nome_canonico)
# ----------------------------------------------------------------------

@st.cache_data(ttl=300)
def carregar_produtos_agrupados() -> pd.DataFrame:
    """Carrega produtos agrupados por nome canônico (ou descrição)."""
    sql = """
        SELECT 
            COALESCE(NULLIF(p.nome_canonico, ''), p.descricao) as nome_agrupado,
            COUNT(DISTINCT p.id_produto) as qtd_variacoes,
            COUNT(h.id) as total_compras,
            MIN(h.preco_unitario) as preco_minimo,
            MAX(h.preco_unitario) as preco_maximo,
            AVG(h.preco_unitario) as preco_medio,
            STRING_AGG(DISTINCT p.descricao, '; ') as exemplos_descricoes
        FROM produtos p
        LEFT JOIN historico_precos h ON p.id_produto = h.id_produto
        GROUP BY COALESCE(NULLIF(p.nome_canonico, ''), p.descricao)
        HAVING COUNT(DISTINCT p.id_produto) >= 1
        ORDER BY total_compras DESC, nome_agrupado;
    """
    return run_query(sql)


@st.cache_data(ttl=300)
def carregar_historico_agrupado(nome_agrupado: str) -> pd.DataFrame:
    """Carrega histórico de preços para um grupo de produtos (nome_agrupado)."""
    sql = """
        SELECT 
            h.data_nota,
            h.mercado,
            h.preco_unitario,
            h.quantidade,
            h.preco_total,
            p.descricao as descricao_original,
            p.nome_canonico
        FROM historico_precos h
        JOIN produtos p ON h.id_produto = p.id_produto
        WHERE COALESCE(NULLIF(p.nome_canonico, ''), p.descricao) = %s
        ORDER BY h.data_nota DESC;
    """
    df = run_query(sql, (nome_agrupado,))
    if not df.empty:
        df["data_nota"] = pd.to_datetime(df["data_nota"], errors="coerce")
        df["preco_unitario"] = pd.to_numeric(df["preco_unitario"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def carregar_analise_mercados_agrupada() -> pd.DataFrame:
    """Carrega análise de mercados por produto agrupado."""
    sql = """
        SELECT 
            COALESCE(NULLIF(p.nome_canonico, ''), p.descricao) as produto,
            h.mercado,
            COUNT(*) as qtd_compras,
            AVG(h.preco_unitario) as preco_medio,
            MIN(h.preco_unitario) as preco_minimo,
            MAX(h.preco_unitario) as preco_maximo,
            STDDEV(h.preco_unitario) as desvio_padrao
        FROM historico_precos h
        JOIN produtos p ON h.id_produto = p.id_produto
        GROUP BY 
            COALESCE(NULLIF(p.nome_canonico, ''), p.descricao),
            h.mercado
        ORDER BY produto, qtd_compras DESC;
    """
    return run_query(sql)


@st.cache_data(ttl=300)
def carregar_variacao_mensal_agrupada() -> pd.DataFrame:
    """Carrega variação mensal por produto agrupado."""
    sql = """
        SELECT 
            COALESCE(NULLIF(p.nome_canonico, ''), p.descricao) as produto,
            DATE_TRUNC('month', h.data_nota) as mes,
            COUNT(*) as qtd_compras,
            AVG(h.preco_unitario) as preco_medio,
            MIN(h.data_nota) as primeira_compra_mes,
            MAX(h.data_nota) as ultima_compra_mes
        FROM historico_precos h
        JOIN produtos p ON h.id_produto = p.id_produto
        GROUP BY 
            COALESCE(NULLIF(p.nome_canonico, ''), p.descricao),
            DATE_TRUNC('month', h.data_nota)
        ORDER BY produto, mes;
    """
    df = run_query(sql)
    if not df.empty:
        df["mes"] = pd.to_datetime(df["mes"], errors="coerce")
        df["mes_str"] = df["mes"].dt.strftime("%Y-%m")
        df["variacao_mensal"] = (
            df.groupby("produto")["preco_medio"].pct_change() * 100
        )
    return df

# ----------------------------------------------------------------------
# VISUALIZAÇÕES
# ----------------------------------------------------------------------

def criar_visualizacao_agrupamento(df_agrupados: pd.DataFrame):
    """Visão geral dos produtos agrupados."""
    if df_agrupados.empty:
        st.warning("Nenhum dado disponível para visualização.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Produtos Agrupados", len(df_agrupados))
    with col2:
        st.metric("Total de Variações", int(df_agrupados["qtd_variacoes"].sum()))
    with col3:
        st.metric("Compras Registradas", int(df_agrupados["total_compras"].sum()))
    with col4:
        preco_medio_geral = df_agrupados["preco_medio"].mean()
        st.metric("Preço Médio Geral", f"R$ {preco_medio_geral:.2f}")

    st.subheader("📋 Produtos Agrupados por Nome Canônico")

    df_display = df_agrupados.copy()
    df_display["exemplos_descricoes"] = df_display["exemplos_descricoes"].apply(
        lambda x: x[:100] + "..." if x and len(x) > 100 else x
    )

    st.dataframe(
        df_display,
        width="stretch",
        hide_index=True,
        column_config={
            "nome_agrupado": "Produto (Agrupado)",
            "qtd_variacoes": "Variações",
            "total_compras": "Compras",
            "preco_minimo": "Preço Mín",
            "preco_maximo": "Preço Máx",
            "preco_medio": "Preço Médio",
            "exemplos_descricoes": "Exemplos de Descrições",
        },
    )

    st.subheader("📊 Distribuição de Variações por Produto")
    df_top = df_agrupados.nlargest(20, "qtd_variacoes")
    chart_data = df_top.set_index("nome_agrupado")[["qtd_variacoes"]]
    st.bar_chart(chart_data)


def analisar_impacto_canonizacao(df_produtos: pd.DataFrame, df_agrupados: pd.DataFrame):
    """Analisa o impacto da canonização na base."""
    st.subheader("📈 Análise do Impacto da Canonização")

    total_produtos = len(df_produtos)
    produtos_com_canonico = len(
        df_produtos[
            df_produtos["nome_canonico"].notna()
            & (df_produtos["nome_canonico"] != "")
        ]
    )

    if total_produtos > 0:
        taxa_canonizacao = (produtos_com_canonico / total_produtos) * 100
        taxa_agrupamento = (1 - (len(df_agrupados) / total_produtos)) * 100
    else:
        taxa_canonizacao = 0
        taxa_agrupamento = 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Produtos", total_produtos)
    with col2:
        st.metric(
            "Produtos Canonizados",
            produtos_com_canonico,
            f"{taxa_canonizacao:.1f}%",
        )
    with col3:
        st.metric(
            "Redução de Itens (Agrupamento)",
            f"{len(df_agrupados)} agrupados",
            f"{taxa_agrupamento:.1f}%",
        )

    st.subheader("📊 Estatísticas de Agrupamento")
    if df_agrupados.empty:
        return

    df_dist = df_agrupados["qtd_variacoes"].value_counts().sort_index()
    df_dist = df_dist.reset_index()
    df_dist.columns = ["qtd_variacoes", "frequencia"]
    st.bar_chart(df_dist.set_index("qtd_variacoes"))

    st.markdown("**Produtos com Mais Variações:**")
    df_mais_variacoes = df_agrupados.nlargest(10, "qtd_variacoes")

    for _, row in df_mais_variacoes.iterrows():
        with st.expander(
            f"{row['nome_agrupado']} ({row['qtd_variacoes']} variações)"
        ):
            st.write("**Descrições originais:**")
            exemplos = (row["exemplos_descricoes"] or "").split("; ")
            for ex in exemplos[:5]:
                st.write(f"- {ex}")
            if len(exemplos) > 5:
                st.write(f"... e mais {len(exemplos) - 5} descrições")

# ----------------------------------------------------------------------
# MÓDULOS DO DASHBOARD
# ----------------------------------------------------------------------

def exibir_visao_geral_agrupada():
    st.header("📈 Visão Geral - Produtos Agrupados")

    with st.spinner("Carregando dados agrupados..."):
        df_agrupados = carregar_produtos_agrupados()
        df_produtos = carregar_produtos_para_canonizacao()

    if df_agrupados.empty:
        st.warning("Nenhum dado encontrado. Rode o processar_notas.py primeiro.")
        return

    criar_visualizacao_agrupamento(df_agrupados)
    analisar_impacto_canonizacao(df_produtos, df_agrupados)

    st.divider()
    st.subheader("📥 Exportação de Dados")

    col1, col2 = st.columns(2)
    with col1:
        csv = df_agrupados.to_csv(index=False)
        st.download_button(
            label="📊 Baixar Agrupamentos (CSV)",
            data=csv,
            file_name=f"produtos_agrupados_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        csv2 = df_produtos.to_csv(index=False)
        st.download_button(
            label="📋 Baixar Lista Completa (CSV)",
            data=csv2,
            file_name=f"produtos_completos_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def exibir_analise_produto():
    st.header("🔍 Análise Detalhada por Produto")

    df_agrupados = carregar_produtos_agrupados()
    if df_agrupados.empty:
        st.warning("Nenhum produto encontrado.")
        return

    produto_selecionado = st.selectbox(
        "Selecione um produto:",
        options=df_agrupados["nome_agrupado"].tolist(),
        help="Produto agrupado por nome canônico/descrição.",
    )
    if not produto_selecionado:
        return

    with st.spinner(f"Carregando histórico de {produto_selecionado}..."):
        df_historico = carregar_historico_agrupado(produto_selecionado)

    if df_historico.empty:
        st.info(f"Nenhum histórico encontrado para {produto_selecionado}.")
        return

    produto_info = df_agrupados[
        df_agrupados["nome_agrupado"] == produto_selecionado
    ].iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Variações", int(produto_info["qtd_variacoes"]))
    with col2:
        st.metric("Compras", int(produto_info["total_compras"]))
    with col3:
        st.metric("Preço Médio", f"R$ {produto_info['preco_medio']:.2f}")
    with col4:
        st.metric(
            "Faixa de Preço",
            f"R$ {produto_info['preco_minimo']:.2f} - R$ {produto_info['preco_maximo']:.2f}",
        )

    tab1, tab2, tab3 = st.tabs(
        ["📈 Evolução Temporal", "🏪 Análise por Mercado", "📋 Dados Detalhados"]
    )

    with tab1:
        df_hist = df_historico.copy()
        df_hist_group = (
            df_hist.groupby("data_nota")
            .agg(
                preco_medio=("preco_unitario", "mean"),
                preco_min=("preco_unitario", "min"),
                preco_max=("preco_unitario", "max"),
                quantidade_total=("quantidade", "sum"),
            )
            .reset_index()
        )
        df_hist_group = df_hist_group.set_index("data_nota")[
            ["preco_medio", "preco_min", "preco_max"]
        ]
        st.line_chart(df_hist_group)

    with tab2:
        if "mercado" in df_historico.columns:
            df_mercado = (
                df_historico.groupby("mercado")
                .agg(
                    preco_medio=("preco_unitario", "mean"),
                    preco_min=("preco_unitario", "min"),
                    preco_max=("preco_unitario", "max"),
                    qtd=("preco_unitario", "count"),
                    quantidade_total=("quantidade", "sum"),
                )
                .round(2)
            )
            st.dataframe(df_mercado, width="stretch")

    with tab3:
        st.dataframe(
            df_historico.sort_values("data_nota", ascending=False),
            width="stretch",
            hide_index=True,
        )


def exibir_comparacao_mercados():
    st.header("🏪 Comparação de Preços entre Mercados")

    with st.spinner("Carregando dados de mercados..."):
        df_mercados = carregar_analise_mercados_agrupada()

    if df_mercados.empty:
        st.warning("Nenhum dado encontrado para comparação.")
        return

    col1, col2 = st.columns(2)
    with col1:
        produtos_disponiveis = df_mercados["produto"].unique().tolist()
        produto_filtro = st.multiselect(
            "Filtrar produtos:",
            options=produtos_disponiveis,
            default=produtos_disponiveis[:5] if produtos_disponiveis else [],
        )
    with col2:
        mercados_disponiveis = df_mercados["mercado"].unique().tolist()
        mercado_filtro = st.multiselect(
            "Filtrar mercados:",
            options=mercados_disponiveis,
            default=mercados_disponiveis,
        )

    df_filtrado = df_mercados.copy()
    if produto_filtro:
        df_filtrado = df_filtrado[df_filtrado["produto"].isin(produto_filtro)]
    if mercado_filtro:
        df_filtrado = df_filtrado[df_filtrado["mercado"].isin(mercado_filtro)]

    st.subheader("📊 Comparação de Preços Médios")
    if df_filtrado.empty:
        st.info("Nenhum dado após os filtros.")
        return

    pivot_data = df_filtrado.pivot_table(
        index="produto", columns="mercado", values="preco_medio", aggfunc="mean"
    ).round(2)

    def color_negative_red(val):
        if pd.isna(val):
            return ""
        media = pivot_data.mean().mean()
        return (
            "background-color: #ffcccc" if val > media else "background-color: #ccffcc"
        )

    styled_df = pivot_data.style.applymap(color_negative_red)
    st.dataframe(styled_df, width="stretch")

    st.subheader("📈 Estatísticas de Mercado")
    for mercado in pivot_data.columns:
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            preco_medio_mercado = pivot_data[mercado].mean()
            if not pd.isna(preco_medio_mercado):
                st.metric(f"Média - {mercado}", f"R$ {preco_medio_mercado:.2f}")
        with col_m2:
            produtos_mercado = pivot_data[mercado].count()
            st.metric(f"Produtos - {mercado}", produtos_mercado)
        with col_m3:
            if len(pivot_data.columns) > 1:
                mercado_mais_barato = pivot_data.idxmin(axis=1)
                porcentagem_mais_barato = (
                    mercado_mais_barato[mercado_mais_barato == mercado].count()
                    / len(mercado_mais_barato)
                    * 100
                )
                st.metric(
                    f"% Produtos onde é mais barato - {mercado}",
                    f"{porcentagem_mais_barato:.1f}%",
                )

    st.subheader("💡 Sugestões de Economia")
    for produto in pivot_data.index:
        precos = pivot_data.loc[produto].dropna()
        if len(precos) >= 2:
            mercado_mais_barato = precos.idxmin()
            mercado_mais_caro = precos.idxmax()
            diferenca = precos.max() - precos.min()
            if diferenca > 0:
                st.info(
                    f"**{produto}**: comprando no **{mercado_mais_barato}** "
                    f"(R$ {precos.min():.2f}) em vez do **{mercado_mais_caro}** "
                    f"(R$ {precos.max():.2f}), economia de R$ {diferenca:.2f} "
                    f"({(diferenca / precos.max() * 100):.1f}% por unidade)."
                )


def exibir_variacao_mensal():
    st.header("📆 Variação Mensal por Produto")

    with st.spinner("Carregando variação mensal..."):
        df_variacao = carregar_variacao_mensal_agrupada()

    if df_variacao.empty:
        st.warning("Nenhum dado encontrado para análise mensal.")
        return

    produtos_disponiveis = df_variacao["produto"].unique().tolist()
    produto_selecionado = st.selectbox(
        "Selecione um produto para análise:", options=produtos_disponiveis
    )
    if not produto_selecionado:
        return

    df_produto = df_variacao[df_variacao["produto"] == produto_selecionado]
    if df_produto.empty:
        st.info(f"Nenhum dado mensal encontrado para {produto_selecionado}.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Meses Analisados", df_produto["mes_str"].nunique())
    with col2:
        variacao_total = (
            (df_produto["preco_medio"].iloc[-1] - df_produto["preco_medio"].iloc[0])
            / df_produto["preco_medio"].iloc[0]
            * 100
        )
        st.metric("Variação Total", f"{variacao_total:.1f}%")
    with col3:
        max_var = df_produto["variacao_mensal"].abs().max()
        st.metric("Maior Variação Mensal", f"{max_var:.1f}%")

    st.subheader("📈 Evolução do Preço Médio Mensal")
    df_grafico = df_produto.set_index("mes")[["preco_medio"]]
    st.line_chart(df_grafico)

    st.subheader("📋 Dados Mensais Detalhados")
    df_display = df_produto.copy()
    df_display["preco_medio"] = df_display["preco_medio"].apply(
        lambda x: f"R$ {x:.2f}"
    )
    df_display["variacao_mensal"] = df_display["variacao_mensal"].apply(
        lambda x: f"{x:+.1f}%" if not pd.isna(x) else "-"
    )
    st.dataframe(
        df_display[["mes_str", "qtd_compras", "preco_medio", "variacao_mensal"]],
        width="stretch",
        hide_index=True,
        column_config={
            "mes_str": "Mês",
            "qtd_compras": "Compras",
            "preco_medio": "Preço Médio",
            "variacao_mensal": "Variação %",
        },
    )

    st.subheader("📊 Sazonalidade (Média por Mês do Ano)")
    if len(df_produto) >= 3:
        df_produto = df_produto.copy()
        df_produto["mes_num"] = df_produto["mes"].dt.month
        df_saz = (
            df_produto.groupby("mes_num")
            .agg(preco_medio=("preco_medio", "mean"), qtd=("qtd_compras", "sum"))
            .reset_index()
        )
        meses_nomes = [
            "Jan",
            "Fev",
            "Mar",
            "Abr",
            "Mai",
            "Jun",
            "Jul",
            "Ago",
            "Set",
            "Out",
            "Nov",
            "Dez",
        ]
        df_saz["mes_nome"] = df_saz["mes_num"].apply(
            lambda x: meses_nomes[x - 1] if 1 <= x <= 12 else str(x)
        )
        st.bar_chart(df_saz.set_index("mes_nome")[["preco_medio"]])


def exibir_sistema_canonizacao():
    st.header("🔄 Sistema de Canonização de Produtos")

    canonizador = CanonizadorProdutos()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📊 Análise Atual",
            "🔄 Canonização em Lote",
            "🔍 Teste Individual",
            "📋 Regras Personalizadas",
            "📈 Estatísticas",
        ]
    )

    with tab1:
        st.subheader("📊 Situação Atual")

        with st.spinner("Carregando dados de produtos..."):
            df_produtos = carregar_produtos_para_canonizacao()

        if df_produtos.empty:
            st.warning("Nenhum produto encontrado.")
            return

        total_produtos = len(df_produtos)
        produtos_sem_canonico = len(
            df_produtos[
                df_produtos["nome_canonico"].isna()
                | (df_produtos["nome_canonico"] == "")
            ]
        )
        produtos_com_canonico = total_produtos - produtos_sem_canonico

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Produtos", total_produtos)
        with col2:
            st.metric("Canonizados", produtos_com_canonico)
        with col3:
            st.metric("Sem Canonizar", produtos_sem_canonico)

        if produtos_sem_canonico > 0:
            st.subheader("📋 Produtos sem Nome Canônico")
            produtos_sem = df_produtos[
                df_produtos["nome_canonico"].isna()
                | (df_produtos["nome_canonico"] == "")
            ]
            produtos_sem = produtos_sem.sort_values(
                "total_compras", ascending=False
            )
            st.dataframe(
                produtos_sem[["descricao", "total_compras"]],
                width="stretch",
                hide_index=True,
            )

    with tab2:
        st.subheader("🔄 Canonização em Lote")

        df_produtos = carregar_produtos_para_canonizacao()
        df_produtos_sem = df_produtos[
            df_produtos["nome_canonico"].isna()
            | (df_produtos["nome_canonico"] == "")
        ]

        if df_produtos_sem.empty:
            st.success("✅ Todos os produtos já possuem nome canônico.")
        else:
            st.info(
                f"{len(df_produtos_sem)} produto(s) sem nome canônico serão analisados."
            )

            col1, col2 = st.columns(2)
            with col1:
                usar_fuzzy = st.checkbox(
                    "Usar correspondência fuzzy",
                    value=FUZZYWUZZY_AVAILABLE,
                    disabled=not FUZZYWUZZY_AVAILABLE,
                )
            with col2:
                threshold_fuzzy = st.slider(
                    "Limite de similaridade (%)",
                    50,
                    100,
                    70,
                    disabled=not (FUZZYWUZZY_AVAILABLE and usar_fuzzy),
                )

            if st.button(
                "🚀 Executar Canonização em Lote",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Processando produtos..."):
                    resultados = []
                    for _, produto in df_produtos_sem.iterrows():
                        descricao = produto["descricao"]

                        if usar_fuzzy and FUZZYWUZZY_AVAILABLE:
                            nome_canonico = canonizador.encontrar_produto_por_similaridade(
                                descricao, threshold_fuzzy
                            )
                        else:
                            nome_canonico = canonizador.encontrar_produto_por_palavras_chave(
                                descricao
                            )

                        if not nome_canonico:
                            nome_canonico = canonizador.canonizar_descricao(descricao)

                        resultados.append(
                            {
                                "id_produto": produto["id_produto"],
                                "descricao": descricao,
                                "nome_canonico_novo": nome_canonico,
                            }
                        )

                    df_atualizar = pd.DataFrame(resultados)
                    sucesso, mensagem = atualizar_nome_canonico_batch(
                        df_atualizar
                    )

                    if sucesso:
                        st.success(f"✅ {mensagem}")
                        st.balloons()
                    else:
                        st.error(f"❌ {mensagem}")

                    st.subheader("📊 Amostra dos Resultados")
                    st.dataframe(
                        df_atualizar[["descricao", "nome_canonico_novo"]].head(50),
                        width="stretch",
                        hide_index=True,
                    )

    with tab3:
        st.subheader("🔍 Teste Individual de Canonização")

        descricao_teste = st.text_area(
            "Digite uma descrição de produto:",
            placeholder="Ex: LING CHURR SUPER FRANGO CBACON 800G 000 UN",
            height=100,
        )

        if descricao_teste:
            if st.button("🔍 Testar Canonização", use_container_width=True):
                with st.spinner("Processando..."):
                    res_palavras = canonizador.encontrar_produto_por_palavras_chave(
                        descricao_teste
                    )
                    res_sim = (
                        canonizador.encontrar_produto_por_similaridade(
                            descricao_teste, 70
                        )
                        if FUZZYWUZZY_AVAILABLE
                        else None
                    )
                    res_final = canonizador.canonizar_descricao(descricao_teste)

                st.markdown("#### Resultados")
                st.write(f"**Descrição original:** {descricao_teste}")
                st.write(f"**Método palavras-chave:** {res_palavras or 'Não encontrado'}")
                if res_sim:
                    st.write(f"**Método similaridade:** {res_sim}")
                st.success(f"**Resultado final:** {res_final}")

    with tab4:
        st.subheader("📋 Regras Personalizadas de Canonização")

        criar_tabela_canonizacao_regras()
        df_regras = carregar_regras_canonizacao()

        if not df_regras.empty:
            st.markdown("#### Regras Ativas")
            st.dataframe(df_regras, width="stretch", hide_index=True)

        st.markdown("#### Adicionar Nova Regra")

        col1, col2 = st.columns(2)
        with col1:
            tipo_regra = st.selectbox("Tipo de Regra:", ["contem", "regex", "exato"])
        with col2:
            padrao_regra = st.text_input(
                "Padrão reconhecido:", placeholder="Ex: arroz.*tipo.*1"
            )

        nome_canonico_regra = st.text_input(
            "Nome canônico a atribuir:", placeholder="Ex: ARROZ"
        )

        if st.button("💾 Salvar Regra", use_container_width=True):
            if padrao_regra and nome_canonico_regra:
                sucesso, mensagem = salvar_regra_canonizacao(
                    padrao_regra, nome_canonico_regra, tipo_regra
                )
                if sucesso:
                    st.success("✅ Regra salva com sucesso!")
                else:
                    st.error(f"❌ {mensagem}")
            else:
                st.warning("Preencha padrão e nome canônico.")

    with tab5:
        st.subheader("📈 Estatísticas do Sistema de Canonização")

        df_produtos = carregar_produtos_para_canonizacao()
        if df_produtos.empty:
            st.warning("Nenhum dado para análise.")
            return

        df_analise = canonizador.analisar_padroes_descricao(df_produtos)
        if df_analise.empty:
            st.info("Sem dados suficientes para análise.")
            return

        analise = df_analise.iloc[0]

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total de Produtos", int(analise["total_produtos"]))
            st.metric(
                "Produtos sem Canonizar", int(analise["produtos_sem_canonico"])
            )
        with col2:
            st.metric(
                "Tamanho Médio da Descrição",
                f"{analise['tamanho_medio_descricao']:.1f} caracteres",
            )

        if analise["palavras_frequentes"]:
            st.markdown("#### Palavras mais Frequentes")
            palavras_df = pd.DataFrame(
                analise["palavras_frequentes"], columns=["Palavra", "Frequência"]
            )
            st.dataframe(palavras_df, width="stretch", hide_index=True)

        if analise["sugestoes_regras"]:
            st.markdown("#### Sugestões de Regras")
            for sugestao in analise["sugestoes_regras"]:
                st.write(f"- {sugestao}")


def exibir_configuracoes_avancadas():
    st.header("⚙️ Configurações Avançadas")

    tab1, tab2, tab3 = st.tabs(["📚 Dicionários", "🛠️ Ferramentas", "⚡ Performance"])

    with tab1:
        st.subheader("📚 Dicionários de Referência")
        st.info("Visualize e ajuste os dicionários usados na canonização.")

        produtos_ref = list(PRODUTOS_REFERENCIA.keys())
        if not produtos_ref:
            st.warning("Nenhum dicionário em memória.")
        else:
            col1, _ = st.columns([3, 1])
            with col1:
                produto_sel = st.selectbox(
                    "Produto de referência:", options=produtos_ref
                )

            variacoes = PRODUTOS_REFERENCIA.get(produto_sel, [])
            st.write(f"**Variações atuais de '{produto_sel}':**")
            for v in variacoes:
                st.write(f"- {v}")

            st.markdown("#### Editar Variações (somente em memória)")
            novas_variacoes = st.text_area(
                "Variações (uma por linha):",
                value="\n".join(variacoes),
                height=150,
            )
            if st.button("💾 Atualizar Variações (sessão atual)", use_container_width=True):
                PRODUTOS_REFERENCIA[produto_sel] = [
                    v.strip()
                    for v in novas_variacoes.splitlines()
                    if v.strip()
                ]
                st.success(f"Variações para '{produto_sel}' atualizadas na sessão.")

            st.markdown("#### Adicionar Novo Produto (sessão)")
            coln1, coln2 = st.columns(2)
            with coln1:
                novo_produto = st.text_input("Nome do novo produto:")
            with coln2:
                variacoes_novo = st.text_area(
                    "Variações (uma por linha):", height=100
                )
            if st.button("➕ Adicionar Produto (sessão)", use_container_width=True):
                if novo_produto and variacoes_novo:
                    PRODUTOS_REFERENCIA[novo_produto.upper()] = [
                        v.strip()
                        for v in variacoes_novo.splitlines()
                        if v.strip()
                    ]
                    st.success(f"Produto '{novo_produto}' adicionado à sessão.")
                else:
                    st.warning("Informe nome e variações.")

    with tab2:
        st.subheader("🛠️ Ferramentas de Manutenção")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧹 Limpar Cache", use_container_width=True):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("Cache limpo com sucesso.")
        with col2:
            if st.button("📁 Exportar Configurações (placeholder)", use_container_width=True):
                st.info("Exportação de configurações pode ser implementada depois.")

        st.markdown("#### Backup do Sistema (placeholder)")
        if st.button("💾 Criar Backup (placeholder)", use_container_width=True):
            st.info("Rotina de backup pode ser integrada no futuro (Neon backups).")

    with tab3:
        st.subheader("⚡ Performance (conceitual)")

        st.info(
            "Essas opções são conceituais. A implementação real de TTL/tamanho de cache "
            "pode ser feita futuramente com redis/outros mecanismos."
        )

        st.slider("TTL do Cache (minutos):", 1, 60, 5)
        st.selectbox("Tamanho Máximo de Cache (conceitual):", ["100MB", "500MB", "1GB"])
        st.slider("Timeout de Consulta (segundos):", 5, 60, 30)
        st.number_input(
            "Limite de Resultados por Consulta (conceitual):",
            min_value=100,
            max_value=10000,
            value=1000,
            step=100,
        )

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Dashboard de Preços - Canonização de Produtos",
        layout="wide",
        page_icon="📊",
    )

    st.title("📊 Dashboard de Preços - Sistema de Canonização")
    st.caption("Análise avançada com agrupamento automático de produtos similares.")

    st.sidebar.title("🔧 Navegação")

    modo = st.sidebar.radio(
        "Selecione o módulo:",
        [
            "📈 Visão Geral Agrupada",
            "🔍 Análise por Produto",
            "🏪 Comparação de Mercados",
            "📆 Variação Mensal",
            "🔄 Sistema de Canonização",
            "⚙️ Configurações Avançadas",
        ],
    )

    st.sidebar.divider()
    st.sidebar.markdown("### Ações Rápidas")
    if st.sidebar.button("🔄 Atualizar Dados", use_container_width=True):
        st.cache_data.clear()
        st.success("Cache limpo! Os dados serão recarregados.")
        st.experimental_rerun()

    st.sidebar.divider()
    st.sidebar.markdown("### Status do Sistema")
    try:
        df_status = run_query(
            """
            SELECT 
                (SELECT COUNT(*) FROM produtos) as total_produtos,
                (SELECT COUNT(*) FROM produtos WHERE nome_canonico IS NOT NULL 
                 AND nome_canonico <> '') as produtos_canonizados,
                (SELECT COUNT(*) FROM historico_precos) as total_compras,
                (SELECT MAX(data_nota) FROM historico_precos) as ultima_compra
        """
        )
        if not df_status.empty:
            status = df_status.iloc[0]
            col_s1, col_s2 = st.sidebar.columns(2)
            with col_s1:
                st.metric("Produtos", int(status["total_produtos"]))
            with col_s2:
                st.metric("Canonizados", int(status["produtos_canonizados"]))
            st.sidebar.metric("Compras", int(status["total_compras"]))
            if status["ultima_compra"]:
                if not isinstance(status["ultima_compra"], datetime):
                    ultima = pd.to_datetime(status["ultima_compra"])
                else:
                    ultima = status["ultima_compra"]
                st.sidebar.caption(f"Última compra: {ultima.strftime('%d/%m/%Y')}")
    except Exception:
        st.sidebar.warning("Não foi possível carregar o status.")

    if modo == "📈 Visão Geral Agrupada":
        exibir_visao_geral_agrupada()
    elif modo == "🔍 Análise por Produto":
        exibir_analise_produto()
    elif modo == "🏪 Comparação de Mercados":
        exibir_comparacao_mercados()
    elif modo == "📆 Variação Mensal":
        exibir_variacao_mensal()
    elif modo == "🔄 Sistema de Canonização":
        exibir_sistema_canonizacao()
    elif modo == "⚙️ Configurações Avançadas":
        exibir_configuracoes_avancadas()


if __name__ == "__main__":
    main()

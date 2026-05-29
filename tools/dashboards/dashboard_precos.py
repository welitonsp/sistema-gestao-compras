# dashboard_precos.py
# Dashboard de preços com Streamlit ligado ao Neon (PostgreSQL)
#
# - Lê DATABASE_URL do .env
# - Protegido por senha simples (check_password)
# - Foca em:
#     • Visão geral: último preço por produto
#     • Histórico de um produto
#     • Tabela bruta
#
# Requisitos:
#   pip install streamlit psycopg2-binary pandas python-dotenv plotly

import os
from datetime import date
from typing import Optional

import psycopg2
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import plotly.express as px

# ---------------------------------------------------------------------
# CONFIGURAÇÃO INICIAL
# ---------------------------------------------------------------------

# Carrega .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error(
        "⚠️ DATABASE_URL não encontrada.\n\n"
        "Verifique o arquivo `.env` na raiz do projeto."
    )
    st.stop()


@st.cache_resource
def get_connection():
    """
    Abre e cacheia a conexão com o banco Neon usando DATABASE_URL.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        # Teste rápido da conexão
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        return conn
    except Exception as e:
        st.error(f"🔴 Erro ao conectar no banco de dados:\n\n{e}")
        st.stop()


def run_query(sql: str, params=None) -> pd.DataFrame:
    """
    Executa uma consulta SQL e retorna um DataFrame.
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Erro ao executar consulta SQL: {e}")
        st.code(sql)
        return pd.DataFrame()


def run_query_with_loading(
    sql: str, params=None, message: str = "Carregando dados..."
) -> pd.DataFrame:
    """
    Executa consulta SQL com spinner.
    """
    with st.spinner(message):
        return run_query(sql, params)


# ---------------------------------------------------------------------
# AUTENTICAÇÃO BÁSICA DO DASHBOARD
# ---------------------------------------------------------------------


def check_password() -> bool:

    """
    Protege o dashboard com uma senha forte definida em DASHBOARD_PASSWORD no st.secrets.
    Não existe mais fallback para senha padrão.
    """


    def password_entered():
        # Descobre a senha esperada
        try:
            expected_password = st.secrets["DASHBOARD_PASSWORD"]
        except Exception:
            st.error("Senha do dashboard não configurada. Defina DASHBOARD_PASSWORD em secrets.toml.")
            st.stop()

        if st.session_state.get("password") == expected_password:
            st.session_state["password_correct"] = True
            # Nunca guardamos a senha no estado
            if "password" in st.session_state:
                del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False


    if "password_correct" not in st.session_state:
        st.text_input(
            "Senha do Dashboard",
            type="password",
            on_change=password_entered,
            key="password",
        )
        return False

    if not st.session_state["password_correct"]:
        st.text_input(
            "Senha do Dashboard",
            type="password",
            on_change=password_entered,
            key="password",
        )
        st.error("Senha incorreta.")
        return False


    return True


# ---------------------------------------------------------------------
# FUNÇÕES DE CARREGAMENTO DE DADOS
# ---------------------------------------------------------------------


@st.cache_data(ttl=300)
def carregar_ultimos_precos() -> pd.DataFrame:
    """
    Carrega o último preço registrado de cada produto (pela data da nota).
    """
    sql = """
        WITH ultimos AS (
            SELECT
                h.id_produto,
                p.descricao,
                h.mercado,
                h.data_nota,
                h.preco_unitario,
                h.quantidade,
                h.preco_total,
                ROW_NUMBER() OVER (
                    PARTITION BY h.id_produto
                    ORDER BY h.data_nota DESC, h.id DESC
                ) AS rn
            FROM historico_precos h
            JOIN produtos p ON p.id_produto = h.id_produto
        )
        SELECT
            id_produto,
            descricao,
            mercado,
            data_nota,
            preco_unitario,
            quantidade,
            preco_total
        FROM ultimos
        WHERE rn = 1
        ORDER BY descricao;
    """
    df = run_query(sql)
    if not df.empty:
        df["data_nota"] = pd.to_datetime(df["data_nota"], errors="coerce")
        df["preco_unitario"] = pd.to_numeric(df["preco_unitario"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def carregar_lista_produtos() -> pd.DataFrame:
    """
    Lista de produtos com histórico.
    """
    sql = """
        SELECT DISTINCT
            p.id_produto,
            p.descricao
        FROM produtos p
        JOIN historico_precos h ON h.id_produto = p.id_produto
        ORDER BY p.descricao;
    """
    return run_query(sql)


@st.cache_data(ttl=300)
def carregar_historico_produto(id_produto: str) -> pd.DataFrame:
    """
    Histórico completo de preços de um produto (por id_produto).
    """
    sql = """
        SELECT
            h.data_nota,
            h.mercado,
            h.preco_unitario,
            h.quantidade,
            h.preco_total
        FROM historico_precos h
        WHERE h.id_produto = %s
        ORDER BY h.data_nota;
    """
    df = run_query(sql, (id_produto,))
    if not df.empty:
        df["data_nota"] = pd.to_datetime(df["data_nota"], errors="coerce")
        df["preco_unitario"] = pd.to_numeric(df["preco_unitario"], errors="coerce")
        df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce")
        df["preco_total"] = pd.to_numeric(df["preco_total"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def carregar_tabela_bruta(limit: int = 2000) -> pd.DataFrame:
    """
    Tabela bruta de histórico (limitada).
    """
    sql = """
        SELECT
            h.id,
            h.id_produto,
            p.descricao,
            h.mercado,
            h.data_nota,
            h.quantidade,
            h.preco_unitario,
            h.preco_total
        FROM historico_precos h
        JOIN produtos p ON p.id_produto = h.id_produto
        ORDER BY h.data_nota DESC, h.id DESC
        LIMIT %s;
    """
    return run_query(sql, (limit,))


# ---------------------------------------------------------------------
# FUNÇÕES DE VISUALIZAÇÃO
# ---------------------------------------------------------------------


def visao_geral():
    st.subheader("📌 Visão Geral - Último preço por produto")

    df = carregar_ultimos_precos()
    if df.empty:
        st.warning("Nenhum dado encontrado em historico_precos.")
        return

    # Filtros
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        mercados = sorted(df["mercado"].dropna().unique().tolist())
        filtro_mercado = st.multiselect(
            "Filtrar por mercado:",
            options=mercados,
            default=mercados,
        )

    with col_f2:
        preco_min = float(df["preco_unitario"].min()) if not df.empty else 0.0
        preco_max = float(df["preco_unitario"].max()) if not df.empty else 100.0
        faixa_preco = st.slider(
            "Faixa de preço (R$):",
            min_value=round(preco_min, 2),
            max_value=round(preco_max, 2),
            value=(round(preco_min, 2), round(preco_max, 2)),
        )

    # Aplica filtros
    df_filtrado = df.copy()
    if filtro_mercado:
        df_filtrado = df_filtrado[df_filtrado["mercado"].isin(filtro_mercado)]

    df_filtrado = df_filtrado[
        (df_filtrado["preco_unitario"] >= faixa_preco[0])
        & (df_filtrado["preco_unitario"] <= faixa_preco[1])
    ]

    # Métricas
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Produtos distintos", df_filtrado["id_produto"].nunique())
    with col_m2:
        st.metric("Mercados distintos", df_filtrado["mercado"].nunique())
    with col_m3:
        preco_medio = df_filtrado["preco_unitario"].mean()
        st.metric("Preço médio (amostra)", f"R$ {preco_medio:,.2f}")

    # Tabela
    st.markdown("### 📋 Últimos preços por produto")
    st.dataframe(
        df_filtrado.sort_values("descricao"),
        hide_index=True,
    )

    # Gráfico de distribuição
    st.markdown("### 📊 Distribuição dos preços unitários")
    fig = px.histogram(
        df_filtrado,
        x="preco_unitario",
        nbins=30,
        title="Distribuição dos últimos preços unitários",
        labels={"preco_unitario": "Preço unitário (R$)"},
    )
    st.plotly_chart(fig)

    # Exportação
    st.markdown("### 📥 Exportar amostra filtrada")
    csv = df_filtrado.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Baixar CSV",
        data=csv,
        file_name=f"ultimos_precos_{date.today()}.csv",
        mime="text/csv",
    )


def historico_produto():
    st.subheader("📈 Histórico de um produto")

    df_produtos = carregar_lista_produtos()
    if df_produtos.empty:
        st.warning("Não há produtos com histórico cadastrado.")
        return

    # Cria um dicionário id → descrição para o selectbox
    lista_ids = df_produtos["id_produto"].tolist()
    mapa_desc = {
        row["id_produto"]: row["descricao"] for _, row in df_produtos.iterrows()
    }

    def format_produto(id_produto: str) -> str:
        desc = mapa_desc.get(id_produto, id_produto)
        return f"{desc} ({id_produto})"

    id_selecionado = st.selectbox(
        "Selecione o produto:",
        options=lista_ids,
        format_func=format_produto,
    )

    if not id_selecionado:
        return

    df_hist = carregar_historico_produto(id_selecionado)
    if df_hist.empty:
        st.info("Nenhum histórico encontrado para este produto.")
        return

    # Métricas básicas
    preco_medio = df_hist["preco_unitario"].mean()
    preco_min = df_hist["preco_unitario"].min()
    preco_max = df_hist["preco_unitario"].max()

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Preço médio", f"R$ {preco_medio:,.2f}")
    with col_m2:
        st.metric("Menor preço", f"R$ {preco_min:,.2f}")
    with col_m3:
        st.metric("Maior preço", f"R$ {preco_max:,.2f}")

    # Abas: gráfico, estatísticas, tabela
    tab1, tab2, tab3 = st.tabs(["📈 Gráfico", "📊 Estatísticas", "📋 Tabela"])

    with tab1:
        fig = px.line(
            df_hist,
            x="data_nota",
            y="preco_unitario",
            color="mercado",
            markers=True,
            title="Evolução do preço por mercado",
            labels={"data_nota": "Data", "preco_unitario": "Preço unitário (R$)"},
        )
        st.plotly_chart(fig)

    with tab2:
        st.write("Quantidade de registros:", len(df_hist))
        st.write("Período:",
                 df_hist["data_nota"].min().date(),
                 "→",
                 df_hist["data_nota"].max().date())

        # Preço médio por mercado
        df_mercado = (
            df_hist.groupby("mercado")["preco_unitario"]
            .agg(["count", "mean", "min", "max"])
            .reset_index()
        )
        df_mercado.rename(
            columns={
                "mercado": "Mercado",
                "count": "Qtde registros",
                "mean": "Preço médio",
                "min": "Mínimo",
                "max": "Máximo",
            },
            inplace=True,
        )
        st.dataframe(df_mercado, hide_index=True)

    with tab3:
        st.dataframe(
            df_hist.sort_values("data_nota", ascending=False),
            hide_index=True,
        )

        csv = df_hist.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Baixar histórico em CSV",
            data=csv,
            file_name=f"historico_{id_selecionado}_{date.today()}.csv",
            mime="text/csv",
        )


def tabela_bruta():
    st.subheader("📋 Tabela bruta (amostra)")

    limite = st.slider(
        "Limite de registros (para não ficar pesado):",
        min_value=100,
        max_value=10000,
        value=2000,
        step=100,
    )

    df = carregar_tabela_bruta(limit=limite)
    if df.empty:
        st.warning("Nenhum registro encontrado em historico_precos.")
        return

    st.dataframe(
        df,
        hide_index=True,
    )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Baixar CSV (amostra)",
        data=csv,
        file_name=f"historico_bruto_{date.today()}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------
# APLICAÇÃO PRINCIPAL
# ---------------------------------------------------------------------


def main():
    st.set_page_config(
        page_title="Dashboard de Preços - Gestão de Compras",
        layout="wide",
        page_icon="📊",
    )

    st.title("📊 Dashboard de Preços - Gestão de Compras")
    st.caption("Análise de notas fiscais com banco Neon (PostgreSQL).")

    # Autenticação simples
    if not check_password():
        st.stop()

    # Sidebar
    st.sidebar.title("📌 Navegação")
    modo = st.sidebar.radio(
        "Selecione o modo:",
        ["Visão Geral", "Histórico de Produto", "Tabela Bruta"],
    )

    st.sidebar.divider()
    if st.sidebar.button("🔄 Recarregar dados"):
        st.cache_data.clear()
        st.success("Cache limpo. Os dados serão recarregados.")
        st.experimental_rerun()

    # Status rápido
    st.sidebar.divider()
    st.sidebar.caption("📊 Status do banco")
    try:
        df_status = run_query(
            """
            SELECT
                (SELECT COUNT(*) FROM produtos) AS total_produtos,
                (SELECT COUNT(*) FROM historico_precos) AS total_registros
        """
        )
        if not df_status.empty:
            row = df_status.iloc[0]
            st.sidebar.metric("Produtos", int(row["total_produtos"]))
            st.sidebar.metric("Registros", int(row["total_registros"]))
    except Exception:
        st.sidebar.write("Não foi possível carregar o status.")

    # Conteúdo principal
    if modo == "Visão Geral":
        visao_geral()
    elif modo == "Histórico de Produto":
        historico_produto()
    elif modo == "Tabela Bruta":
        tabela_bruta()


if __name__ == "__main__":
    main()

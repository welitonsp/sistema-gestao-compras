# core/config.py
# ==========================================================
# CONFIGURAÇÕES CENTRAIS DO SISTEMA GESTAOCOMPRAS
# ==========================================================
# Este arquivo centraliza:
# - Variáveis de ambiente (.env)
# - Configurações de banco
# - Configurações de IA (Groq / Gemini)
# - Constantes globais
#
# Pensado para facilitar manutenção e aprendizado.
# ==========================================================

import os
from dotenv import load_dotenv

# ----------------------------------------------------------
# CARREGAMENTO DO .env
# ----------------------------------------------------------

# Carrega o arquivo .env da raiz do projeto
load_dotenv()


# ----------------------------------------------------------
# BANCO DE DADOS
# ----------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não definida. "
        "Configure corretamente no arquivo .env."
    )

# Nomes das tabelas (centralizados para evitar erro de digitação)
TABELA_PRODUTOS = "produtos"
TABELA_HISTORICO_PRECOS = "historico_precos"


# ----------------------------------------------------------
# GROQ (IA OPERACIONAL)
# ----------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# A IA Groq é usada para:
# - Classificação em massa
# - Processamento rápido
# - Execuções automáticas

if not GROQ_API_KEY:
    print(
        "⚠️ AVISO: GROQ_API_KEY não encontrada no .env. "
        "Funções de IA Groq não irão funcionar."
    )


# ----------------------------------------------------------
# GEMINI (IA COGNITIVA)
# ----------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# A IA Gemini é usada para:
# - Insights
# - Auditoria
# - Consultas em linguagem natural
# - Explicações

if not GEMINI_API_KEY:
    print(
        "⚠️ AVISO: GEMINI_API_KEY não encontrada no .env. "
        "Funções de IA Gemini não irão funcionar."
    )


# ----------------------------------------------------------
# CONFIGURAÇÕES GERAIS DO SISTEMA
# ----------------------------------------------------------

# Quantidade padrão de registros para auditoria
AUDITORIA_AMOSTRA_PADRAO = 25

# Limite padrão de resultados em consultas automáticas
LIMITE_RESULTADOS_PADRAO = 100

# Modo debug (pode ser usado no futuro)
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


# ----------------------------------------------------------
# FUNÇÃO DE DIAGNÓSTICO (OPCIONAL)
# ----------------------------------------------------------

def resumo_configuracoes():
    """
    Retorna um resumo simples das configurações carregadas.
    Útil para debug e aprendizado.
    """
    return {
        "DATABASE_URL_configurada": bool(DATABASE_URL),
        "GROQ_configurado": bool(GROQ_API_KEY),
        "GEMINI_configurado": bool(GEMINI_API_KEY),
        "DEBUG": DEBUG,
        "GROQ_MODEL": GROQ_MODEL,
        "GEMINI_MODEL": GEMINI_MODEL,
    }

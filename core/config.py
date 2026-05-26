# core/config.py
# ==========================================================
# CONFIGURAÇÕES CENTRAIS DO SISTEMA GESTAOCOMPRAS
# ==========================================================

import os
from dotenv import load_dotenv
from dataclasses import dataclass

# ----------------------------------------------------------
# CARREGAMENTO DO .env
# ----------------------------------------------------------

load_dotenv()

# ----------------------------------------------------------
# FLAG GLOBAL DE DEBUG
# ----------------------------------------------------------

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ----------------------------------------------------------
# BANCO DE DADOS
# ----------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não definida no .env")

TABELA_PRODUTOS = "produtos"
TABELA_HISTORICO_PRECOS = "historico_precos"

# AI CONFIG (CONTROL)
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq")
ENABLE_GEMINI = os.getenv("ENABLE_GEMINI", "false").lower() == "true"

# ----------------------------------------------------------
# GROQ (IA OPERACIONAL)
# ----------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# ----------------------------------------------------------
# GEMINI (IA COGNITIVA)
# ----------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ----------------------------------------------------------
# OBJETO DE CONFIGURAÇÃO (ÚTIL PARA TESTES)
# ----------------------------------------------------------

@dataclass
class Settings:
    database_url: str
    groq_api_key: str | None
    gemini_api_key: str | None
    groq_model: str
    gemini_model: str
    debug: bool
    ai_provider: str
    enable_gemini: bool


def get_settings() -> Settings:
    return Settings(
        database_url=DATABASE_URL,
        groq_api_key=GROQ_API_KEY,
        gemini_api_key=GEMINI_API_KEY,
        groq_model=GROQ_MODEL,
        gemini_model=GEMINI_MODEL,
        debug=DEBUG,
        ai_provider=AI_PROVIDER,
        enable_gemini=ENABLE_GEMINI,
    )

settings = get_settings()

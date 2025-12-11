# config.py
# Centraliza leitura do .env e exposição das configurações do sistema.

import os
from dataclasses import dataclass
from typing import Dict


_ENV_CACHE: Dict[str, str] | None = None


def _load_env(path: str = ".env") -> Dict[str, str]:
    """
    Lê o arquivo .env manualmente e devolve um dicionário {chave: valor}.
    Ignora linhas vazias e comentários começando com '#'.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Arquivo {path} não encontrado. "
            "Certifique-se de que o .env está na pasta C:\\GestaoCompras."
        )

    env: Dict[str, str] = {}

    with open(path, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            if "=" not in linha:
                continue

            chave, valor = linha.split("=", 1)
            chave = chave.strip()
            # remove aspas simples ou duplas ao redor do valor
            valor_limpo = valor.strip().strip('"').strip("'")
            env[chave] = valor_limpo

    return env


@dataclass(slots=True)
class Settings:
    gemini_api_key: str
    database_url: str


def get_settings() -> Settings:
    """
    Retorna um objeto Settings com as configurações lidas do .env.
    Usa cache em memória para não reler o arquivo toda hora.
    """
    global _ENV_CACHE
    if _ENV_CACHE is None:
        _ENV_CACHE = _load_env()

    gemini_api_key = _ENV_CACHE.get("GEMINI_API_KEY")
    database_url = _ENV_CACHE.get("DATABASE_URL")

    if not gemini_api_key:
        raise RuntimeError("A chave GEMINI_API_KEY não foi encontrada no .env.")

    if not database_url:
        raise RuntimeError("A variável DATABASE_URL não foi encontrada no .env.")

    return Settings(
        gemini_api_key=gemini_api_key,
        database_url=database_url,
    )

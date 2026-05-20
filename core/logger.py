# core/logger.py
# ==========================================================
# LOG ESTRUTURADO E OBSERVABILIDADE (MODERNO)
# ==========================================================

import logging
import os
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
from core.config import settings

# ----------------------------------------------------------
# CONFIGURAÇÕES
# ----------------------------------------------------------

LOG_DIR = "logs"
LOG_FILE = "gestaocompras_structured.log"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, LOG_FILE)

LOG_LEVEL = logging.DEBUG if settings.debug else logging.INFO

import re

# ----------------------------------------------------------
# SANITIZAÇÃO DE DADOS SENSÍVEIS
# ----------------------------------------------------------

class SensitiveDataFilter(logging.Filter):
    """Oculta dados sensíveis como chaves de acesso (44 dígitos) e CNPJs."""
    
    # Regex para chaves de acesso (44 dígitos consecutivos)
    CHAVE_PATTERN = re.compile(r"\b\d{44}\b")
    # Regex para CNPJ (XX.XXX.XXX/XXXX-XX ou XXXXXXXXXXXXXX)
    CNPJ_PATTERN = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")

    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)
        
        if hasattr(record, "context") and isinstance(record.context, dict):
            # Sanitiza o contexto injetado pelo ContextAdapter
            new_context = {}
            for k, v in record.context.items():
                if isinstance(v, str):
                    new_context[k] = self._sanitize(v)
                else:
                    new_context[k] = v
            record.context = new_context
            
        return True

    def _sanitize(self, text: str) -> str:
        # Mascara chave: mantém 4 primeiros e 4 últimos
        text = self.CHAVE_PATTERN.sub(lambda m: f"{m.group()[:4]}...{m.group()[-4:]}", text)
        # Mascara CNPJ: mantém 2 primeiros e 2 últimos
        text = self.CNPJ_PATTERN.sub(lambda m: f"{m.group()[:2]}...{m.group()[-2:]}", text)
        return text

class StructuredFormatter(logging.Formatter):
    """Gera logs em formato que facilita ingestão por ELK/CloudWatch."""
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName
        }
        if hasattr(record, "context"):
            log_record["context"] = record.context
        
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record, ensure_ascii=False)

def _init_logger():
    root = logging.getLogger("gestaocompras")
    if root.handlers:
        return

    root.setLevel(LOG_LEVEL)
    root.propagate = False # Evita duplicidade com o root do python

    # Console Handler (Formatado para humanos)
    human_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    console = logging.StreamHandler()
    console.setFormatter(human_formatter)
    console.addFilter(SensitiveDataFilter())
    
    # File Handler (Estruturado para Máquinas)
    file_handler = RotatingFileHandler(
        LOG_PATH, maxBytes=5_000_000, backupCount=10, encoding="utf-8"
    )
    file_handler.setFormatter(StructuredFormatter())
    file_handler.addFilter(SensitiveDataFilter())

    root.addHandler(console)
    root.addHandler(file_handler)

_init_logger()

# ----------------------------------------------------------
# FUNÇÕES PÚBLICAS
# ----------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado com o prefixo do projeto."""
    return logging.getLogger(f"gestaocompras.{name}")

class ContextAdapter(logging.LoggerAdapter):
    """Permite injetar metadados (ex: chave_nota) em todos os logs de uma sessão."""
    def process(self, msg, kwargs):
        context = kwargs.pop("context", self.extra or {})
        kwargs["extra"] = {"context": context}
        return msg, kwargs

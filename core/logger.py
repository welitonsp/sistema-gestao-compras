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
    
    # File Handler (Estruturado para Máquinas)
    file_handler = RotatingFileHandler(
        LOG_PATH, maxBytes=5_000_000, backupCount=10, encoding="utf-8"
    )
    file_handler.setFormatter(StructuredFormatter())

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

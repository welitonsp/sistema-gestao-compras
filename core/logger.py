# core/logger.py
# ==========================================================
# LOG CENTRALIZADO DO SISTEMA GESTAOCOMPRAS
# ==========================================================

import logging
import os
from logging.handlers import RotatingFileHandler
from core.config import DEBUG

# ----------------------------------------------------------
# CONFIGURAÇÕES
# ----------------------------------------------------------

LOG_DIR = "logs"
LOG_FILE = "gestaocompras.log"

os.makedirs(LOG_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOG_DIR, LOG_FILE)

LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO

# ----------------------------------------------------------
# INICIALIZA LOGGER GLOBAL (UMA VEZ)
# ----------------------------------------------------------

def _init_logger():
    root = logging.getLogger()

    if root.handlers:
        return

    root.setLevel(LOG_LEVEL)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(LOG_LEVEL)

    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(LOG_LEVEL)

    root.addHandler(console_handler)
    root.addHandler(file_handler)


_init_logger()

# ----------------------------------------------------------
# FUNÇÃO PÚBLICA
# ----------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

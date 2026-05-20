# logger_config.py
# Configuração central de logging para o sistema de Gestão de Compras.

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str = "gestaocompras",
    log_file: str = "gestaocompras.log",
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Cria (ou reutiliza) um logger com:
      - saída para arquivo em logs/gestaocompras.log (rotacionado)
      - saída para console (terminal)

    Uso:
        from logger_config import setup_logger
        logger = setup_logger("xml_processor")
        logger.info("Mensagem")
    """
    logger = logging.getLogger(name)

    # Se já tiver handlers configurados, apenas retorna
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Pasta de logs
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", log_file)

    # Handler de arquivo com rotação
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,   # ~1MB
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # Handler de console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

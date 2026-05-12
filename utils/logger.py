"""
utils/logger.py
---------------
Configure le logger centralisé pour tout le pipeline ETL.
  - Écrit dans logs/etl_YYYYMMDD_HHMMSS.log
  - Affiche aussi dans la console
  - Fournit get_logger() utilisé par tous les modules
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from config.settings import LOG_DIR

# Crée le répertoire logs s'il n'existe pas
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Nom du fichier de log horodaté
_log_file = LOG_DIR / f"etl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Format des messages
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """
    Initialise le logging global.
    À appeler UNE SEULE FOIS depuis main.py.
    """
    logging.basicConfig(
        level=level,
        format=_FORMAT,
        datefmt=_DATE_FMT,
        handlers=[
            logging.FileHandler(_log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Réduire le bruit de sqlalchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Retourne un logger nommé pour un module donné.

    Usage :
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("message")
    """
    return logging.getLogger(name)

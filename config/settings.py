"""
config/settings.py
------------------
Centralise tous les paramètres du pipeline ETL Mexora :
  - Chemins des fichiers sources
  - Paramètres de connexion PostgreSQL
  - Constantes métier (seuils de segmentation, périodes Ramadan, etc.)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# CHARGEMENT DU FICHIER .env
# ──────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent   # racine mexora_etl/
load_dotenv(BASE_DIR / ".env")   # charge .env en variables d'environnement
DATA_DIR  = BASE_DIR / "data"
LOG_DIR   = BASE_DIR / "logs"

# Sources
COMMANDES_FILE = DATA_DIR / "commandes_mexora.csv"
PRODUITS_FILE  = DATA_DIR / "produits_mexora.json"
CLIENTS_FILE   = DATA_DIR / "clients_mexora.csv"
REGIONS_FILE   = DATA_DIR / "regions_maroc.csv"

# ──────────────────────────────────────────────
# CONNEXION POSTGRESQL
# Les valeurs peuvent être surchargées via variables d'environnement
# ──────────────────────────────────────────────
DB_HOST   = os.getenv("DB_HOST",   "localhost")
DB_PORT   = os.getenv("DB_PORT",   "5432")
DB_NAME   = os.getenv("DB_NAME",   "mexora_dwh")
DB_USER   = os.getenv("DB_USER",   "postgres")
DB_PASS   = os.getenv("DB_PASS",   "postgres")
DB_SCHEMA = "dwh_mexora"

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ──────────────────────────────────────────────
# CONSTANTES MÉTIER
# ──────────────────────────────────────────────

# Segmentation clients (CA 12 mois glissants, en MAD)
SEGMENT_GOLD   = 15_000
SEGMENT_SILVER =  5_000

# Plage de la dimension temporelle
DIM_TEMPS_START = "2020-01-01"
DIM_TEMPS_END   = "2025-12-31"

# Jours fériés marocains (à compléter selon les années)
FERIES_MAROC = [
    "2020-01-01", "2020-01-11", "2020-05-01", "2020-07-30",
    "2020-08-14", "2020-08-20", "2020-08-21", "2020-11-06", "2020-11-18",
    "2021-01-01", "2021-01-11", "2021-05-01", "2021-07-30",
    "2021-08-14", "2021-08-20", "2021-08-21", "2021-11-06", "2021-11-18",
    "2022-01-01", "2022-01-11", "2022-05-01", "2022-07-30",
    "2022-08-14", "2022-08-20", "2022-08-21", "2022-11-06", "2022-11-18",
    "2023-01-01", "2023-01-11", "2023-05-01", "2023-07-30",
    "2023-08-14", "2023-08-20", "2023-08-21", "2023-11-06", "2023-11-18",
    "2024-01-01", "2024-01-11", "2024-05-01", "2024-07-30",
    "2024-08-14", "2024-08-20", "2024-08-21", "2024-11-06", "2024-11-18",
    "2025-01-01", "2025-01-11", "2025-05-01", "2025-07-30",
    "2025-08-14", "2025-08-20", "2025-08-21", "2025-11-06", "2025-11-18",
]

# Périodes Ramadan (début, fin)
RAMADAN_PERIODES = [
    ("2020-04-23", "2020-05-23"),
    ("2021-04-12", "2021-05-12"),
    ("2022-04-02", "2022-05-01"),
    ("2023-03-22", "2023-04-20"),
    ("2024-03-10", "2024-04-09"),
    ("2025-03-01", "2025-03-29"),
]

# Mapping de standardisation des statuts de commande
STATUTS_MAPPING = {
    "livré":    "livré",  "livre":   "livré",  "LIVRE":   "livré",
    "DONE":     "livré",  "done":    "livré",
    "annulé":   "annulé", "annule":  "annulé", "ANNULE":  "annulé",
    "KO":       "annulé", "ko":      "annulé",
    "en_cours": "en_cours", "OK":    "en_cours", "ok":    "en_cours",
    "retourné": "retourné", "retourne": "retourné", "RETOURNE": "retourné",
}

STATUTS_VALIDES = {"livré", "annulé", "en_cours", "retourné"}

# Mapping standardisation du sexe
SEXE_MAPPING = {
    "m": "m", "M": "m", "male": "m", "Male": "m", "MALE": "m",
    "h": "m", "H": "m", "homme": "m", "Homme": "m", "HOMME": "m",
    "1": "m",
    "f": "f", "F": "f", "female": "f", "Female": "f", "FEMALE": "f",
    "femme": "f", "Femme": "f", "FEMME": "f",
    "0": "f",
}

# Âge minimum et maximum acceptés pour les clients
AGE_MIN = 16
AGE_MAX = 100

# Taux de TVA Maroc
TVA_TAUX = 0.20

# Chunksize pour les insertions SQL
SQL_CHUNKSIZE = 1000

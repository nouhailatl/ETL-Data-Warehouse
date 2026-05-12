"""
load/loader.py
--------------
Phase LOAD du pipeline ETL Mexora.
Charge les dimensions et la table de faits dans PostgreSQL.

Stratégies :
  - Dimensions  : REPLACE (truncate + reload complet)
  - Fait        : UPSERT  (insert + update sur conflit id_vente)

En l'absence de PostgreSQL (mode dev/test), exporte en CSV.
"""

import pandas as pd
from datetime import datetime
from pathlib import Path

from utils.logger import get_logger
from config.settings import DB_SCHEMA, SQL_CHUNKSIZE, BASE_DIR

logger = get_logger(__name__)

# Répertoire de sortie CSV (mode fallback)
CSV_OUTPUT_DIR = BASE_DIR / "output_csv"


def get_engine():
    """
    Crée et retourne un moteur SQLAlchemy vers PostgreSQL.
    Lève une exception claire si la connexion échoue.
    """
    try:
        from sqlalchemy import create_engine, text
        from config.settings import DATABASE_URL
        engine = create_engine(DATABASE_URL, echo=False)
        # Test de connexion
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"[LOAD] Connexion PostgreSQL OK → {DATABASE_URL.split('@')[-1]}")
        return engine
    except Exception as e:
        logger.error(f"[LOAD] Impossible de se connecter à PostgreSQL : {e}")
        raise


def charger_dimension(
    df:         pd.DataFrame,
    table_name: str,
    engine,
    schema:     str = DB_SCHEMA,
) -> None:
    """
    Charge une table de dimension dans PostgreSQL.
    Stratégie : replace (truncate + reload complet).

    Parameters
    ----------
    df         : DataFrame de la dimension nettoyée
    table_name : nom de la table (ex: 'dim_temps')
    engine     : moteur SQLAlchemy
    schema     : schéma PostgreSQL cible
    """
    logger.info(f"[LOAD] Chargement {schema}.{table_name} ({len(df):,} lignes) ...")
    try:
        df.to_sql(
            name      = table_name,
            con       = engine,
            schema    = schema,
            if_exists = "replace",   # truncate + reload
            index     = False,
            method    = "multi",
            chunksize = SQL_CHUNKSIZE,
        )
        logger.info(f"[LOAD] ✅ {schema}.{table_name} : {len(df):,} lignes chargées")
    except Exception as e:
        logger.error(f"[LOAD] ❌ Erreur sur {table_name} : {e}")
        raise


def charger_faits(df: pd.DataFrame, engine, schema: str = DB_SCHEMA) -> None:
    """
    Charge la table de faits avec une stratégie UPSERT.
    Utilise ON CONFLICT DO UPDATE sur id_vente.

    Parameters
    ----------
    df     : DataFrame FAIT_VENTES
    engine : moteur SQLAlchemy
    schema : schéma PostgreSQL cible
    """
    from sqlalchemy import Table, MetaData
    from sqlalchemy.dialects.postgresql import insert

    table_name = "fait_ventes"
    logger.info(f"[LOAD] UPSERT {schema}.{table_name} ({len(df):,} lignes) ...")

    try:
        meta = MetaData()
        meta.reflect(bind=engine, schema=schema, only=[table_name])
        tbl = meta.tables[f"{schema}.{table_name}"]

        with engine.connect() as conn:
            chunks = [df.iloc[i:i+5000] for i in range(0, len(df), 5000)]
            for chunk_num, chunk in enumerate(chunks, 1):
                records = chunk.to_dict("records")
                stmt = insert(tbl).values(records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id_vente"],
                    set_={c.key: c for c in stmt.excluded if c.key != "id_vente"},
                )
                conn.execute(stmt)
                conn.commit()
                logger.info(
                    f"[LOAD] {table_name} chunk {chunk_num}/{len(chunks)} "
                    f"({len(chunk):,} lignes)"
                )
        logger.info(f"[LOAD] ✅ {schema}.{table_name} : {len(df):,} lignes chargées (upsert)")

    except Exception as e:
        logger.error(f"[LOAD] ❌ Erreur UPSERT {table_name} : {e}")
        raise


# ══════════════════════════════════════════════
# MODE FALLBACK — Export CSV (sans PostgreSQL)
# ══════════════════════════════════════════════

def exporter_csv(df: pd.DataFrame, table_name: str) -> Path:
    """
    Exporte un DataFrame en CSV dans le répertoire output_csv/.
    Utilisé en mode développement quand PostgreSQL n'est pas disponible.

    Returns
    -------
    Path du fichier créé
    """
    CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CSV_OUTPUT_DIR / f"{table_name}.csv"
    df.to_csv(filepath, index=False, encoding="utf-8")
    logger.info(f"[LOAD-CSV] ✅ {filepath} — {len(df):,} lignes")
    return filepath


def charger_tout_csv(dimensions: dict, fait: pd.DataFrame) -> None:
    """
    Exporte toutes les dimensions et la table de faits en CSV.

    Parameters
    ----------
    dimensions : dict { 'dim_temps': df, 'dim_client': df, ... }
    fait       : DataFrame FAIT_VENTES
    """
    logger.info("[LOAD-CSV] Mode fallback CSV activé")
    for table_name, df in dimensions.items():
        exporter_csv(df, table_name)
    exporter_csv(fait, "fait_ventes")
    logger.info(f"[LOAD-CSV] Tous les fichiers exportés dans : {CSV_OUTPUT_DIR}")

"""
main.py
-------
Point d'entrée du pipeline ETL Mexora.
Orchestre les phases Extract → Transform → Load.

Usage :
    # Mode PostgreSQL (production)
    python main.py

    # Mode CSV fallback (développement / sans PostgreSQL)
    python main.py --csv

    # Tester uniquement Extract + Transform (sans charger)
    python main.py --dry-run
"""

import sys
import argparse
from datetime import datetime

# ── Setup logging EN PREMIER (avant tous les imports ETL) ──────────────
from utils.logger import setup_logging, get_logger
setup_logging()
logger = get_logger("main")

# ── Imports ETL ────────────────────────────────────────────────────────
from extract.extractor import (
    extract_commandes,
    extract_produits,
    extract_clients,
    extract_regions,
)
from transform.clean_commandes  import transform_commandes
from transform.clean_clients    import transform_clients
from transform.clean_produits   import transform_produits
from transform.build_dimensions import (
    build_dim_temps,
    build_dim_produit,
    build_dim_region,
    build_dim_client,
    build_dim_livreur,
    build_fait_ventes,
)
from load.loader import (
    get_engine,
    charger_dimension,
    charger_faits,
    charger_tout_csv,
)


# ══════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ══════════════════════════════════════════════

def run_pipeline(use_csv: bool = False, dry_run: bool = False) -> None:
    """
    Exécute le pipeline ETL complet :
      1. EXTRACT  — lecture des fichiers sources bruts
      2. TRANSFORM — nettoyage, standardisation, construction des dimensions
      3. LOAD     — chargement dans PostgreSQL (ou export CSV si use_csv=True)

    Parameters
    ----------
    use_csv  : si True, exporte en CSV au lieu de charger dans PostgreSQL
    dry_run  : si True, exécute Extract + Transform uniquement (pas de Load)
    """
    start = datetime.now()
    logger.info("=" * 65)
    logger.info("  DÉMARRAGE PIPELINE ETL MEXORA")
    logger.info(f"  Mode : {'CSV' if use_csv else 'PostgreSQL'} | "
                f"Dry-run : {dry_run}")
    logger.info("=" * 65)

    try:
        # ──────────────────────────────────────────
        # PHASE 1 — EXTRACT
        # ──────────────────────────────────────────
        logger.info("")
        logger.info("─── PHASE 1 : EXTRACT ───────────────────────────────")

        df_commandes_raw = extract_commandes()
        df_produits_raw  = extract_produits()
        df_clients_raw   = extract_clients()
        df_regions_raw   = extract_regions()

        logger.info(
            f"[EXTRACT] Bilan : "
            f"{len(df_commandes_raw):,} commandes | "
            f"{len(df_produits_raw):,} produits | "
            f"{len(df_clients_raw):,} clients | "
            f"{len(df_regions_raw):,} régions"
        )

        # ──────────────────────────────────────────
        # PHASE 2 — TRANSFORM
        # ──────────────────────────────────────────
        logger.info("")
        logger.info("─── PHASE 2 : TRANSFORM ─────────────────────────────")

        # 2a. Nettoyage des sources
        logger.info("[TRANSFORM] Nettoyage commandes ...")
        df_commandes = transform_commandes(df_commandes_raw, df_regions_raw)

        logger.info("[TRANSFORM] Nettoyage clients ...")
        df_clients = transform_clients(df_clients_raw, df_regions_raw)

        logger.info("[TRANSFORM] Nettoyage produits ...")
        df_produits = transform_produits(df_produits_raw)

        # 2b. Construction des dimensions
        logger.info("[TRANSFORM] Construction des dimensions ...")

        dim_temps   = build_dim_temps()
        dim_produit = build_dim_produit(df_produits)
        dim_region  = build_dim_region(df_regions_raw)
        dim_client  = build_dim_client(df_clients, df_commandes)
        dim_livreur = build_dim_livreur(df_commandes)

        # 2c. Construction de la table de faits
        logger.info("[TRANSFORM] Construction FAIT_VENTES ...")
        fait_ventes = build_fait_ventes(
            df_commandes,
            dim_temps,
            dim_client,
            dim_produit,
            dim_region,
            dim_livreur,
        )

        # Bilan Transform
        logger.info("")
        logger.info("[TRANSFORM] ─── Bilan dimensions ───────────────────")
        logger.info(f"  dim_temps   : {len(dim_temps):,} jours")
        logger.info(f"  dim_produit : {len(dim_produit):,} produits")
        logger.info(f"  dim_region  : {len(dim_region):,} régions")
        logger.info(f"  dim_client  : {len(dim_client):,} clients")
        logger.info(f"  dim_livreur : {len(dim_livreur):,} livreurs")
        logger.info(f"  fait_ventes : {len(fait_ventes):,} lignes")
        logger.info(
            f"  CA total TTC : {fait_ventes['montant_ttc'].sum():,.0f} MAD"
        )

        if dry_run:
            logger.info("")
            logger.info("─── DRY-RUN : chargement ignoré ─────────────────────")
            logger.info("✅ Extract + Transform terminés avec succès")
            _print_summary(start)
            return

        # ──────────────────────────────────────────
        # PHASE 3 — LOAD
        # ──────────────────────────────────────────
        logger.info("")
        logger.info("─── PHASE 3 : LOAD ──────────────────────────────────")

        dimensions = {
            "dim_temps":   dim_temps,
            "dim_produit": dim_produit,
            "dim_region":  dim_region,
            "dim_client":  dim_client,
            "dim_livreur": dim_livreur,
        }

        if use_csv:
            # ── Mode CSV (dev / test) ──────────────────────────────────
            charger_tout_csv(dimensions, fait_ventes)
        else:
            # ── Mode PostgreSQL (production) ───────────────────────────
            engine = get_engine()
            for table_name, df in dimensions.items():
                charger_dimension(df, table_name, engine)
            charger_faits(fait_ventes, engine)

        logger.info("")
        logger.info("✅ Pipeline ETL terminé avec succès")
        _print_summary(start)

    except Exception as e:
        logger.error("")
        logger.error(f"❌ ERREUR PIPELINE : {e}", exc_info=True)
        logger.error("Pipeline interrompu.")
        sys.exit(1)


def _print_summary(start: datetime) -> None:
    duree = (datetime.now() - start).total_seconds()
    logger.info("")
    logger.info("=" * 65)
    logger.info(f"  Durée totale : {duree:.1f} secondes")
    logger.info("=" * 65)


# ══════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline ETL Mexora — chargement du Data Warehouse"
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Exporter en CSV au lieu de charger dans PostgreSQL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Exécuter uniquement Extract + Transform (sans chargement)",
    )
    args = parser.parse_args()
    run_pipeline(use_csv=args.csv, dry_run=args.dry_run)

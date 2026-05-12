"""
transform/clean_commandes.py
-----------------------------
Nettoyage et standardisation du fichier commandes_mexora.csv.

Règles appliquées :
  R1  Suppression des doublons sur id_commande (dernière occurrence)
  R2  Standardisation des dates au format YYYY-MM-DD
  R3  Harmonisation des villes via le référentiel régions_maroc
  R4  Standardisation des statuts de commande
  R5  Suppression des lignes avec quantite <= 0
  R6  Suppression des lignes avec prix_unitaire = 0 (commandes test)
  R7  Remplacement des id_livreur manquants par '-1'
  R8  Calcul du montant_ttc et montant_ht
"""

import re
import pandas as pd
from datetime import datetime

from utils.logger import get_logger
from config.settings import STATUTS_MAPPING, STATUTS_VALIDES, TVA_TAUX

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _build_ville_mapping(df_regions: pd.DataFrame) -> dict:
    """
    Construit un dictionnaire {alias_brut_lowercase → nom_standard}
    à partir du référentiel régions_maroc.

    On génère des variantes automatiques :
      - nom standard en minuscules
      - code_ville en minuscules
      - premières lettres, abbréviations communes
    """
    mapping = {}
    for _, row in df_regions.iterrows():
        std  = row["nom_ville_standard"]
        code = row["code_ville"].lower()

        # Variantes générées automatiquement
        aliases = [
            std.lower(),
            code,
            std.upper().lower(),
            std.replace("è","e").replace("é","e").replace("â","a")
               .replace("ê","e").replace("î","i").replace("ô","o")
               .replace("û","u").lower(),
        ]
        for alias in aliases:
            mapping[alias.strip()] = std

    # Aliases manuels pour les cas problématiques détectés dans les données
    manual = {
        "tnja": "Tanger", "tng": "Tanger", "tanger-ville": "Tanger",
        "tanger-med": "Tanger",
        "casa": "Casablanca", "cas": "Casablanca",
        "casablanca-anfa": "Casablanca", "casablanca-centre": "Casablanca",
        "rbat": "Rabat", "rba": "Rabat",
        "marrakesh": "Marrakech", "mrakech": "Marrakech", "mrk": "Marrakech",
        "fez": "Fès", "fes": "Fès",
        "agdr": "Agadir", "aga": "Agadir",
        "meknes": "Meknès", "mek": "Meknès",
        "kenitra": "Kénitra", "ken": "Kénitra",
        "sale": "Salé", "sal": "Salé",
        "oujda": "Oujda", "ouj": "Oujda",
        "beni mellal": "Béni Mellal", "ber": "Béni Mellal",
    }
    mapping.update(manual)
    return mapping


def _parse_date_flexible(series: pd.Series) -> pd.Series:
    """
    Tente de parser une série de dates avec plusieurs formats mixtes :
      - DD/MM/YYYY
      - YYYY-MM-DD
      - Mon DD YYYY  (ex: Jan 05 2024)
    Retourne NaT pour les valeurs non parsables.
    """
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%b %d %Y", "%B %d %Y",
               "%d-%m-%Y", "%m/%d/%Y"]
    result = pd.Series([pd.NaT] * len(series), index=series.index)

    remaining_mask = pd.Series([True] * len(series), index=series.index)

    for fmt in formats:
        if not remaining_mask.any():
            break
        parsed = pd.to_datetime(
            series[remaining_mask], format=fmt, errors="coerce"
        )
        # Affecter les valeurs parsées avec succès
        success = parsed.notna()
        result[remaining_mask & success.reindex(series.index, fill_value=False)] = \
            parsed[success].values
        remaining_mask[remaining_mask & success.reindex(series.index, fill_value=False)] = False

    # Dernier recours : inférence automatique
    still_remaining = remaining_mask & series.notna()
    if still_remaining.any():
        result[still_remaining] = pd.to_datetime(
            series[still_remaining], infer_datetime_format=True, errors="coerce"
        )

    return result


# ──────────────────────────────────────────────
# Transformation principale
# ──────────────────────────────────────────────

def transform_commandes(df: pd.DataFrame, df_regions: pd.DataFrame) -> pd.DataFrame:
    """
    Applique toutes les règles de nettoyage sur les commandes Mexora.

    Parameters
    ----------
    df          : DataFrame brut issu de extract_commandes()
    df_regions  : DataFrame du référentiel géographique (extrait de regions_maroc.csv)

    Returns
    -------
    pd.DataFrame nettoyé et enrichi
    """
    initial = len(df)
    logger.info(f"[TRANSFORM-COMMANDES] Début : {initial:,} lignes")

    # ── R1 : Suppression des doublons sur id_commande ──────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["id_commande"], keep="last")
    dropped = before - len(df)
    logger.info(f"[TRANSFORM-COMMANDES] R1 doublons : {dropped:,} lignes supprimées")

    # ── R2 : Standardisation des dates ────────────────────────────────
    df["date_commande"]  = _parse_date_flexible(df["date_commande"])
    df["date_livraison"] = pd.to_datetime(df["date_livraison"], errors="coerce")

    invalides_date = df["date_commande"].isna().sum()
    df = df.dropna(subset=["date_commande"])
    logger.info(f"[TRANSFORM-COMMANDES] R2 dates : {invalides_date:,} dates invalides supprimées")

    # ── R3 : Harmonisation des villes ─────────────────────────────────
    ville_map = _build_ville_mapping(df_regions)
    df["ville_livraison"] = (
        df["ville_livraison"]
        .str.strip()
        .str.lower()
        .map(ville_map)
        .fillna("Non renseignée")
    )
    non_mappes = (df["ville_livraison"] == "Non renseignée").sum()
    logger.info(
        f"[TRANSFORM-COMMANDES] R3 villes : {non_mappes:,} villes non mappées → 'Non renseignée'"
    )

    # ── R4 : Standardisation des statuts ──────────────────────────────
    df["statut"] = df["statut"].str.strip().replace(STATUTS_MAPPING)
    invalides_statut = ~df["statut"].isin(STATUTS_VALIDES)
    nb_invalides = invalides_statut.sum()
    if nb_invalides:
        logger.warning(
            f"[TRANSFORM-COMMANDES] R4 statuts : {nb_invalides:,} valeurs non reconnues → 'inconnu'"
        )
        df.loc[invalides_statut, "statut"] = "inconnu"

    # ── R5 : Suppression quantités invalides ───────────────────────────
    before = len(df)
    df["quantite"] = pd.to_numeric(df["quantite"], errors="coerce")
    df = df[df["quantite"] > 0]
    logger.info(
        f"[TRANSFORM-COMMANDES] R5 quantités : {before - len(df):,} lignes supprimées (quantite <= 0)"
    )

    # ── R6 : Suppression commandes test (prix = 0) ─────────────────────
    before = len(df)
    df["prix_unitaire"] = pd.to_numeric(df["prix_unitaire"], errors="coerce").fillna(0)
    df = df[df["prix_unitaire"] > 0]
    logger.info(
        f"[TRANSFORM-COMMANDES] R6 prix nuls : {before - len(df):,} commandes test supprimées"
    )

    # ── R7 : Livreurs manquants ────────────────────────────────────────
    nb_manquants = df["id_livreur"].isna().sum() + (df["id_livreur"] == "").sum()
    df["id_livreur"] = df["id_livreur"].replace("", "-1").fillna("-1")
    logger.info(
        f"[TRANSFORM-COMMANDES] R7 livreurs : {nb_manquants:,} valeurs manquantes → '-1'"
    )

    # ── R8 : Calcul montants ───────────────────────────────────────────
    df["quantite"]     = df["quantite"].astype(float)
    df["prix_unitaire"]= df["prix_unitaire"].astype(float)
    df["montant_ht"]   = (df["quantite"] * df["prix_unitaire"]).round(2)
    df["montant_ttc"]  = (df["montant_ht"] * (1 + TVA_TAUX)).round(2)

    # ── Calcul délai de livraison ──────────────────────────────────────
    df["delai_livraison_jours"] = (
        (df["date_livraison"] - df["date_commande"]).dt.days
    ).clip(lower=0)

    # ── Typage final ───────────────────────────────────────────────────
    df["quantite"] = df["quantite"].astype(int)
    df["date_commande"]  = df["date_commande"].dt.date
    df["date_livraison"] = df["date_livraison"].dt.date

    total_supprimees = initial - len(df)
    logger.info(
        f"[TRANSFORM-COMMANDES] Fin : {initial:,} → {len(df):,} lignes "
        f"({total_supprimees:,} supprimées au total)"
    )
    return df.reset_index(drop=True)

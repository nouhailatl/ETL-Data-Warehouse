"""
transform/clean_clients.py
---------------------------
Nettoyage et standardisation du fichier clients_mexora.csv.

Règles appliquées :
  R1  Déduplication sur email normalisé (conserver inscription la plus récente)
  R2  Standardisation du sexe → 'm' / 'f' / 'inconnu'
  R3  Validation des dates de naissance (âge entre 16 et 100 ans)
  R4  Validation du format email (regex)
  R5  Harmonisation des villes via le référentiel régions_maroc
  R6  Calcul de la tranche d'âge
"""

import re
import pandas as pd
from datetime import date

from utils.logger import get_logger
from config.settings import SEXE_MAPPING, AGE_MIN, AGE_MAX

logger = get_logger(__name__)

# Regex de validation email
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

# Mapping villes (même logique que commandes)
def _build_ville_mapping(df_regions: pd.DataFrame) -> dict:
    mapping = {}
    for _, row in df_regions.iterrows():
        std  = row["nom_ville_standard"]
        code = row["code_ville"].lower()
        aliases = [
            std.lower(), code,
            std.replace("è","e").replace("é","e").replace("â","a")
               .replace("ê","e").replace("î","i").replace("ô","o")
               .replace("û","u").lower(),
        ]
        for alias in aliases:
            mapping[alias.strip()] = std

    manual = {
        "tnja": "Tanger", "tng": "Tanger", "tanger-ville": "Tanger",
        "casa": "Casablanca", "cas": "Casablanca",
        "rbat": "Rabat", "rba": "Rabat",
        "marrakesh": "Marrakech", "mrakech": "Marrakech", "mrk": "Marrakech",
        "fez": "Fès", "fes": "Fès",
        "agdr": "Agadir", "aga": "Agadir",
        "meknes": "Meknès", "mek": "Meknès",
        "kenitra": "Kénitra", "ken": "Kénitra",
        "sale": "Salé", "sal": "Salé",
        "ouj": "Oujda",
        "ber": "Béni Mellal",
    }
    mapping.update(manual)
    return mapping


def transform_clients(df: pd.DataFrame, df_regions: pd.DataFrame) -> pd.DataFrame:
    """
    Applique toutes les règles de nettoyage sur les clients Mexora.

    Parameters
    ----------
    df          : DataFrame brut issu de extract_clients()
    df_regions  : référentiel géographique

    Returns
    -------
    pd.DataFrame nettoyé
    """
    initial = len(df)
    logger.info(f"[TRANSFORM-CLIENTS] Début : {initial:,} lignes")

    # ── R1 : Déduplication sur email normalisé ─────────────────────────
    df["email_norm"] = df["email"].str.lower().str.strip()
    df["date_inscription"] = pd.to_datetime(df["date_inscription"], errors="coerce")
    before = len(df)
    df = (
        df.sort_values("date_inscription", na_position="first")
          .drop_duplicates(subset=["email_norm"], keep="last")
    )
    logger.info(
        f"[TRANSFORM-CLIENTS] R1 doublons email : {before - len(df):,} lignes supprimées"
    )

    # ── R2 : Standardisation du sexe ──────────────────────────────────
    df["sexe"] = (
        df["sexe"].str.strip()
                  .map(SEXE_MAPPING)
                  .fillna("inconnu")
    )
    inconnus = (df["sexe"] == "inconnu").sum()
    logger.info(f"[TRANSFORM-CLIENTS] R2 sexe : {inconnus:,} valeurs → 'inconnu'")

    # ── R3 : Validation dates de naissance ────────────────────────────
    df["date_naissance"] = pd.to_datetime(df["date_naissance"], errors="coerce")
    today = pd.Timestamp(date.today())
    df["age_calc"] = ((today - df["date_naissance"]).dt.days / 365.25).astype("float")

    invalide_age = (
        df["age_calc"].isna() |
        (df["age_calc"] < AGE_MIN) |
        (df["age_calc"] > AGE_MAX)
    )
    nb_invalides = invalide_age.sum()
    df.loc[invalide_age, "date_naissance"] = pd.NaT
    df.loc[invalide_age, "age_calc"] = None
    logger.info(
        f"[TRANSFORM-CLIENTS] R3 dates naissance : {nb_invalides:,} dates invalidées "
        f"(âge hors [{AGE_MIN}-{AGE_MAX}] ans)"
    )

    # Tranches d'âge
    df["tranche_age"] = pd.cut(
        df["age_calc"].fillna(-1),
        bins=[-2, 0, 18, 25, 35, 45, 55, 65, 200],
        labels=["inconnu", "<18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"],
    ).astype(str)
    df.loc[df["age_calc"].isna(), "tranche_age"] = "inconnu"

    # ── R4 : Validation email ──────────────────────────────────────────
    mask_email_invalide = ~df["email"].apply(
        lambda x: bool(_EMAIL_RE.match(str(x))) if pd.notna(x) else False
    )
    nb_emails_invalides = mask_email_invalide.sum()
    df.loc[mask_email_invalide, "email"] = None
    logger.info(
        f"[TRANSFORM-CLIENTS] R4 emails : {nb_emails_invalides:,} emails invalides → None"
    )

    # ── R5 : Harmonisation des villes ─────────────────────────────────
    ville_map = _build_ville_mapping(df_regions)
    df["ville"] = (
        df["ville"].str.strip().str.lower()
                   .map(ville_map)
                   .fillna("Non renseignée")
    )
    non_mappes = (df["ville"] == "Non renseignée").sum()
    logger.info(
        f"[TRANSFORM-CLIENTS] R5 villes : {non_mappes:,} villes non mappées → 'Non renseignée'"
    )

    # ── Nettoyage final ────────────────────────────────────────────────
    df["nom_complet"] = df["prenom"].str.strip() + " " + df["nom"].str.strip()
    df["date_inscription"] = df["date_inscription"].dt.date
    df["date_naissance"] = df["date_naissance"].dt.date.where(df["date_naissance"].notna(), None)

    # Supprimer colonnes temporaires
    df = df.drop(columns=["email_norm", "age_calc"], errors="ignore")

    logger.info(
        f"[TRANSFORM-CLIENTS] Fin : {initial:,} → {len(df):,} lignes "
        f"({initial - len(df):,} supprimées)"
    )
    return df.reset_index(drop=True)

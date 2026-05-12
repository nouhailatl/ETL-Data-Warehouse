"""
transform/clean_produits.py
----------------------------
Nettoyage et standardisation du fichier produits_mexora.json.

Règles appliquées :
  R1  Standardisation de la casse des catégories → Title Case
  R2  Remplacement des prix_catalogue null par la médiane de la sous-catégorie
  R3  Standardisation de la colonne 'actif' en booléen
  R4  Normalisation des dates de création
  R5  Suppression des espaces parasites sur les champs texte
"""

import pandas as pd

from utils.logger import get_logger

logger = get_logger(__name__)

# Mapping manuel des catégories avec casse incohérente → valeur standard
_CATEGORIE_MAPPING = {
    "electronique":  "Electronique",
    "ELECTRONIQUE":  "Electronique",
    "Electronique":  "Electronique",
    "mode":          "Mode",
    "MODE":          "Mode",
    "Mode":          "Mode",
    "alimentation":  "Alimentation",
    "ALIMENTATION":  "Alimentation",
    "Alimentation":  "Alimentation",
}


def transform_produits(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applique toutes les règles de nettoyage sur les produits Mexora.

    Parameters
    ----------
    df : DataFrame brut issu de extract_produits()

    Returns
    -------
    pd.DataFrame nettoyé
    """
    initial = len(df)
    logger.info(f"[TRANSFORM-PRODUITS] Début : {initial:,} lignes")

    # ── R5 : Suppression espaces parasites ────────────────────────────
    str_cols = ["id_produit", "nom", "categorie", "sous_categorie",
                "marque", "fournisseur", "origine_pays"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ── R1 : Standardisation casse catégories ─────────────────────────
    cats_avant = df["categorie"].unique().tolist()
    df["categorie"] = df["categorie"].replace(_CATEGORIE_MAPPING)
    # Fallback : Title Case pour toute valeur non mappée
    unmapped = ~df["categorie"].isin(["Electronique", "Mode", "Alimentation"])
    df.loc[unmapped, "categorie"] = df.loc[unmapped, "categorie"].str.title()
    cats_apres = df["categorie"].unique().tolist()
    logger.info(
        f"[TRANSFORM-PRODUITS] R1 catégories : {cats_avant} → {cats_apres}"
    )

    # ── R2 : Remplacement des prix null ───────────────────────────────
    df["prix_catalogue"] = pd.to_numeric(df["prix_catalogue"], errors="coerce")
    nb_null_prix = df["prix_catalogue"].isna().sum()
    if nb_null_prix > 0:
        # Médiane par sous-catégorie
        mediane_par_sous_cat = (
            df.groupby("sous_categorie")["prix_catalogue"]
              .transform("median")
        )
        # Médiane globale en dernier recours
        mediane_globale = df["prix_catalogue"].median()
        df["prix_catalogue"] = (
            df["prix_catalogue"]
              .fillna(mediane_par_sous_cat)
              .fillna(mediane_globale)
              .round(2)
        )
        logger.info(
            f"[TRANSFORM-PRODUITS] R2 prix null : {nb_null_prix:,} valeurs imputées "
            f"(médiane sous-catégorie)"
        )
    else:
        logger.info("[TRANSFORM-PRODUITS] R2 prix null : aucun prix manquant")

    # ── R3 : Standardisation booléen 'actif' ──────────────────────────
    df["actif"] = df["actif"].apply(
        lambda x: bool(x) if isinstance(x, bool)
        else str(x).lower() in ("true", "1", "yes", "oui")
    )
    nb_inactifs = (~df["actif"]).sum()
    logger.info(
        f"[TRANSFORM-PRODUITS] R3 actif : {nb_inactifs:,} produits inactifs "
        f"(conservés pour gestion SCD)"
    )

    # ── R4 : Normalisation dates création ─────────────────────────────
    df["date_creation"] = pd.to_datetime(df["date_creation"], errors="coerce").dt.date

    # ── Colonnes SCD Type 2 (valeurs initiales) ────────────────────────
    # Ces colonnes seront gérées lors du chargement (build_dimensions)
    from datetime import date
    df["date_debut"]  = date.today()
    df["date_fin"]    = date(9999, 12, 31)
    df["est_actif_dwh"] = True   # différent de 'actif' source (SCD)

    logger.info(f"[TRANSFORM-PRODUITS] Fin : {len(df):,} lignes (aucune suppression)")
    return df.reset_index(drop=True)

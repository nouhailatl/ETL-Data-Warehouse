"""
transform/build_dimensions.py
------------------------------
Construction des 5 tables de dimensions et de la table de faits
à partir des DataFrames nettoyés.

  build_dim_temps(start, end)              → DIM_TEMPS
  build_dim_produit(df_produits)           → DIM_PRODUIT
  build_dim_region(df_regions)             → DIM_REGION
  build_dim_client(df_clients, df_cmd)     → DIM_CLIENT  (avec segment Gold/Silver/Bronze)
  build_dim_livreur(df_commandes)          → DIM_LIVREUR
  build_fait_ventes(df_cmd, dims...)       → FAIT_VENTES
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta

from utils.logger import get_logger
from config.settings import (
    DIM_TEMPS_START, DIM_TEMPS_END,
    FERIES_MAROC, RAMADAN_PERIODES,
    SEGMENT_GOLD, SEGMENT_SILVER,
)

logger = get_logger(__name__)


# ══════════════════════════════════════════════
# DIM_TEMPS
# ══════════════════════════════════════════════

def build_dim_temps(
    date_debut: str = DIM_TEMPS_START,
    date_fin:   str = DIM_TEMPS_END,
) -> pd.DataFrame:
    """
    Génère la dimension temporelle complète entre deux dates.
    Chaque ligne = 1 jour.

    Returns
    -------
    pd.DataFrame avec colonnes :
        id_date, jour, mois, trimestre, annee, semaine,
        libelle_jour, libelle_mois, est_weekend,
        est_ferie_maroc, periode_ramadan, date_complete
    """
    logger.info(f"[BUILD] DIM_TEMPS : génération {date_debut} → {date_fin}")
    dates = pd.date_range(start=date_debut, end=date_fin, freq="D")

    feries_set = set(FERIES_MAROC)

    df = pd.DataFrame({
        "id_date":         dates.strftime("%Y%m%d").astype(int),
        "date_complete":   dates.date,
        "jour":            dates.day,
        "mois":            dates.month,
        "trimestre":       dates.quarter,
        "annee":           dates.year,
        "semaine":         dates.isocalendar().week.astype(int),
        "libelle_jour":    dates.strftime("%A"),
        "libelle_mois":    dates.strftime("%B"),
        "est_weekend":     (dates.dayofweek >= 5),
        "est_ferie_maroc": dates.strftime("%Y-%m-%d").isin(feries_set),
        "periode_ramadan": False,
    })

    # Marquer les périodes Ramadan
    for debut, fin in RAMADAN_PERIODES:
        masque = (
            (df["date_complete"] >= pd.Timestamp(debut).date()) &
            (df["date_complete"] <= pd.Timestamp(fin).date())
        )
        df.loc[masque, "periode_ramadan"] = True

    logger.info(f"[BUILD] DIM_TEMPS : {len(df):,} jours générés")
    return df


# ══════════════════════════════════════════════
# DIM_PRODUIT
# ══════════════════════════════════════════════

def build_dim_produit(df_produits: pd.DataFrame) -> pd.DataFrame:
    """
    Construit DIM_PRODUIT depuis les produits nettoyés.
    Ajoute une surrogate key (id_produit_sk).
    Les colonnes SCD Type 2 (date_debut, date_fin, est_actif_dwh)
    sont déjà présentes depuis clean_produits.py.

    Returns
    -------
    pd.DataFrame avec colonnes :
        id_produit_sk, id_produit_nk, nom_produit, categorie,
        sous_categorie, marque, fournisseur, prix_standard,
        origine_pays, date_creation, date_debut, date_fin, est_actif_dwh
    """
    logger.info("[BUILD] DIM_PRODUIT : construction")
    df = df_produits.copy()

    # Renommer pour aligner avec le schéma DWH
    df = df.rename(columns={
        "id_produit":     "id_produit_nk",
        "nom":            "nom_produit",
        "prix_catalogue": "prix_standard",
        "actif":          "actif_source",
    })

    # Surrogate key
    df.insert(0, "id_produit_sk", range(1, len(df) + 1))

    cols = [
        "id_produit_sk", "id_produit_nk", "nom_produit", "categorie",
        "sous_categorie", "marque", "fournisseur", "prix_standard",
        "origine_pays", "date_creation", "date_debut", "date_fin", "est_actif_dwh",
    ]
    df = df[[c for c in cols if c in df.columns]]

    logger.info(f"[BUILD] DIM_PRODUIT : {len(df):,} produits")
    return df.reset_index(drop=True)


# ══════════════════════════════════════════════
# DIM_REGION
# ══════════════════════════════════════════════

def build_dim_region(df_regions: pd.DataFrame) -> pd.DataFrame:
    """
    Construit DIM_REGION depuis le référentiel géographique.

    Returns
    -------
    pd.DataFrame avec colonnes :
        id_region, code_ville, ville, province,
        region_admin, zone_geo, population, pays
    """
    logger.info("[BUILD] DIM_REGION : construction")
    df = df_regions.copy()

    df = df.rename(columns={"nom_ville_standard": "ville"})
    df.insert(0, "id_region", range(1, len(df) + 1))
    df["pays"] = "Maroc"

    # Ajouter une ligne "Non renseignée" pour les villes non mappées
    non_renseignee = pd.DataFrame([{
        "id_region": 0,
        "code_ville": "XXX",
        "ville": "Non renseignée",
        "province": "Inconnu",
        "region_admin": "Inconnu",
        "zone_geo": "Inconnu",
        "population": None,
        "code_postal": None,
        "pays": "Maroc",
    }])
    df = pd.concat([non_renseignee, df], ignore_index=True)

    logger.info(f"[BUILD] DIM_REGION : {len(df):,} régions (dont 1 valeur 'Non renseignée')")
    return df


# ══════════════════════════════════════════════
# DIM_CLIENT
# ══════════════════════════════════════════════

def _calculer_segments(df_commandes: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule le segment Gold/Silver/Bronze basé sur le CA cumulé
    des 12 derniers mois (commandes livrées uniquement).

    Règles Mexora :
        Gold   : CA >= 15 000 MAD
        Silver : CA >= 5 000 MAD
        Bronze : CA < 5 000 MAD
    """
    date_limite = pd.Timestamp(date.today() - timedelta(days=365))

    df_recent = df_commandes[
        (pd.to_datetime(df_commandes["date_commande"]) >= date_limite) &
        (df_commandes["statut"] == "livré")
    ].copy()

    if df_recent.empty:
        # Si aucune commande récente, tout le monde est Bronze
        tous_clients = df_commandes["id_client"].unique()
        return pd.DataFrame({
            "id_client": tous_clients,
            "segment_client": "Bronze",
            "ca_12m": 0.0,
        })

    df_recent["montant_ttc"] = pd.to_numeric(df_recent["montant_ttc"], errors="coerce").fillna(0)
    ca_par_client = (
        df_recent.groupby("id_client")["montant_ttc"]
                 .sum()
                 .reset_index()
                 .rename(columns={"montant_ttc": "ca_12m"})
    )

    def _segment(ca: float) -> str:
        if ca >= SEGMENT_GOLD:   return "Gold"
        if ca >= SEGMENT_SILVER: return "Silver"
        return "Bronze"

    ca_par_client["segment_client"] = ca_par_client["ca_12m"].apply(_segment)
    return ca_par_client


def build_dim_client(
    df_clients:   pd.DataFrame,
    df_commandes: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construit DIM_CLIENT en joignant les clients nettoyés
    avec la segmentation calculée depuis les commandes.

    Returns
    -------
    pd.DataFrame avec colonnes :
        id_client_sk, id_client_nk, nom_complet, tranche_age, sexe,
        ville, region_admin, segment_client, canal_acquisition,
        date_debut, date_fin, est_actif
    """
    logger.info("[BUILD] DIM_CLIENT : construction")

    # Joindre les régions pour récupérer region_admin
    # (df_clients.ville est déjà standardisé)
    segments = _calculer_segments(df_commandes)

    df = df_clients.copy()
    df = df.merge(segments, on="id_client", how="left")
    df["segment_client"] = df["segment_client"].fillna("Bronze")
    df["ca_12m"]         = df["ca_12m"].fillna(0.0)

    # Renommage pour aligner avec le schéma DWH
    df = df.rename(columns={"id_client": "id_client_nk"})

    # Colonnes SCD Type 2
    df["date_debut"]  = date.today()
    df["date_fin"]    = date(9999, 12, 31)
    df["est_actif"]   = True

    # Surrogate key
    df.insert(0, "id_client_sk", range(1, len(df) + 1))

    cols = [
        "id_client_sk", "id_client_nk", "nom_complet", "tranche_age", "sexe",
        "ville", "canal_acquisition", "segment_client", "ca_12m",
        "date_inscription", "date_debut", "date_fin", "est_actif",
    ]
    df = df[[c for c in cols if c in df.columns]]

    # Segments
    gold   = (df["segment_client"] == "Gold").sum()
    silver = (df["segment_client"] == "Silver").sum()
    bronze = (df["segment_client"] == "Bronze").sum()
    logger.info(
        f"[BUILD] DIM_CLIENT : {len(df):,} clients | "
        f"Gold={gold} Silver={silver} Bronze={bronze}"
    )
    return df.reset_index(drop=True)


# ══════════════════════════════════════════════
# DIM_LIVREUR
# ══════════════════════════════════════════════

def build_dim_livreur(df_commandes: pd.DataFrame) -> pd.DataFrame:
    """
    Construit DIM_LIVREUR depuis les id_livreur uniques présents
    dans les commandes (les détails livreurs ne sont pas dans la source,
    on génère des données réalistes à partir des IDs).

    Returns
    -------
    pd.DataFrame avec colonnes :
        id_livreur, id_livreur_nk, nom_livreur,
        type_transport, zone_couverture, est_actif
    """
    logger.info("[BUILD] DIM_LIVREUR : construction")

    livreurs_ids = (
        df_commandes["id_livreur"]
        .dropna()
        .unique()
    )
    # Exclure -1 (livreur inconnu)
    livreurs_ids = [lid for lid in livreurs_ids if str(lid) != "-1"]

    types_transport   = ["Moto", "Voiture", "Camionnette", "Vélo"]
    zones_couverture  = [
        "Tanger", "Casablanca", "Rabat", "Marrakech", "Fès",
        "Agadir", "Meknès", "Oujda", "National",
    ]
    noms_livreurs = [
        "Ali Benjelloun","Youssef Karimi","Ahmed Tlemcani","Hassan Ziani",
        "Omar Filali","Mehdi Chraibi","Karim Lahlou","Rachid Berrada",
        "Nabil Alaoui","Samir El Fassi","Bilal Idrissi","Hamza Tazi",
        "Adil Mansouri","Reda Moussaoui","Tariq Belkadi","Hicham Ghazi",
        "Zakaria Bennani","Mustapha Ouali","Khalid Tahiri","Amine Kadiri",
    ]

    import random
    random.seed(99)
    rows = []
    for i, lid in enumerate(sorted(livreurs_ids)):
        rows.append({
            "id_livreur":    i + 1,
            "id_livreur_nk": str(lid),
            "nom_livreur":   noms_livreurs[i % len(noms_livreurs)],
            "type_transport": random.choice(types_transport),
            "zone_couverture": random.choice(zones_couverture),
            "est_actif": True,
        })

    # Livreur inconnu (id = 0)
    rows.insert(0, {
        "id_livreur":    0,
        "id_livreur_nk": "-1",
        "nom_livreur":   "Livreur Inconnu",
        "type_transport": "Inconnu",
        "zone_couverture": "Inconnu",
        "est_actif": False,
    })

    df = pd.DataFrame(rows)
    logger.info(f"[BUILD] DIM_LIVREUR : {len(df):,} livreurs (dont 1 inconnu)")
    return df


# ══════════════════════════════════════════════
# FAIT_VENTES
# ══════════════════════════════════════════════

def build_fait_ventes(
    df_commandes: pd.DataFrame,
    dim_temps:    pd.DataFrame,
    dim_client:   pd.DataFrame,
    dim_produit:  pd.DataFrame,
    dim_region:   pd.DataFrame,
    dim_livreur:  pd.DataFrame,
) -> pd.DataFrame:
    """
    Construit la table de faits FAIT_VENTES en résolvant
    les surrogate keys depuis les dimensions.

    Granularité : 1 ligne = 1 commande (1 produit × 1 client × 1 date)

    Returns
    -------
    pd.DataFrame avec colonnes :
        id_vente, id_date, id_produit, id_client, id_region, id_livreur,
        quantite_vendue, montant_ht, montant_ttc, cout_livraison,
        delai_livraison_jours, remise_pct, statut_commande,
        mode_paiement, date_chargement
    """
    logger.info(f"[BUILD] FAIT_VENTES : début avec {len(df_commandes):,} commandes")

    df = df_commandes.copy()

    # ── Résolution id_date ─────────────────────────────────────────────
    temps_lookup = dim_temps.set_index("date_complete")["id_date"].to_dict()
    df["id_date"] = pd.to_datetime(df["date_commande"]).dt.date.map(temps_lookup)
    nb_date_manq = df["id_date"].isna().sum()
    if nb_date_manq:
        logger.warning(f"[BUILD] FAIT_VENTES : {nb_date_manq:,} dates non résolues → supprimées")
        df = df.dropna(subset=["id_date"])

    # ── Résolution id_produit (surrogate key) ─────────────────────────
    produit_lookup = dim_produit.set_index("id_produit_nk")["id_produit_sk"].to_dict()
    df["id_produit"] = df["id_produit"].map(produit_lookup)
    nb_prod_manq = df["id_produit"].isna().sum()
    if nb_prod_manq:
        logger.warning(f"[BUILD] FAIT_VENTES : {nb_prod_manq:,} produits non résolus → supprimés")
        df = df.dropna(subset=["id_produit"])

    # ── Résolution id_client (surrogate key) ──────────────────────────
    client_lookup = dim_client.set_index("id_client_nk")["id_client_sk"].to_dict()
    df["id_client"] = df["id_client"].map(client_lookup)
    nb_cli_manq = df["id_client"].isna().sum()
    if nb_cli_manq:
        logger.warning(
            f"[BUILD] FAIT_VENTES : {nb_cli_manq:,} clients non résolus → id_client_sk=0"
        )
        df["id_client"] = df["id_client"].fillna(0).astype(int)

    # ── Résolution id_region ───────────────────────────────────────────
    region_lookup = dim_region.set_index("ville")["id_region"].to_dict()
    df["id_region"] = df["ville_livraison"].map(region_lookup)
    df["id_region"] = df["id_region"].fillna(0).astype(int)  # 0 = Non renseignée

    # ── Résolution id_livreur ──────────────────────────────────────────
    livreur_lookup = dim_livreur.set_index("id_livreur_nk")["id_livreur"].to_dict()
    df["id_livreur_fk"] = df["id_livreur"].astype(str).map(livreur_lookup).fillna(0).astype(int)

    # ── Coût de livraison estimé (non présent dans source) ────────────
    # Règle métier : 30 MAD par défaut, 0 si commande annulée
    df["cout_livraison"] = 30.0
    df.loc[df["statut"] == "annulé", "cout_livraison"] = 0.0

    # ── Remise (non présente dans source, initialisée à 0) ────────────
    df["remise_pct"] = 0.0

    # ── Construction de la table de faits ─────────────────────────────
    fait = pd.DataFrame({
        "id_date":              df["id_date"].astype(int),
        "id_produit":           df["id_produit"].astype(int),
        "id_client":            df["id_client"].astype(int),
        "id_region":            df["id_region"].astype(int),
        "id_livreur":           df["id_livreur_fk"].astype(int),
        "quantite_vendue":      df["quantite"].astype(int),
        "montant_ht":           df["montant_ht"].astype(float),
        "montant_ttc":          df["montant_ttc"].astype(float),
        "cout_livraison":       df["cout_livraison"].astype(float),
        "delai_livraison_jours":df["delai_livraison_jours"].astype("Int64"),
        "remise_pct":           df["remise_pct"].astype(float),
        "statut_commande":      df["statut"],
        "mode_paiement":        df["mode_paiement"],
    })

    # Surrogate key pour la table de faits
    fait.insert(0, "id_vente", range(1, len(fait) + 1))

    # Horodatage ETL
    from datetime import datetime
    fait["date_chargement"] = datetime.now()

    logger.info(
        f"[BUILD] FAIT_VENTES : {len(fait):,} lignes | "
        f"CA total TTC = {fait['montant_ttc'].sum():,.0f} MAD"
    )
    return fait.reset_index(drop=True)

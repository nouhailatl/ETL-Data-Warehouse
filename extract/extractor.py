"""
extract/extractor.py
--------------------
Phase EXTRACT du pipeline ETL Mexora.
Lit les 4 fichiers sources bruts SANS aucune transformation.
Tout est chargé en string pour éviter les conversions implicites de pandas.
"""

import json
import pandas as pd
from pathlib import Path

from utils.logger import get_logger
from config.settings import (
    COMMANDES_FILE, PRODUITS_FILE,
    CLIENTS_FILE,   REGIONS_FILE,
)

logger = get_logger(__name__)


def extract_commandes(filepath: Path = COMMANDES_FILE) -> pd.DataFrame:
    """
    Extrait les commandes depuis le fichier CSV source.
    Retourne le DataFrame brut sans aucune modification.

    Returns
    -------
    pd.DataFrame  — colonnes :
        id_commande, id_client, id_produit, date_commande, quantite,
        prix_unitaire, statut, ville_livraison, mode_paiement,
        id_livreur, date_livraison
    """
    logger.info(f"[EXTRACT] Lecture commandes : {filepath}")
    df = pd.read_csv(filepath, encoding="utf-8", dtype=str)
    # Supprimer espaces parasites sur les noms de colonnes
    df.columns = df.columns.str.strip()
    logger.info(f"[EXTRACT] Commandes brutes : {len(df):,} lignes | {df.shape[1]} colonnes")
    return df


def extract_produits(filepath: Path = PRODUITS_FILE) -> pd.DataFrame:
    """
    Extrait les produits depuis le fichier JSON source.
    Retourne un DataFrame plat.

    Returns
    -------
    pd.DataFrame  — colonnes :
        id_produit, nom, categorie, sous_categorie, marque,
        fournisseur, prix_catalogue, origine_pays, date_creation, actif
    """
    logger.info(f"[EXTRACT] Lecture produits : {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    df = pd.DataFrame(data["produits"])
    df.columns = df.columns.str.strip()
    logger.info(f"[EXTRACT] Produits bruts : {len(df):,} lignes | {df.shape[1]} colonnes")
    return df


def extract_clients(filepath: Path = CLIENTS_FILE) -> pd.DataFrame:
    """
    Extrait les clients depuis le fichier CSV source.
    Retourne le DataFrame brut sans aucune modification.

    Returns
    -------
    pd.DataFrame  — colonnes :
        id_client, nom, prenom, email, date_naissance, sexe,
        ville, telephone, date_inscription, canal_acquisition
    """
    logger.info(f"[EXTRACT] Lecture clients : {filepath}")
    df = pd.read_csv(filepath, encoding="utf-8", dtype=str)
    df.columns = df.columns.str.strip()
    logger.info(f"[EXTRACT] Clients bruts : {len(df):,} lignes | {df.shape[1]} colonnes")
    return df


def extract_regions(filepath: Path = REGIONS_FILE) -> pd.DataFrame:
    """
    Extrait le référentiel géographique (fichier propre).
    Utilisé comme table de correspondance pour harmoniser les villes.

    Returns
    -------
    pd.DataFrame  — colonnes :
        code_ville, nom_ville_standard, province,
        region_admin, zone_geo, population, code_postal
    """
    logger.info(f"[EXTRACT] Lecture régions : {filepath}")
    df = pd.read_csv(filepath, encoding="utf-8", dtype=str)
    df.columns = df.columns.str.strip()
    logger.info(f"[EXTRACT] Régions brutes : {len(df):,} lignes")
    return df

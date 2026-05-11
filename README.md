# 📊 Mexora Data Warehouse Project : Architecture ETL & BI

## 🌟 Présentation du Projet
Ce projet consiste en la mise en place d'une solution complète de **Business Intelligence** pour l'entreprise **Mexora**. L'objectif est de centraliser des données hétérogènes (fichiers CSV et JSON) dans un entrepôt de données structuré pour permettre une analyse décisionnelle avancée.

L'architecture repose sur un pipeline **ETL (Extract, Transform, Load)** automatisé en Python et un stockage robuste sous PostgreSQL, culminant par un dashboard interactif sous Power BI.

---

## 🛠️ Stack Technique
* **Langage :** Python 3.12 (Pandas, SQLAlchemy)
* **Base de Données :** PostgreSQL 18 (Schéma en étoile)
* **Outils BI :** Power BI Desktop
* **Gestion de version :** Git / GitHub

---

## 📐 Architecture des Données (Star Schema)
L'entrepôt est structuré selon un schéma en étoile pour optimiser les performances de calcul :

* **Table de Faits :** `fait_ventes` (Mesures de ventes, prix, quantités).
* **Dimensions :**
    * `dim_client` : Données sociodémographiques (Historisation SCD Type 2).
    * `dim_produit` : Catalogue produits et catégories.
    * `dim_temps` : Calendrier (Année, Trimestre, Mois, Jour).
    * `dim_region` : Référentiel géographique (Provinces et Régions du Maroc).

---

## ⚙️ Pipeline ETL
Le processus de transformation des données est divisé en trois scripts principaux :

1.  **`nettoyage_clients.py`** : 
    * Extraction depuis CSV.
    * Fusion Nom/Prénom et suppression des doublons.
    * Chargement vers `dwh_mexora.dim_client`.
2.  **`nettoyage_produits.py`** : 
    * Normalisation de fichiers JSON complexes (unfolding).
    * Nettoyage des prix et renommage des colonnes.
3.  **`nettoyage_commandes.py`** : 
    * Nettoyage des dates (JJ/MM/AAAA vers YYYY-MM-DD).
    * Filtrage des quantités et montants positifs.
    * Liaison des clés étrangères vers la table de faits.

---

## 🚀 Installation et Utilisation

### 1. Prérequis
* Avoir une instance **PostgreSQL** active.
* Installer les dépendances Python :
    ```bash
    pip install pandas sqlalchemy psycopg2
    ```

### 2. Configuration
Modifier l'URL de connexion dans les scripts Python avec vos identifiants :
```python
engine = create_engine("postgresql://user:password@localhost:5432/dbname")
```
3. Exécution
Lancez les scripts dans l'ordre suivant :

```Bash
python nettoyage_clients.py
python nettoyage_produits.py
python nettoyage_commandes.py
```
📈 Dashboard & Insights
Le rapport Power BI final permet de répondre aux problématiques métier suivantes :

Analyse du CA : Évolution mensuelle et par région.
Top Produits : Identification des articles les plus performants.
Panier Moyen : Segmentation par type de client (Gold, Silver, Bronze).

# 🏗️ Mexora ETL — Pipeline Data Warehouse
=======
#  Mexora ETL — Pipeline Data Warehouse

Pipeline ETL complet pour le Data Warehouse de Mexora Analytics.  
**Stack :** Python 3.11+ · pandas · SQLAlchemy · PostgreSQL 15+

---

## 📁 Structure du projet

```
mexora_etl/
├── config/
│   └── settings.py          # Chemins, connexion DB, constantes métier
├── data/
│   ├── commandes_mexora.csv  # Source 1 — 50 000 commandes (brutes)
│   ├── produits_mexora.json  # Source 2 — catalogue produits
│   ├── clients_mexora.csv    # Source 3 — base clients
│   └── regions_maroc.csv     # Source 4 — référentiel géographique (propre)
├── extract/
│   └── extractor.py          # Lecture des 4 fichiers sources
├── transform/
│   ├── clean_commandes.py    # Nettoyage commandes (7 règles)
│   ├── clean_clients.py      # Nettoyage clients (5 règles)
│   ├── clean_produits.py     # Nettoyage produits (5 règles)
│   └── build_dimensions.py   # Construction des 5 dimensions + FAIT_VENTES
├── load/
│   └── loader.py             # Chargement PostgreSQL (REPLACE + UPSERT) ou CSV
├── utils/
│   └── logger.py             # Logging centralisé
├── logs/                     # Logs horodatés (auto-générés)
├── output_csv/               # Export CSV (mode --csv, auto-généré)
├── main.py                   # Point d'entrée — orchestration
└── requirements.txt
```

---

## ⚙️ Installation

```bash
# 1. Cloner le projet
git clone https://github.com/votre-user/mexora-etl.git
cd mexora_etl

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. (Optionnel) Configurer la base PostgreSQL via variables d'environnement
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=mexora_dwh
export DB_USER=postgres
export DB_PASS=postgres
```

---

## 🚀 Utilisation

### Mode 1 — PostgreSQL (production)
```bash
python main.py
```
Charge toutes les dimensions et la table de faits dans PostgreSQL.  
Pré-requis : PostgreSQL 15+ installé, base `mexora_dwh` créée, schéma `dwh_mexora` existant.

### Mode 2 — CSV (développement, sans PostgreSQL)
```bash
python main.py --csv
```
Exporte toutes les tables transformées en CSV dans `output_csv/`.  
Idéal pour tester sans base de données.

### Mode 3 — Dry-run (validation uniquement)
```bash
python main.py --dry-run
```
Exécute Extract + Transform uniquement. Aucune donnée chargée.  
Utile pour valider les transformations rapidement.

---

## 🗄️ Schéma du Data Warehouse

```
                    ┌─────────────┐
                    │  DIM_TEMPS  │
                    └──────┬──────┘
       ┌──────────┐        │        ┌─────────────┐
       │DIM_CLIENT│        │        │ DIM_PRODUIT │
       └────┬─────┘        ▼        └──────┬──────┘
            └──────► FAIT_VENTES ◄──────────┘
       ┌──────────┐        ▲        ┌─────────────┐
       │DIM_REGION│        │        │ DIM_LIVREUR │
       └────┬─────┘        │        └──────┬──────┘
            └──────────────┘───────────────┘
```

**Granularité :** 1 ligne = 1 commande (1 produit × 1 client × 1 date)

**Mesures FAIT_VENTES :**
| Mesure | Additivité |
|---|---|
| quantite_vendue | Additive |
| montant_ht | Additive |
| montant_ttc | Additive |
| cout_livraison | Additive |
| delai_livraison_jours | Semi-additive (AVG) |
| remise_pct | Non-additive |

---

## 🔄 Règles de transformation appliquées

### Commandes (7 règles)
| Règle | Description | Impact |
|---|---|---|
| R1 | Suppression doublons `id_commande` (keep last) | ~1 500 lignes |
| R2 | Standardisation dates mixtes → `YYYY-MM-DD` | 3 formats parsés |
| R3 | Harmonisation villes via référentiel régions | Alias multiples |
| R4 | Standardisation statuts (OK→en_cours, KO→annulé...) | ~3 600 valeurs |
| R5 | Suppression quantité <= 0 | ~400 lignes |
| R6 | Suppression prix = 0 (commandes test) | ~550 lignes |
| R7 | `id_livreur` manquant → `-1` (livreur inconnu) | ~3 500 lignes |

### Clients (5 règles)
| Règle | Description |
|---|---|
| R1 | Déduplication email normalisé (keep dernière inscription) |
| R2 | Standardisation sexe : m/f/1/0/Homme/Femme → `m`/`f`/`inconnu` |
| R3 | Validation âge [16-100 ans], invalidation sinon |
| R4 | Validation format email (regex) |
| R5 | Harmonisation villes via référentiel |

### Produits (5 règles)
| Règle | Description |
|---|---|
| R1 | Casse catégories : electronique/ELECTRONIQUE → `Electronique` |
| R2 | Prix null imputé par médiane de la sous-catégorie |
| R3 | Booléen `actif` standardisé |
| R4 | Dates de création normalisées |
| R5 | Espaces parasites supprimés |

---

## 📊 SCD (Slowly Changing Dimensions)

- **DIM_PRODUIT** → SCD Type 2 : colonnes `date_debut`, `date_fin`, `est_actif_dwh`
- **DIM_CLIENT** → SCD Type 2 : colonnes `date_debut`, `date_fin`, `est_actif`
- **DIM_REGION** → SCD Type 1 (écrasement)
- **DIM_LIVREUR** → SCD Type 1 (écrasement)

---

## 📝 Logs

Les logs sont générés automatiquement dans `logs/etl_YYYYMMDD_HHMMSS.log`.  
Chaque règle loggue le nombre de lignes affectées.

---

## 🛠️ Configuration PostgreSQL

Modifier `config/settings.py` ou utiliser des variables d'environnement :

```python
DB_HOST = "localhost"      # ou export DB_HOST=...
DB_PORT = "5432"
DB_NAME = "mexora_dwh"
DB_USER = "postgres"
DB_PASS = "nouhaila2004"
```

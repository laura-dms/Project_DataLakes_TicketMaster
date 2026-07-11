````markdown
# Data Lake Pipeline – Ticketmaster

Ce projet met en œuvre un **pipeline Data Lake** basé sur l'architecture **Raw → Staging → Curated** à partir des données de l'API **Ticketmaster** et de données externes de fréquentation touristique.

L'ensemble du pipeline est orchestré avec **Apache Airflow** et permet d'ingérer, nettoyer, enrichir puis stocker les données dans différentes bases de données adaptées à chaque étape.

---

# Architecture

```text
              Ticketmaster API
                     │
                     ▼
       Données de fréquentation touristique
                     │
                     ▼
            LocalStack (Raw)
                     │
                     ▼
            MySQL (Staging)
                     │
                     ▼
        Machine Learning (Enrichissement)
                     │
                     ▼
          MongoDB (Curated)
```

Le pipeline réalise les opérations suivantes :

- Ingestion des données de l'API Ticketmaster
- Ingestion des données externes de fréquentation touristique
- Stockage des données brutes dans LocalStack (Raw)
- Nettoyage et préparation des données dans MySQL (Staging)
- Entraînement d'un modèle de Machine Learning
- Enrichissement des données
- Stockage des données finales dans MongoDB (Curated)

---

# Structure du projet

```text
.
├── dags/
│   └── data_lake_pipeline.py
├── src/
│   ├── ingestion.py
│   ├── staging.py
│   ├── train_model.py
│   ├── curated_ml.py
│   └── app.py
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

# Technologies utilisées

- Python 3.12
- Apache Airflow
- Docker
- Docker Compose
- LocalStack
- MySQL
- MongoDB
- FastAPI
- uv

---

# Pré-requis

Avant de commencer, installer :

- Docker Desktop
- Visual Studio Code
- Python 3.12
- uv

---

# Installation

## 1. Cloner le projet

```bash
git clone <url_du_repo>
cd projet-datalakes
```

---

## 2. Installer les dépendances

```bash
uv sync
```

---

## 3. Lancer les services Docker

```bash
docker compose up -d
```

Vérifier que tous les conteneurs sont bien démarrés :

```bash
docker ps
```

---

## 4. Lancer Airflow

```bash
uv run airflow standalone
```

L'interface est disponible à l'adresse :

```
http://localhost:8080
```

---

# Exécution manuelle du pipeline

Les différentes étapes peuvent être exécutées indépendamment.

## 1. Ingestion des données

Cette étape récupère :

- les données de l'API Ticketmaster ;
- les données de fréquentation touristique.

```bash
uv run src/ingestion.py
```

---

## 2. Nettoyage et préparation des données (Staging)

Les données sont nettoyées, transformées puis chargées dans MySQL.

```bash
uv run src/staging.py
```

---

## 3. Entraînement du modèle de Machine Learning

Le modèle est entraîné afin d'enrichir les données.

```bash
uv run src/train_model.py
```

---

## 4. Stockage des données enrichies (Curated)

Les données enrichies sont enregistrées dans MongoDB.

```bash
uv run src/curated_ml.py
```

---

## 5. Lancer l'API FastAPI

Depuis le dossier `src` :

```bash
cd src
uv run uvicorn app:app --reload
```

L'API sera disponible sur :

```
http://127.0.0.1:8000
```

La documentation Swagger est accessible sur :

```
http://127.0.0.1:8000/docs
```

---

# Exécution avec Apache Airflow

Une fois Airflow démarré :

1. Ouvrir l'interface Airflow.
2. Activer le DAG.
3. Cliquer sur **Trigger DAG**.

Les tâches s'exécutent automatiquement dans l'ordre suivant :

```text
raw_ingestion
        ↓
staging_mysql
        ↓
train_ml_model
        ↓
curated_mongodb
```

---

# Résultat du pipeline

À la fin de l'exécution :

- Les données brutes sont stockées dans **LocalStack**.
- Les données nettoyées sont disponibles dans **MySQL**.
- Le modèle de Machine Learning enrichit les données.
- Les données finales sont stockées dans **MongoDB**.
- Les résultats peuvent être consultés via l'API **FastAPI**.
````

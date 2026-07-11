Ce projet met en œuvre un pipeline Data Lake basé sur l'architecture Raw → Staging → Curated à partir des données Ticketmaster.

Les différentes étapes sont orchestrées avec Apache Airflow.

Le pipeline effectue les opérations suivantes :

Ingestion des données Ticketmaster
Chargement dans MySQL (Staging)
Entraînement d'un modèle Machine Learning
Enregistrement des résultats dans MongoDB

Architecture:
Ticketmaster API
        │
        ▼
LocalStack (Raw)
        │
        ▼
MySQL (Staging)
        │
        ▼
Machine Learning
        │
        ▼
MongoDB (Curated)



Structure du projet
.
├── dags/
│   └── data_lake_pipeline.py
├── src/
│   ├── ingestion.py
│   ├── staging.py
│   ├── train_model.py
│   └── curated_ml.py
├── docker-compose.yml
├── pyproject.toml
└── README.md

Technologies utilisées
Python 3.12
Apache Airflow
Docker
Docker Compose
LocalStack
MySQL
MongoDB
uv

Installation

1- Cloner le projet:
git clone <url_du_repo>
cd projet-datalakes
 
2- Installer les dépendances : uv sync

3- Lancer Docker:  docker compose up -d
Vérifier les conteneurs: docker ps

4-Lancer Airflow :  uv run airflow standalone
Une interface est disponible sur -> http://localhost:8080


5- Exécuter le DAG:  Activer le DAG-> Trigger DAG
Les tâches s'exécutent dans l'ordre :

raw_ingestion
        ↓
staging_mysql
        ↓
train_ml_model
        ↓
curated_mongodb

# Mise en place du projet et étapes à suivre pour construire le Data Lake

## Pré-requis

Docker desktop
VsCode

## 1. Installation des libraires du projet

uv sync

## 2. Ingestion des données de l'API TicketMaster et du fichier externe de données de fréquentations touristiques

uv run src/ingestion.py

## 3. Nettoyage et préparation des données avec un base de données relationnelle MySQL

uv run src/staging.py

## 4. Entrainement du modèle pour enrichir les données nettoyées

uv run src/train_model.py

## 4. Données enrichies stockées dans une collection MongoDB

uv run src/curated_ml.py

## 6. Chargement de l'API

cd src
uv run uvicorn app:app --reload
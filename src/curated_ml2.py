import os
import pymysql
import joblib
import pandas as pd
from pymongo import MongoClient
from datetime import date, datetime
import json

# Configuration des bases de données
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3307,
    "user": "root",
    "password": "rootpassword",
    "database": "staging_ticketmaster",
    "cursorclass": pymysql.cursors.DictCursor
}

MONGO_URI = "mongodb://admin:adminpassword@localhost:27017/"
MONGO_DB = "curated_datalake"
MONGO_COLLECTION = "events_curated"

def convert_dates(obj):
    """Convertit les types temporels en chaînes ISO pour MongoDB."""
    for key, value in obj.items():
        if isinstance(value, (date, datetime)):
            obj[key] = value.isoformat()
    return obj

def main():
    print("🚀 Démarrage de la couche CURATED (Machine Learning & MongoDB)...")
    
    # 1. Vérification et chargement du modèle Random Forest
    model_path = "models/rf_popularity.joblib"
    ref_path = "models/drift_reference.csv"
    
    if not os.path.exists(model_path) or not os.path.exists(ref_path):
        print("⚠️ Modèle introuvable. Lancement automatique de l'entraînement d'abord...")
        from train_model import train_rf_model
        train_rf_model()
        
    model = joblib.load(model_path)
    df_ref = pd.read_csv(ref_path)

    # 2. Lecture des données de Staging depuis MySQL
    mysql_conn = pymysql.connect(**MYSQL_CONFIG)
    
    query_events = """
        SELECT
            e.id AS event_id,
            e.name AS event_name,
            e.type AS event_type,
            e.url AS event_url,
            e.local_date,
            v.id AS venue_id,
            v.name AS venue_name,
            v.city,
            v.country,
            v.postal_code,
            v.timezone
        FROM events e
        LEFT JOIN venues v ON e.venue_id = v.id
        LIMIT 1200;
    """
    
    with mysql_conn.cursor() as cursor:
        cursor.execute(query_events)
        events = cursor.fetchall()

        # Extraction du profil touristique de la dernière année connue (ex: 2008)
        query_latest_tourism = """
            SELECT AVG(tourism_value) AS market_avg, MAX(tourism_value) AS market_max
            FROM tourism_history 
            WHERE year = (SELECT MAX(year) FROM tourism_history);
        """
        cursor.execute(query_latest_tourism)
        latest_tourism = cursor.fetchone()

    mysql_conn.close()

    if not events:
        print("❌ Aucun événement trouvé dans le Staging MySQL. Fin du script.")
        return

    # Extraction des valeurs contextuelles de l'année de référence (Constantes de contexte économique)
    market_avg_raw = float(latest_tourism["market_avg"] or 0)
    market_max_raw = float(latest_tourism["market_max"] or 0)

    # Charger les bornes sauvegardées lors du training (obligatoire pour cohérence)
    with open("models/norm_params.json", "r") as f:
        norm_params = json.load(f)
    # Passer les features BRUTES au modèle — le modèle a été entraîné sur les valeurs brutes
    # La normalisation est faite DANS la fonction de génération des targets, pas dans les features X
    # Donc on passe market_avg et market_max RAW, exactement comme lors du fit()
    market_avg = market_avg_raw
    market_max = market_max_raw

    # 3. Préparation de la matrice d'Inférence (Features de 2026)
    features_2026_list = []
    for ev in events:
        month_str = "1"
        if ev["local_date"]:
            month_str = str(ev["local_date"].month)
            
        features_2026_list.append({
            "event_type": ev["event_type"],
            "event_month": month_str,
            "market_avg": market_avg,
            "market_max": market_max
        })
        
    df_features_2026 = pd.DataFrame(features_2026_list)

    # --- CONTROLE DU DATA DRIFT ---
    ref_types = set(df_ref["event_type"].unique())
    current_types = set(df_features_2026["event_type"].unique())
    new_categories = current_types - ref_types
    
    drift_status = "DRIFT_DETECTED" if len(new_categories) > 0 else "PASSED"
    psi_score_simulated = 0.22 if drift_status == "DRIFT_DETECTED" else 0.03
    print(f"📊 Vérification du Data Drift : Statut = {drift_status} (Score PSI simulé : {psi_score_simulated})")

    # 4. Inférence (Calcul des prédictions dynamiques par le Random Forest)
    print("🌲 Calcul des scores de popularité personnalisés via le Random Forest...")
    predicted_scores = model.predict(df_features_2026)

    # 5. Dénormalisation et assemblage des documents JSON
    documents = []
    for idx, event in enumerate(events):
        event = convert_dates(event)
        
        documents.append({
            "_id": event["event_id"],  
            "event_name": event["event_name"],
            "event_type": event["event_type"],
            "event_url": event["event_url"],
            "local_date": event["local_date"],
            "venue": {
                "venue_id": event["venue_id"],
                "venue_name": event["venue_name"],
                "city": event["city"],
                "country": event["country"],
                "postal_code": event["postal_code"],
                "timezone": event["timezone"],
            },
            "machine_learning": {
                "model_version": "v1.0-random-forest",
                "data_drift_status": drift_status,
                "psi_score": psi_score_simulated,
                "predicted_popularity_score": round(float(predicted_scores[idx]), 1),
                "interpretation": "Score prédictif calculé par IA basé sur les caractéristiques de l'événement projetées sur le profil de maturité du marché."
            }
        })

    # 6. Envoi et persistance dans MongoDB
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[MONGO_DB]
    collection = db[MONGO_COLLECTION]

    collection.delete_many({})  
    if documents:
        collection.insert_many(documents)

    mongo_client.close()
    print(f"✅ {len(documents)} événements enrichis par le Random Forest insérés dans MongoDB.")
    print("🏁 Couche CURATED terminée avec succès.")

if __name__ == "__main__":
    main()
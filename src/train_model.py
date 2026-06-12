import os
import polars as pl
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import random

# Utilisation de la chaîne de connexion SQLAlchemy (compatible avec Polars pour read_database)
SQLALCHEMY_URL = "mysql://root:rootpassword@localhost:3307/staging_ticketmaster"

def train_rf_model():
    print("🧠 [ML TRAINING] Connexion à la base MySQL Staging via Polars...")
    
    # 1. On résume le tourisme historique : 1 ligne par année avec des indicateurs globaux
    query_tourism = """
        SELECT year, 
               AVG(tourism_value) as market_avg,
               MAX(tourism_value) as market_max
        FROM tourism_history
        GROUP BY year;
    """
    # Polars accepte directement l'URI sous forme de chaîne de caractères
    df_tourism = pl.read_database_uri(query_tourism, uri=SQLALCHEMY_URL)
    
    # 2. On récupère les types d'événements disponibles pour calquer la structure d'apprentissage
    query_events = """
        SELECT type as event_type, MONTH(local_date) as event_month FROM events;
    """
    df_events = pl.read_database_uri(query_events, uri=SQLALCHEMY_URL)

    if df_tourism.is_empty() or df_events.is_empty():
        print("❌ Erreur : Les tables 'tourism_history' ou 'events' sont vides dans MySQL.")
        return

    print("📊 [ML TRAINING] Génération du jeu de données d'apprentissage (1973-2008)...")
    records = []
    
    # On fait croiser les structures d'événements avec toutes les années économiques du passé
    for year_row in df_tourism.iter_rows(named=True):
        for event_row in df_events.iter_rows(named=True):
            if not event_row["event_month"]:
                continue
                
            # Règle métier empirique (La cible Y à faire apprendre au modèle)
            # 1. On corrige la détection du type d'événement
            # (Assure-toi que ton SELECT SQL récupère bien le vrai type et pas juste une constante)
            # --- NOUVELLES RÈGLES MÉTIERS ALIGNÉES SUR TICKETMASTER ---
            if event_row["event_type"] == "sports":
                base = 45  # Le sport attire généralement de grandes foules régulières
            elif event_row["event_type"] == "music":
                base = 40  # Les concerts et festivals ont une forte attractivité
            elif event_row["event_type"] == "arts & theatre":
                base = 30  # Public plus de niche mais très fidèle
            elif event_row["event_type"] == "none":
                base = 15  # Événements non classés ou inconnus (attractivité faible par défaut)
            else:
                base = 20  # Cas de secours (fallback) si un autre type apparaît

            # --- BONUS SAISONNIER SUBTIL (Par mois) ---
            month = int(event_row["event_month"])
            if month in [6, 7, 8]:  # Juin, Juillet, Août (Haute saison)
                if event_row["event_type"] == "music":
                    base += 20  # 🎸 Gros bonus été pour la musique (Saison des festivals)
                else:
                    base += 12  # Bonus estival standard pour les autres événements
            elif month in [5, 9]:   # Mai, Septembre (Moyenne saison)
                base += 6

            # 2. On ajuste l'impact touristique à la baisse pour compenser les grandes valeurs (ex: 92 000)
            # Diviser par 2500 ou 3000 permet d'obtenir un impact maximal d'environ 30 à 40 points au lieu de 60+.
            market_impact = (year_row["market_avg"] / 2800) 

            # 3. On ajoute une dose de variabilité aléatoire (bruit)
            noise = random.uniform(-15.0, 15.0)

            # 4. Calcul final mieux réparti
            popularity_target = base + market_impact + noise
            popularity_target = min(100.0, max(10.0, popularity_target))
            
            records.append({
                "event_type": event_row["event_type"],
                "event_month": str(int(event_row["event_month"])),
                "market_avg": float(year_row["market_avg"]),
                "market_max": float(year_row["market_max"]),
                "target_popularity": float(popularity_target)
            })
            
    df_train = pl.DataFrame(records)
    
    # Séparation Features (X) et Cible (y)
    X = df_train.select(["event_type", "event_month", "market_avg", "market_max"]).to_pandas()
    y = df_train["target_popularity"].to_pandas()
    
    # 3. Pipeline de Preprocessing (One-Hot Encoding pour le texte) + Modèle Regressor
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["event_type", "event_month"])
        ],
        remainder="passthrough"
    )
    
    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("regressor", RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42))
    ])
    
    print("🌲 [ML TRAINING] Entraînement du modèle Random Forest...")
    pipeline.fit(X, y)
    
    # Évaluation rapide sur le set d'entraînement
    r2_score = pipeline.score(X, y)
    print(f"✅ Modèle entraîné avec succès. Indice de performance $R^2$ : {r2_score:.4f}")
    
    # 4. Sauvegarde physique du modèle et des features pour le calcul du Data Drift
    os.makedirs("models", exist_ok=True)
    joblib.dump(pipeline, "models/rf_popularity.joblib")
    X.to_csv("models/drift_reference.csv", index=False)
    print("💾 Modèle enregistré dans 'models/rf_popularity.joblib'.\n")

if __name__ == "__main__":
    train_rf_model()
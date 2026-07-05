import os
import polars as pl
import joblib
import numpy as np
import random
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

SQLALCHEMY_URL = "mysql://root:rootpassword@localhost:3307/staging_ticketmaster"

def train_rf_model():
    print("🧠 [ML TRAINING] Connexion à la base MySQL Staging via Polars...")

    query_tourism = """
        SELECT year,
               AVG(tourism_value) as market_avg,
               MAX(tourism_value) as market_max
        FROM tourism_history
        GROUP BY year;
    """
    df_tourism = pl.read_database_uri(query_tourism, uri=SQLALCHEMY_URL)

    query_events = """
        SELECT type as event_type, MONTH(local_date) as event_month FROM events;
    """
    df_events = pl.read_database_uri(query_events, uri=SQLALCHEMY_URL)

    if df_tourism.is_empty() or df_events.is_empty():
        print("❌ Erreur : Les tables sont vides.")
        return

    # ✅ FIX 1 : Calculer les bornes de normalisation sur les données réelles
    # On utilise le percentile 95 comme plafond pour ne pas se faire écraser par les outliers
    market_avg_values = df_tourism["market_avg"].to_list()
    market_avg_values.sort()
    p95_idx = int(len(market_avg_values) * 0.95)
    MARKET_AVG_NORM_MAX = market_avg_values[p95_idx]  # ex: ~500 000
    MARKET_AVG_NORM_MAX = max(MARKET_AVG_NORM_MAX, 1.0)  # garde-fou

    market_max_values = df_tourism["market_max"].to_list()
    market_max_values.sort()
    p95_idx_max = int(len(market_max_values) * 0.95)
    MARKET_MAX_NORM_MAX = market_max_values[p95_idx_max]
    MARKET_MAX_NORM_MAX = max(MARKET_MAX_NORM_MAX, 1.0)

    print(f"📐 Normalisation : market_avg_p95={MARKET_AVG_NORM_MAX:.0f} | market_max_p95={MARKET_MAX_NORM_MAX:.0f}")

    print("📊 [ML TRAINING] Génération du jeu de données d'apprentissage...")
    records = []

    for year_row in df_tourism.iter_rows(named=True):
        for event_row in df_events.iter_rows(named=True):
            if not event_row["event_month"]:
                continue

            # Base par type
            # Règles métier alignées sur les vrais types MySQL
            if event_row["event_type"] == "sports":
                base = 45
            elif event_row["event_type"] == "arts & theatre":
                base = 30
            elif event_row["event_type"] == "music":
                base = 55
            elif event_row["event_type"] == "miscellaneous":
                base = 20
            else:
                base = 15  # garde-fou au cas où un nouveau type apparaît un jour

            # ✅ Bonus saisonnier UNIQUEMENT pour les types classifiés (pas "none")
            if event_row["event_type"] != "miscellaneous":
                month = int(event_row["event_month"])
                if month in [6, 7, 8]:
                    base += 20 if event_row["event_type"] == "music" else 12
                elif month in [5, 9]:
                    base += 6
                elif month in [12, 1, 2]:
                    base -= 4  # léger malus hiver pour les classifiés aussi

            # Malus hiver pour "miscellaneous" (remplace l'ancien bloc séparé)
            if event_row["event_type"] == "miscellaneous":
                month = int(event_row["event_month"])
                if month in [12, 1, 2]:
                    base -= 5  # base 12 - 5 = 7 en hiver
                elif month in [6, 7, 8]:
                    base += 3  # petit bonus été mais plafonné, max = 15


            # ✅ FIX 2 : market_avg normalisé entre 0 et 1, contribution max = 15 pts
            market_avg_norm = min(year_row["market_avg"] / MARKET_AVG_NORM_MAX, 1.0)
            market_impact = market_avg_norm * 15.0

            # ✅ FIX 3 : Bruit élargi pour créer une vraie distribution
            noise = random.uniform(-18.0, 18.0)

            popularity_target = base + market_impact + noise

            # ✅ FIX 4 : Plafond à 95 (pas 100) pour éviter le clustering au max
            popularity_target = min(95.0, max(5.0, popularity_target))

            records.append({
                "event_type": event_row["event_type"],
                "event_month": str(int(event_row["event_month"])),
                "market_avg": float(year_row["market_avg"]),
                "market_max": float(year_row["market_max"]),
                "target_popularity": float(popularity_target)
            })

    df_train = pl.DataFrame(records)
    # Séparation Features / Cible — inchangé
    X = df_train.select(["event_type", "event_month", "market_avg", "market_max"]).to_pandas()
    y = df_train["target_popularity"].to_pandas()

    # Poids par type d'événement
    type_weights = {
    "sports":         0.6,
    "arts & theatre": 1.2,
    "music":          2.5,
    "miscellaneous":  1.8,
    }
    sample_weights = X["event_type"].map(type_weights).fillna(1.0).values

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
    # ✅ Passage des sample_weight via le nom de l'étape dans le Pipeline
    pipeline.fit(X, y, regressor__sample_weight=sample_weights)

    r2_score = pipeline.score(X, y)
    print(f"✅ Modèle entraîné. R² = {r2_score:.4f}")

    os.makedirs("models", exist_ok=True)
    joblib.dump(pipeline, "models/rf_popularity.joblib")
    X.to_csv("models/drift_reference.csv", index=False)

    # ✅ FIX 5 : Sauvegarder les bornes de normalisation pour curated.py
    norm_params = {
        "market_avg_norm_max": MARKET_AVG_NORM_MAX,
        "market_max_norm_max": MARKET_MAX_NORM_MAX
    }
    import json
    with open("models/norm_params.json", "w") as f:
        json.dump(norm_params, f)
    print(f"💾 Paramètres de normalisation sauvegardés dans 'models/norm_params.json'.")

    # Validation rapide post-training
    import pandas as pd
    test_cases = pd.DataFrame([
        {"event_type": "music",         "event_month": "7",  "market_avg": 100000, "market_max": 500000},
        {"event_type": "sports",        "event_month": "3",  "market_avg": 50000,  "market_max": 200000},
        {"event_type": "arts & theatre","event_month": "11", "market_avg": 20000,  "market_max": 80000},
        {"event_type": "miscellaneous", "event_month": "1",  "market_avg": 5000,   "market_max": 20000},
    ])
    preds = pipeline.predict(test_cases)
    for i, row in test_cases.iterrows():
        print(f"   {row['event_type']:20s} | mois {row['event_month']:>2s} → score prédit : {preds[i]:.1f}")


if __name__ == "__main__":
    train_rf_model()

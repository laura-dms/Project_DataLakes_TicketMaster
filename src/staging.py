import json
import os
import boto3
import polars as pl
from botocore.client import Config
from sqlalchemy import create_engine, text

# --- CONFIGURATION ---
LOCALSTACK_ENDPOINT = "http://localhost:4566"
BUCKET_NAME = "my-data-lake"

# Structure : mysql://USER:PASSWORD@HOST:PORT/DATABASE
SQLALCHEMY_URL = "mysql+pymysql://root:rootpassword@localhost:3307/staging_ticketmaster"


def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1',
        config=Config(s3={'addressing_style': 'path'})
    )


def init_mysql_tables():
    """Crée les tables SQL en s'assurant que les IDs respectent strictement la casse (Case Sensitive)."""
    print("1. Initialisation du schéma de base de données MySQL...")
    engine = create_engine(SQLALCHEMY_URL)
    with engine.begin() as conn:
        conn.execute(text("SET GLOBAL max_allowed_packet = 1073741824;"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        # Nettoyage pour garantir le re-run sans crash
        conn.execute(text("DROP TABLE IF EXISTS prices;"))
        conn.execute(text("DROP TABLE IF EXISTS events;"))
        conn.execute(text("DROP TABLE IF EXISTS venues;"))
        conn.execute(text("DROP TABLE IF EXISTS tourism_history;"))

        # --- AJOUT DE CHARACTER SET utf8mb4 COLLATE utf8mb4_bin ---
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS venues (
                id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin PRIMARY KEY,
                name VARCHAR(255),
                type VARCHAR(50),
                url TEXT,
                city VARCHAR(100),
                country VARCHAR(100),
                postal_code VARCHAR(50),
                timezone VARCHAR(50)
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS events (
                id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin PRIMARY KEY,
                name VARCHAR(255),
                type VARCHAR(50),
                url TEXT,
                local_date DATE,
                venue_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
                FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE SET NULL
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_id VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
                type VARCHAR(50),
                min_price DECIMAL(10, 2),
                max_price DECIMAL(10, 2),
                currency VARCHAR(10),
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tourism_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                series_name VARCHAR(100),
                year INT,
                tourism_value DECIMAL(15, 4)
            );
        """))
        
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    print("Schéma MySQL prêt (avec support Case-Sensitive pour Ticketmaster).")


def parse_and_load_ticketmaster(s3_client):
    """Télécharge le fichier JSON unique d'événements, extrait tout le réel (y compris les prix) et écrit dans MySQL."""
    print("2. Extraction et transformation des données Ticketmaster (Fichier unique) avec Polars...")
    
    try:
        obj_events = s3_client.get_object(Bucket=BUCKET_NAME, Key="raw/ticketmaster/events_raw.json")
        raw_data = json.loads(obj_events['Body'].read().decode('utf-8'))
        events_list = raw_data.get('_embedded', {}).get('events', [])
    except Exception as e:
        print(f"Impossible de lire events_raw.json de S3 : {e}")
        return

    venues_data = []
    events_data = []
    prices_data = []

    for ev in events_list:
        # 1. Extraction de la Venue (Salle)
        venues_list = ev.get('_embedded', {}).get('venues', [])
        venue_id = None
        if venues_list:
            v = venues_list[0]
            venue_id = v.get('id')
            if venue_id:
                venues_data.append({
                    "id": str(venue_id),
                    "name": v.get('name'),
                    "type": v.get('type'),
                    "url": v.get('url'),
                    "city": v.get('city', {}).get('name'),
                    "country": v.get('country', {}).get('name'),
                    "postal_code": v.get('postalCode'),
                    "timezone": v.get('timezone')
                })

        # 2. Extraction de l'Événement
        event_id = ev.get('id')
        if event_id:
            classifications = ev.get('classifications', [])
            true_type = "none" # Valeur par défaut si non spécifié
            
            if classifications and isinstance(classifications, list):
                segment = classifications[0].get('segment', {})
                if segment and segment.get('name'):
                    # On extrait le nom et on le passe en minuscules (ex: "sports", "music")
                    true_type = str(segment.get('name')).lower()

            events_data.append({
                "id": str(event_id),
                "name": ev.get('name'),
                "type": true_type,
                "url": ev.get('url'),
                "local_date": ev.get('dates', {}).get('start', {}).get('localDate'),
                "venue_id": str(venue_id) if venue_id else None
            })

            # 3. Extraction STREECTEMENT RÉELLE des prix (directement depuis l'événement)
            # Si le champ 'priceRanges' n'existe pas, on ignore l'insertion pour cet event_id
            if "priceRanges" in ev:
                for p in ev["priceRanges"]:
                    prices_data.append({
                        "event_id": str(event_id),
                        "type": p.get('type', 'standard'),
                        "min_price": float(p['min']) if p.get('min') is not None else None,
                        "max_price": float(p['max']) if p.get('max') is not None else None,
                        "currency": p.get('currency', 'USD')
                    })

    # Conversion en DataFrames Polars uniques
    # Conversion et nettoyage strict des doublons
    df_venues = pl.DataFrame(venues_data).unique(subset=["id"]) if venues_data else pl.DataFrame()
    
    if events_data:
        df_events = pl.DataFrame(events_data).unique(subset=["id"])
    else:
        df_events = pl.DataFrame()
        
    df_prices = pl.DataFrame(prices_data) if prices_data else pl.DataFrame()

    # Cast de la colonne date au bon format
    if not df_events.is_empty():
        df_events = df_events.with_columns(pl.col("local_date").str.to_date("%Y-%m-%d", strict=False))
        
    # Injection SQL via sqlalchemy - AJOUT DE chunksize=200 ---
    if not df_venues.is_empty():
        df_venues.write_database(
            table_name="venues", 
            connection=SQLALCHEMY_URL, 
            if_table_exists="append", 
            engine="sqlalchemy",
            engine_options={"chunksize": 200}
        )
        print(f"   -> {df_venues.height} salles insérées dans 'venues'.")

    if not df_events.is_empty():
        df_events.write_database(
            table_name="events", 
            connection=SQLALCHEMY_URL, 
            if_table_exists="append", 
            engine="sqlalchemy",
            engine_options={"chunksize": 200}
        )
        print(f"   -> {df_events.height} événements insérés dans 'events'.")

    if not df_prices.is_empty():
        df_prices.write_database(
            table_name="prices", 
            connection=SQLALCHEMY_URL, 
            if_table_exists="append", 
            engine="sqlalchemy",
            engine_options={"chunksize": 200}  # Découpe l'envoi
        )
        print(f"   -> {df_prices.height} grilles de prix réelles insérées dans 'prices'.")
    else:
        print("   ->Aucune grille de prix réelle trouvée dans le fichier, la table 'prices' restera vide.")


def parse_and_load_tourism(s3_client):
    """Télécharge le fichier TSF, isole la section @data et extrait l'année de start_timestamp."""
    print("3. Extraction et parsing du fichier Tourisme .tsf adapté aux spécificités...")
    
    try:
        obj_tsf = s3_client.get_object(Bucket=BUCKET_NAME, Key="raw/monash_tourism/tourism_yearly_dataset.tsf")
        tsf_lines = obj_tsf['Body'].read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"Impossible de lire le fichier TSF sur S3 : {e}")
        return

    records = []
    is_data_section = False
    
    for line in tsf_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("@data"):
            is_data_section = True
            continue
        
        if is_data_section:
            parts = line.split(":")
            if len(parts) >= 3:
                series_name = parts[0]
                start_timestamp_str = parts[1].strip()
                try:
                    start_year = int(start_timestamp_str[:4])
                except ValueError:
                    continue
                
                values_str = parts[2].replace("?", "None")
                values = [float(v) for v in values_str.split(",") if v.strip() and v != "None"]
                
                for idx, val in enumerate(values):
                    records.append({
                        "series_name": series_name,
                        "year": start_year + idx,
                        "tourism_value": val
                    })

    df_tourism = pl.DataFrame(records)
    if not df_tourism.is_empty():
        df_tourism.write_database(
            table_name="tourism_history", 
            connection=SQLALCHEMY_URL, 
            if_table_exists="append", 
            engine="sqlalchemy",
            engine_options={"chunksize": 200}
        )
        print(f"   -> {df_tourism.height} lignes chargées dans 'tourism_history' (518 séries temporelles intégrées).")


def main():
    s3_client = get_s3_client()
    
    print("Démarrage du pipeline de STAGING (Moteur : POLARS)...")
    init_mysql_tables()
    parse_and_load_ticketmaster(s3_client)
    parse_and_load_tourism(s3_client)
    print("Fin de l'étape Staging MySQL.")


if __name__ == "__main__":
    main()
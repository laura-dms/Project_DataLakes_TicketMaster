import os
import json
import requests
import boto3
from botocore.client import Config

# --- CONFIGURATION ---
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "Gp9H78beEUEtDsYFVkVlOAaMnbJnPlSo")
LOCALSTACK_ENDPOINT = "http://localhost:4566"
BUCKET_NAME = "my-data-lake"
LOCAL_TSF_PATH = "tourism_yearly_dataset/tourism_yearly_dataset.tsf"


def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1',
        config=Config(s3={'addressing_style': 'path'})
    )


def clear_s3_bucket(s3_client):
    print(f"Rules 🧹 Nettoyage de la couche RAW : Vidage du bucket '{BUCKET_NAME}'...")
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        if 'Contents' in response:
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
            s3_client.delete_objects(Bucket=BUCKET_NAME, Delete={'Objects': objects_to_delete})
            print(f"   -> {len(objects_to_delete)} anciens fichiers supprimés du Data Lake.")
    except s3_client.exceptions.NoSuchBucket:
        pass


def ingest_local_zenodo_file(s3_client):
    print(f"📥 1. Lecture et conversion en UTF-8 du fichier local Tourisme ({LOCAL_TSF_PATH})...")
    if not os.path.exists(LOCAL_TSF_PATH):
        print(f"❌ Erreur : Le fichier est introuvable : {LOCAL_TSF_PATH}")
        return
    try:
        # 1. On lit le fichier local avec son encodage d'origine (cp1252)
        with open(LOCAL_TSF_PATH, 'r', encoding='cp1252', errors='replace') as f:
            file_text = f.read()
        
        # 2. On le convertit en bytes UTF-8 pour l'envoyer sur S3
        file_content_utf8 = file_text.encode('utf-8')
        
        # 3. Envoi sur LocalStack S3
        s3_client.put_object(
            Bucket=BUCKET_NAME, 
            Key="raw/monash_tourism/tourism_yearly_dataset.tsf", 
            Body=file_content_utf8
        )
        print("✅ Fichier local Zenodo converti en UTF-8 et poussé avec succès sur S3.")
    except Exception as e:
        print(f"❌ Échec de l'ingestion du fichier Zenodo : {e}")


def ingest_ticketmaster_data(s3_client):
    print("📥 2. Appel de l'API Ticketmaster (Collecte mondiale globale)...")
    url_search = "https://app.ticketmaster.com/discovery/v2/events.json"
    
    params = {"apikey": TICKETMASTER_API_KEY, "size": 200, "page": 0}
    all_events = []
    
    for page in range(6):
        print(f"   -> Récupération de la page {page}...")
        params["page"] = page
        try:
            response = requests.get(url_search, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            if "_embedded" in data and "events" in data["_embedded"]:
                events_page = data["_embedded"]["events"]
                all_events.extend(events_page)
                if len(events_page) < 200:
                    break
            else:
                break
        except Exception as e:
            print(f"⚠️ Fin de pagination ou restriction de profondeur atteinte à la page {page}.")
            break

    print(f"✅ {len(all_events)} événements de base récupérés.")

    # --- SÉLECTION EXCLUSIVEMENT RÉELLE DES PRIX ---
    print("🔄 3. Extraction des grilles tarifaires réelles...")
    prices_details = {}
    real_api_prices = 0
    
    for target_event in all_events:
        event_id = target_event.get('id')
        if not event_id:
            continue
            
        # On ne prend QUE si l'API Ticketmaster a fourni un vrai tableau 'priceRanges'
        if "priceRanges" in target_event:
            prices_details[event_id] = target_event["priceRanges"]
            real_api_prices += 1

    # Sauvegarde stricte sur LocalStack S3
    raw_output = {"_embedded": {"events": all_events}}
    s3_client.put_object(
        Bucket=BUCKET_NAME, 
        Key="raw/ticketmaster/events_raw.json", 
        Body=json.dumps(raw_output, indent=2, ensure_ascii=False).encode('utf-8')
    )
    
    print(f"📊 Bilan strict des prix : {real_api_prices} événements ont de vrais tarifs sur les {len(all_events)} récupérés.")
    print("✅ Données brutes réelles synchronisées sur S3.")


def main():
    s3_client = get_s3_client()
    try:
        s3_client.create_bucket(Bucket=BUCKET_NAME)
    except (s3_client.exceptions.BucketAlreadyExists, s3_client.exceptions.BucketAlreadyOwnedByYou):
        pass

    print("🚀 Démarrage du pipeline d'ingestion (Couche RAW - Pure Réel)...")
    clear_s3_bucket(s3_client)
    ingest_local_zenodo_file(s3_client)
    ingest_ticketmaster_data(s3_client)
    print("🏁 Fin de l'étape Ingestion RAW.")


if __name__ == "__main__":
    main()
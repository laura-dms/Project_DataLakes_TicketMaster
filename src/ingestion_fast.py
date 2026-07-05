import os
import json
import requests
import boto3
from botocore.client import Config
from concurrent.futures import ThreadPoolExecutor # 👈 Pour le multi-threading

TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "Gp9H78beEUEtDsYFVkVlOAaMnbJnPlSo")
LOCALSTACK_ENDPOINT = "http://localhost:4566"
BUCKET_NAME = "my-data-lake"
LOCAL_TSF_PATH = "tourism_yearly_dataset/tourism_yearly_dataset.tsf"

def get_s3_client():
    return boto3.client('s3', endpoint_url=LOCALSTACK_ENDPOINT, aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1', config=Config(s3={'addressing_style': 'path'}))

def fetch_page(page):
    """Fonction travailleur pour télécharger une seule page."""
    url_search = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {"apikey": TICKETMASTER_API_KEY, "size": 200, "page": page}
    try:
        response = requests.get(url_search, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("_embedded", {}).get("events", [])
    except Exception:
        return []

def main():
    s3_client = get_s3_client()
    
    # 1. Ingestion parallèle de Ticketmaster (6 pages en même temps)
    all_events = []
    pages_to_fetch = list(range(6))
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = executor.map(fetch_page, pages_to_fetch)
        for events_page in results:
            all_events.extend(events_page)

    # Sauvegarde sur S3
    raw_output = {"_embedded": {"events": all_events}}
    s3_client.put_object(
        Bucket=BUCKET_NAME, 
        Key="raw/ticketmaster/events_raw.json", 
        Body=json.dumps(raw_output, indent=2, ensure_ascii=False).encode('utf-8')
    )
    
    # 2. Ingestion rapide du fichier local Tourisme (on évite de décoder/recoder si inchangé)
    if os.path.exists(LOCAL_TSF_PATH):
        with open(LOCAL_TSF_PATH, 'rb') as f: # Lecture en binaire direct (plus rapide)
            s3_client.put_object(Bucket=BUCKET_NAME, Key="raw/monash_tourism/tourism_yearly_dataset.tsf", Body=f.read())

if __name__ == "__main__":
    main()
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.openapi.docs import get_swagger_ui_html 
from fastapi.responses import HTMLResponse
from typing import List, Optional
import pymysql
from pymongo import MongoClient
import boto3
from botocore.client import Config
import time
import subprocess

# 1. On instancie l'application une seule fois et on désactive la doc standard
app = FastAPI(
    title="Ticketmaster Data Lake API",
    description="API FastAPI pour accéder aux couches Ingestion (S3), Staging (MySQL) et Curated (MongoDB)",
    version="1.0.0",
    docs_url=None, 
    redoc_url=None
)

# 2. Injection du CSS personnalisé style Ticketmaster Dark Edition
CSS_TICKETMASTER = """
<style>
    /* Fond général et police */
    body, .swagger-ui {
        background-color: #0a1128 !important;
        color: #ffffff !important;
        font-family: 'Avenir Next', 'Segoe UI', Helvetica, Arial, sans-serif;
    }
    
    /* En-tête / Topbar */
    .swagger-ui .topbar {
        background-color: #026cdf !important; /* Bleu Ticketmaster */
        box-shadow: 0 4px 12px rgba(2, 108, 223, 0.2);
    }
    
    /* Titres et textes de description généraux (Haut de page) */
    .swagger-ui .info .title, .swagger-ui .info p, .swagger-ui .info li, .swagger-ui .info a {
        color: #ffffff !important;
    }
    
    /* ==========================================
       FIX LISIBILITÉ TEXTES INTERNES ET EXTERNES
       ========================================== */
       
    /* 1. Descriptions principales des routes */
    .swagger-ui .opblock .opblock-summary-description {
        color: #f8fafc !important;
        font-weight: 500 !important;
    }
    
    /* 2. Chemins des routes */
    .swagger-ui .opblock .opblock-summary-path {
        color: #ffffff !important;
    }
    
    /* 3. Texte d'explication à l'intérieur d'un endpoint déplié */
    .swagger-ui .opblock-body .opblock-description-wrapper p {
        color: #f8fafc !important;
        font-size: 14px !important;
    }
    
    /* 4. Textes d'indications vides */
    .swagger-ui .opblock-body .opblock-description-wrapper + div h4,
    .swagger-ui .opblock-body em,
    .swagger-ui .response-col_links {
        color: #cbd5e1 !important;
    }
    
    /* 5. En-têtes de colonnes des tableaux */
    .swagger-ui .parameters-header .col_header,
    .swagger-ui .responses-header .col_header {
        color: #ffffff !important;
        font-weight: bold !important;
    }
    
    /* 6. Descriptions des codes de réponses */
    .swagger-ui .response-col_description .response-col_description__inner div,
    .swagger-ui .response-col_status {
        color: #f8fafc !important;
    }
    
    /* ========================================== */
    
    /* Blocs d'endpoints (Général) */
    .swagger-ui .opblock-tag {
        color: #026cdf !important;
        border-bottom: 2px solid #026cdf !important;
        font-size: 1.3rem;
    }
    
    .swagger-ui .opblock {
        background-color: #101f42 !important;
        border: 1px solid #1e356e !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
    }
    
    /* Boutons et verbes HTTP (GET) */
    .swagger-ui .opblock.opblock-get {
        border-color: #026cdf !important;
    }
    .swagger-ui .opblock.opblock-get .opblock-summary-method {
        background-color: #026cdf !important;
        color: white !important;
        border-radius: 4px;
    }
    .swagger-ui .opblock.opblock-get .opblock-summary {
        background-color: rgba(2, 108, 223, 0.08) !important;
    }
    
    /* Tableaux, paramètres et sous-titres */
    .swagger-ui section.models h4, .swagger-ui .parameter__name {
        color: #ffffff !important;
    }
    .swagger-ui .tabli button {
        color: #a0aec0 !important;
    }
    .swagger-ui .tabli.active button {
        color: #026cdf !important;
    }
    .swagger-ui table thead tr td, .swagger-ui table thead tr th {
        color: #ffffff !important;
        border-bottom: 1px solid #1e356e !important;
    }
    
    /* Inputs et champs texte */
    .swagger-ui input[type=text], .swagger-ui select {
        background-color: #0a1128 !important;
        color: white !important;
        border: 1px solid #1e356e !important;
        border-radius: 4px;
    }
    
    /* Bouton Try it out */
    .swagger-ui .btn.try-out__btn {
        background-color: #026cdf !important;
        color: white !important;
        border: none !important;
    }
    .swagger-ui .btn.execute {
        background-color: #24b47e !important;
        color: white !important;
    }
</style>
"""

# 3. Route personnalisée robuste : injection directe dans la structure HTML de la réponse
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    # 1. On génère la réponse HTML standard fournie par FastAPI
    response = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Ticketmaster Style",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
    )
    
    # 2. On récupère le texte HTML brut de la réponse (.body est en bytes, on le décode)
    html_content = response.body.decode("utf-8")
    
    # 3. On injecte notre bloc <style> juste avant la fermeture de la balise </head>
    custom_html_content = html_content.replace("</head>", f"{CSS_TICKETMASTER}</head>")
    
    # 4. On renvoie le HTML modifié avec un code 200
    return HTMLResponse(content=custom_html_content, status_code=200)

# --- CONFIGURATIONS DES ACCÈS DOCKER---
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

LOCALSTACK_ENDPOINT = "http://localhost:4566"
BUCKET_NAME = "my-data-lake"

# --- UTILS / DEPENDENCIES ---
def get_mysql_conn():
    return pymysql.connect(**MYSQL_CONFIG)

def get_mongo_collection():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    return client, db[MONGO_COLLECTION]

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1',
        config=Config(s3={'addressing_style': 'path'})
    )

# --- 0. ENDPOINT DE SANTÉ (HEALTHCHECK) ---

@app.get("/health", tags=["0. Healthcheck"], summary="Vérifie l'état de santé du Data Lake et des bases de données")
def health_check():
    """
    Vérifie en temps réel la connectivité avec LocalStack (S3), MySQL et MongoDB.
    Retourne un statut global 'healthy' ou 'unhealthy' avec le détail par service.
    """
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "s3_localstack": {"status": "unknown"},
            "mysql_staging": {"status": "unknown"},
            "mongodb_curated": {"status": "unknown"}
        }
    }
    
    # 1. Vérification S3 (LocalStack)
    try:
        s3 = get_s3_client()
        # Une opération légère : lister les buckets existants pour vérifier la connectivité
        s3.list_buckets()
        health_status["services"]["s3_localstack"] = {"status": "up"}
    except Exception as e:
        health_status["services"]["s3_localstack"] = {"status": "down", "error": str(e)}
        health_status["status"] = "unhealthy"

    # 2. Vérification MySQL (Staging)
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            # Un ping SQL ultra léger pour vérifier la connectivité
            cursor.execute("SELECT 1;")
        conn.close()
        health_status["services"]["mysql_staging"] = {"status": "up"}
    except Exception as e:
        health_status["services"]["mysql_staging"] = {"status": "down", "error": str(e)}
        health_status["status"] = "unhealthy"

    # 3. Vérification MongoDB (Curated)
    try:
        mongo_client, _ = get_mongo_collection()
        # Vérification avec ping pour s'assurer que le serveur MongoDB répond
        mongo_client.admin.command('ping')
        mongo_client.close()
        health_status["services"]["mongodb_curated"] = {"status": "up"}
    except Exception as e:
        health_status["services"]["mongodb_curated"] = {"status": "down", "error": str(e)}
        health_status["status"] = "unhealthy"

    # Si l'un des services est down, on lève une HTTPException 503 (Service Unavailable)
    # tout en renvoyant le détail pour aider au debug.
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status

# --- 1. ENDPOINTS COUCHE : INGESTION (RAW - S3) ---

@app.get("/ingestion/files", tags=["1. Ingestion (Raw)"], summary="Liste les fichiers bruts stockés dans S3")
def list_raw_files():
    """Retourne la liste des objets présents dans le bucket S3 LocalStack."""
    s3 = get_s3_client()
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME)
        if 'Contents' in response:
            return {"bucket": BUCKET_NAME, "files": [obj['Key'] for obj in response['Contents']]}
        return {"bucket": BUCKET_NAME, "files": [], "message": "Le bucket est vide."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur S3 : {str(e)}")


# --- 2. ENDPOINTS COUCHE : STAGING (SQL) ---

@app.get("/staging/events", tags=["2. Staging (MySQL)"], summary="Liste les événements nettoyés dans MySQL")
def get_staging_events(limit: int = Query(50, ge=1, le=200), event_type: Optional[str] = None):
    """Récupère les événements de la table MySQL avec jointure sur la salle (Venue)."""
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT e.id, e.name, e.type, e.local_date, v.name as venue_name, v.city, v.country 
                FROM events e
                LEFT JOIN venues v ON e.venue_id = v.id
            """
            params = []
            if event_type:
                query += " WHERE e.type = %s"
                params.append(event_type.lower())
            
            query += " LIMIT %s;"
            params.append(limit)
            
            cursor.execute(query, params)
            result = cursor.fetchall()
            return {"count": len(result), "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur MySQL : {str(e)}")
    finally:
        conn.close()

@app.get("/staging/prices", tags=["2. Staging (MySQL)"], summary="Consulte les grilles tarifaires réelles")
def get_staging_prices(event_id: str):
    """Retourne les tarifs associés à un ID d'événement spécifique."""
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cursor:
            query = "SELECT * FROM prices WHERE event_id = %s"
            cursor.execute(query, (event_id,))
            result = cursor.fetchall()
            if not result:
                raise HTTPException(status_code=404, detail=f"Aucun prix réel trouvé pour l'événement {event_id}")
            return {"event_id": event_id, "prices": result}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur MySQL : {str(e)}")
    finally:
        conn.close()


# --- 3. ENDPOINTS COUCHE : CURATED (NoSQL + ML) ---

@app.get("/curated/events", tags=["3. Curated (MongoDB)"], summary="Liste les événements enrichis par le Random Forest")
def get_curated_events(
    drift_status: Optional[str] = Query(None, description="Filtrer par statut de drift : PASSED ou DRIFT_DETECTED"),
    min_popularity: Optional[float] = Query(None, description="Score de popularité prédit minimum")
):
    """
    Récupère les documents JSON finaux depuis MongoDB.
    Permet de filtrer sur le statut du Data Drift et le score généré par le Random Forest (ML).
    """
    mongo_client, collection = get_mongo_collection()
    try:
        # Construction dynamique du filtre MongoDB
        query_filter = {}
        if drift_status:
            query_filter["machine_learning.data_drift_status"] = drift_status
        if min_popularity is not None:
            query_filter["machine_learning.predicted_popularity_score"] = {"$gte": min_popularity}

        # On exclut l'id natif MongoDB si on utilise déjà le code event_id en _id
        cursor = collection.find(query_filter).limit(100)
        events = list(cursor)
        
        return {"count": len(events), "data": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur MongoDB : {str(e)}")
    finally:
        mongo_client.close()

@app.get("/curated/events/{event_id}", tags=["3. Curated (MongoDB)"], summary="Détail complet d'un événement enrichi")
def get_curated_event_by_id(event_id: str):
    """Recherche un document unique par sa clé primaire dans MongoDB (qui correspond à l'ID Ticketmaster)."""
    mongo_client, collection = get_mongo_collection()
    try:
        event = collection.find_one({"_id": event_id})
        if not event:
            raise HTTPException(status_code=404, detail=f"Événement enrichi {event_id} introuvable dans la couche Curated.")
        return event
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur MongoDB : {str(e)}")
    finally:
        mongo_client.close()

# Variable globale temporaire pour stocker le temps de référence de /ingest : calculer le % de réduction dans /ingest_fast
baseline_duration = None

@app.post("/ingest", tags=["4. Benchmark du temps d'exécution de l'ingestion"], summary="Exécute l'ingestion Standard (Synchrone) et mesure le temps")
def run_standard_ingest():
    global baseline_duration
    start_time = time.time()
    
    try:
        # Exécute le script ingestion.py d'origine à l'aide de uv run
        result = subprocess.run(["uv", "run", "ingestion.py"], capture_output=True, text=True, check=True)
        
        duration = round(time.time() - start_time, 2)
        baseline_duration = duration # On sauvegarde le temps de référence
        
        return {
            "status": "success",
            "pipeline": "Standard (Synchrone)",
            "duration_seconds": duration,
            "message": "Le Data Lake (Couche Raw) a été rechargé de manière séquentielle."
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'exécution de l'ingestion : {e.stderr}")


@app.post("/ingest_fast", tags=["4. Benchmark du temps d'exécution de l'ingestion"], summary="Exécute l'ingestion Optimisée (Multi-threadée) et évalue le gain de performance")
def run_fast_ingest():
    global baseline_duration
    start_time = time.time()
    
    try:
        # Exécute le nouveau script optimisé
        result = subprocess.run(["uv", "run", "ingestion_fast.py"], capture_output=True, text=True, check=True)
        
        duration = round(time.time() - start_time, 2)
        
        # Calcul du pourcentage de réduction du temps de traitement
        performance_gain = None
        if baseline_duration and baseline_duration > 0:
            # Formule : ((Temps_Séquentiel - Temps_Parallèle) / Temps_Séquentiel) * 100
            reduction_percentage = ((baseline_duration - duration) / baseline_duration) * 100
            performance_gain = f"{round(reduction_percentage, 1)}% de réduction du temps"
        else:
            performance_gain = "Évaluation impossible. Veuillez exécuter le endpoint /ingest classique au moins une fois d'abord pour avoir un point de comparaison."

        return {
            "status": "success",
            "pipeline": "Optimisé (Multi-threadé)",
            "duration_seconds": duration,
            "baseline_reference_seconds": baseline_duration,
            "performance_evaluation": performance_gain,
            "message": "Le Data Lake (Couche Raw) a été rechargé en parallèle !"
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'exécution de l'ingestion rapide : {e.stderr}")

# --- ENDPOINT DES STATISTIQUES (VOLUMÉTRIE & METRICS) ---

@app.get("/stats", tags=["5. Statistiques Globales"], summary="Génère un état des lieux de la volumétrie du Data Lake")
def get_lake_statistics():
    """
    Scanne les 3 couches du Data Lake (Raw, Staging, Curated) pour compiler
    des indicateurs de volumétrie et de répartition des données.
    """
    stats = {
        "timestamp": time.time(),
        "couche_1_raw_s3": {},
        "couche_2_staging_mysql": {},
        "couche_3_curated_mongodb": {}
    }

    # ==========================================
    # 1. METRIQUES COUCHE 1 : RAW (S3 / LocalStack)
    # ==========================================
    try:
        s3 = get_s3_client()
        response = s3.list_objects_v2(Bucket=BUCKET_NAME)
        
        total_files = 0
        total_size_bytes = 0
        file_keys = []
        
        if 'Contents' in response:
            total_files = len(response['Contents'])
            file_keys = [obj['Key'] for obj in response['Contents']]
            total_size_bytes = sum(obj['Size'] for obj in response['Contents'])

        stats["couche_1_raw_s3"] = {
            "bucket_name": BUCKET_NAME,
            "total_files": total_files,
            "total_size_mb": round(total_size_bytes / (1024 * 1024), 3),
            "files_present": file_keys
        }
    except Exception as e:
        stats["couche_1_raw_s3"] = {"error": f"Impossible d'accéder à S3 : {str(e)}"}

    # ==========================================
    # 2. METRIQUES COUCHE 2 : STAGING (MySQL)
    # ==========================================
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cursor:
            # Récupération du nombre total de lignes par table
            tables = ["events", "venues", "prices", "tourism_history"]
            table_counts = {}
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) AS cnt FROM {table};")
                res = cursor.fetchone()
                table_counts[table] = res["cnt"] if res else 0

            # Répartion des événements par type (catégorie)
            cursor.execute("""
                SELECT type, COUNT(*) as count 
                FROM events 
                GROUP BY type 
                ORDER BY count DESC;
            """)
            type_distribution = {row["type"]: row["count"] for row in cursor.fetchall()}

        conn.close()
        
        stats["couche_2_staging_mysql"] = {
            "tables_volumetry": table_counts,
            "events_by_type": type_distribution,
            "total_stored_records": sum(table_counts.values())
        }
    except Exception as e:
        stats["couche_2_staging_mysql"] = {"error": f"Impossible d'accéder à MySQL : {str(e)}"}

    # ==========================================
    # 3. METRIQUES COUCHE 3 : CURATED (MongoDB)
    # ==========================================
    try:
        mongo_client, collection = get_mongo_collection()
        
        # Nombre total de documents enrichis
        total_curated_events = collection.count_documents({})
        
        # Pipeline d'agrégation pour obtenir :
        # - La répartition du statut de Data Drift
        # - Le score moyen de popularité prédit
        pipeline = [
            {
                "$group": {
                    "_id": "$machine_learning.data_drift_status",
                    "count": {"$sum": 1},
                    "avg_popularity": {"$avg": "$machine_learning.predicted_popularity_score"}
                }
            }
        ]
        
        aggregation_results = list(collection.aggregate(pipeline))
        mongo_client.close()

        drift_summary = {}
        avg_popularity_scores = {}
        
        for item in aggregation_results:
            status = item["_id"] or "UNKNOWN"
            drift_summary[status] = item["count"]
            avg_popularity_scores[status] = round(item["avg_popularity"], 2) if item["avg_popularity"] is not None else 0.0

        stats["couche_3_curated_mongodb"] = {
            "collection_name": collection.name,
            "total_enriched_events": total_curated_events,
            "data_drift_distribution": drift_summary,
            "average_predicted_popularity_by_drift": avg_popularity_scores
        }
    except Exception as e:
        stats["couche_3_curated_mongodb"] = {"error": f"Impossible d'accéder à MongoDB : {str(e)}"}

    return stats
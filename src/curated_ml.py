import pymysql
from pymongo import MongoClient
from datetime import date, datetime

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3307,
    "user": "root",
    "password": "rootpassword",
    "database": "staging_ticketmaster",
    "cursorclass": pymysql.cursors.DictCursor,
}

MONGO_URI = "mongodb://admin:adminpassword@localhost:27017/"
MONGO_DB = "curated_datalake"
MONGO_COLLECTION = "events_curated"


def convert_dates(obj):
    for key, value in obj.items():
        if isinstance(value, (date, datetime)):
            obj[key] = value.isoformat()
    return obj


def main():
    print("Démarrage de la couche CURATED...")

    mysql_conn = pymysql.connect(**MYSQL_CONFIG)

    query = """
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
        cursor.execute(query)
        events = cursor.fetchall()

        cursor.execute("""
            SELECT AVG(tourism_value) AS avg_tourism
            FROM tourism_history
            WHERE tourism_value IS NOT NULL;
        """)
        tourism_result = cursor.fetchone()

    mysql_conn.close()

    avg_tourism = float(tourism_result["avg_tourism"] or 0)

    documents = []
    for event in events:
        event = convert_dates(event)

        prediction_score = min(1, avg_tourism / 100000)

        documents.append({
            "event_id": event["event_id"],
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
            "ml_prediction": {
                "model": "simple_baseline",
                "tourism_score": avg_tourism,
                "prediction_score": round(prediction_score, 4),
                "interpretation": "Score estimé à partir de la moyenne historique du tourisme."
            }
        })

    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[MONGO_DB]
    collection = db[MONGO_COLLECTION]

    collection.delete_many({})
    if documents:
        collection.insert_many(documents)

    mongo_client.close()

    print(f"{len(documents)} événements enrichis insérés dans MongoDB.")
    print("Couche CURATED terminée avec succès.")


if __name__ == "__main__":
    main()
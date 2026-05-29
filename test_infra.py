import boto3
import pymysql
from pymongo import MongoClient

print("Vérification des connexions aux couches du Data Lake...")

# 1. Test S3 LocalStack
try:
    s3 = boto3.client('s3', endpoint_url='http://localhost:4566', aws_access_key_id='test', aws_secret_access_key='test')
    # Création du bucket de notre data lake
    s3.create_bucket(Bucket='my-data-lake')
    print("Couche RAW (LocalStack S3) : Connectée ! Bucket 'my-data-lake' créé.")
except Exception as e:
    print(f"Couche RAW (LocalStack) Échec : {e}")

# 2. Test MySQL Staging
try:
    conn = pymysql.connect(host='localhost', user='root', password='rootpassword', database='staging_ticketmaster', port=3307)
    print("Couche STAGING (MySQL) : Connectée avec succès !")
    conn.close()
except Exception as e:
    print(f"Couche STAGING (MySQL) Échec : {e}")

# 3. Test MongoDB Curated
try:
    client = MongoClient('mongodb://admin:adminpassword@localhost:27017/')
    db = client['curated_datalake']
    # Force une connexion
    client.server_info() 
    print("Couche CURATED (MongoDB) : Connectée avec succès !")
    client.close()
except Exception as e:
    print(f"Couche CURATED (MongoDB) Échec : {e}")
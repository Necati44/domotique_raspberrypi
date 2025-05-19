import os
from dotenv import load_dotenv
import random
import pika
import sqlite3
import json
import time
from datetime import datetime, UTC

# Charger les variables depuis .env
load_dotenv()

credentials = pika.PlainCredentials(
    os.getenv("RABBITMQ_DEFAULT_USER", "guest"),
    os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
)
parameters = pika.ConnectionParameters(
    host=os.getenv("RABBITMQ_HOST", "localhost"),
    credentials=credentials
)

# print("Paramètres: " + os.getenv("RABBITMQ_DEFAULT_USER", "guest") + " , " + os.getenv("RABBITMQ_DEFAULT_PASS", "guest"))

DB_NAME = "zigbee.db"
QUEUE_NAME = "temperature_data"

# parameters.host = "localhost"
# print("host: " + parameters.host)

# 1. Init BDD
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS failed_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# 2. Stockage en base locale
def store_failed_message(payload: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO failed_messages (payload) VALUES (?)", (payload,))
        conn.commit()
    print(f"[!] Message stocké en local : {payload}")

# 3. Retry en base
def retry_failed_messages(channel):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, payload FROM failed_messages")
        messages = cursor.fetchall()

        for msg_id, payload in messages:
            try:
                channel.basic_publish(
                    exchange='',
                    routing_key=QUEUE_NAME,
                    body=payload,
                    properties=pika.BasicProperties(delivery_mode=2)
                    )
                print(f"[✓] Message ré-envoyé : {payload}")
                cursor.execute("DELETE FROM failed_messages WHERE id = ?", (msg_id,))
            except Exception as e:
                print(f"[✗] Échec republication ID {msg_id} : {e}")
        conn.commit()

# 4. Envoi avec fallback
def publish_message(channel, payload: dict):
    payload_str = json.dumps(payload)
    try:
        channel.basic_publish(
            exchange='',
            routing_key=QUEUE_NAME,
            body=payload_str,
            properties=pika.BasicProperties(delivery_mode=2)
            )
        print(f"[→] Message envoyé : {payload_str}")
    except Exception as e:
        print(f"[✗] Erreur RabbitMQ : {e}")
        store_failed_message(payload_str)

# 5. Connexion RabbitMQ
def connect_to_rabbitmq():
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True, exclusive=False)
        print("[✓] Connexion RabbitMQ réussie")
        return connection, channel
    except Exception as e:
        print(f"[!] Impossible de se connecter à RabbitMQ : {e}")
        return None, None
    
def format_lorawan_payload(temperature: float, humidity: float) -> str:
    # Exemple d'encodage : 1 octet pour la température, 1 octet pour l'humidité * 2 (précision 0.5)
    # Température (°C) * 10 pour garder une décimale, ex : 23.4 -> 234 -> 0xEA
    temp_encoded = int(temperature * 10)
    hum_encoded = int(humidity * 2)  # 0.5 précision

    # Format hexadécimal sur 2 octets chacun
    return f"{temp_encoded:04X}{hum_encoded:04X}"

# 6. Boucle principale
def main_loop():
    init_db()
    channel = None

    try:
        while True:
            temperature= round(random.uniform(20.0, 25.0), 1)
            humidity= round(random.uniform(40.0, 60.0), 1)

            # Donnée simulée
            lorawan_payload = {
                "device_id": "sim01",
                "payload": format_lorawan_payload(temperature, humidity),
                "timestamp": datetime.now(UTC).isoformat()
            }

            # Si pas connecté, on tente de se reconnecter
            if channel is None or connection.is_closed:
                connection, channel = connect_to_rabbitmq()

            if channel:
                retry_failed_messages(channel)
                publish_message(channel, lorawan_payload)
            else:
                print("[~] Pas de connexion active, stockage uniquement")

                # Stockage immédiat si on n'a pas pu envoyer
                store_failed_message(json.dumps(lorawan_payload))

            time.sleep(5)

    except KeyboardInterrupt:
        print("\n[↩] Interruption utilisateur, arrêt propre")
        if connection and not connection.is_closed:
            connection.close()

if __name__ == "__main__":
    main_loop()

import pika
import json
import time

# Configuration de la connexion à RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))  # Remplace par l'IP de ton serveur RabbitMQ
channel = connection.channel()

# Assure-toi que la queue existe
channel.queue_declare(queue='temperature_data')

# Simulation de la donnée (exemple d'un capteur de température)
def simulate_sensor_data():
    # Ici, tu peux générer une donnée aléatoire ou simuler un capteur
    sensor_data = {
        "temperature": 25.6,  # Température simulée
        "humidity": 45.2,     # Humidité simulée
        "timestamp": time.time()  # Timestamp actuel
    }
    return sensor_data

# Publication des données sur RabbitMQ
def publish_data():
    sensor_data = simulate_sensor_data()
    message = json.dumps(sensor_data)  # Conversion des données en JSON
    channel.basic_publish(
        exchange='',
        routing_key='temperature_data',  # Nom de la queue RabbitMQ
        body=message
    )
    print(f"Message envoyé: {message}")

# Test : publier toutes les 5 secondes
try:
    while True:
        publish_data()
        time.sleep(5)  # Publie toutes les 5 secondes
except KeyboardInterrupt:
    print("Arrêt du script")

# Ferme la connexion RabbitMQ après l'exécution
connection.close()

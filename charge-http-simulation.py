import requests
import time
import random

TARGET_URL = "http://127.0.0.1:64988"  # à adapter avec le minikube service nginx-deployment --url

def generate_traffic(duration=300):
    start = time.time()
    while time.time() - start < duration:
        num_requests = random.randint(200, 100000)  # nombre de requêtes à envoyer dans cette boucle
        for _ in range(num_requests):
            try:
                requests.get(TARGET_URL)
            except:
                pass  # ignore les erreurs
        sleep_time = random.uniform(0.5, 3)
        print(f"⏳ Pause de {sleep_time:.2f}s avant nouvelle vague...")
        time.sleep(sleep_time)

generate_traffic()

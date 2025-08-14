import requests
import subprocess
import math
import time

# ===============================
# Configuration
# ===============================
PROMETHEUS_URL = "http://127.0.0.1:50718/api/v1/query" #a modifier selon l'url vers prometheus
QUERY = 'rate(nginx_http_requests_total[1m])'

CHARGE_UNITAIRE = 500   # nombre de requêtes/min qu'un pod peut gérer sans saturation
MIN_REPLICAS = 1
MAX_REPLICAS = 10
INTERVAL = 5           # secondes entre deux vérifications

DEPLOYMENT_NAME = "nginx-deployment"
NAMESPACE = "default"

# ===============================
# Fonctions utilitaires
# ===============================
def get_http_rate():
    """Récupère le nombre de requêtes HTTP/min depuis Prometheus"""
    try:
        response = requests.get(PROMETHEUS_URL, params={'query': QUERY}, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data['status'] == 'success' and data['data']['result']:
            return float(data['data']['result'][0]['value'][1])
    except Exception as e:
        print(f"[ERREUR] Impossible de récupérer les métriques : {e}")

    return 0.0

def scale_nginx(pods):
    """Applique le scaling du déploiement nginx"""
    try:
        subprocess.run(
            ["kubectl", "scale", f"deployment/{DEPLOYMENT_NAME}",
             f"--replicas={pods}", "-n", NAMESPACE],
            check=True
        )
        print(f"[INFO] Scaling appliqué : {pods} pods")
    except subprocess.CalledProcessError as e:
        print(f"[ERREUR] Échec du scaling : {e}")

# ===============================
# Boucle principale
# ===============================
def main():
    print(f"[DÉMARRAGE] Autoscaler HTTP démarré - Intervalle : {INTERVAL}s")
    while True:
        http_rate = get_http_rate()
        desired = math.ceil(http_rate / CHARGE_UNITAIRE)
        desired = max(MIN_REPLICAS, min(desired, MAX_REPLICAS))

        print(f"[MÉTRIQUES] Requêtes/min : {http_rate:.2f} | Pods désirés : {desired}")
        scale_nginx(desired)

        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()

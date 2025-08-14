import requests, time, subprocess
import numpy as np
from tensorflow.keras.models import load_model
import joblib
from datetime import datetime

# === Paramètres ===
PROM_URL      = 'http://127.0.0.1:50718' #a adapter
QUERY         = 'irate(nginx_http_requests_total[30s])'
MIN_REPLICAS  = 1
MAX_REPLICAS  = 10
N_STEPS       = 24
MODEL_PATH    = 'lstm_predictor.keras'   # format .keras
SCALER_PATH   = 'scaler.pkl'

# === Adapter ici selon ton générateur ===
MAX_EXPECTED_RPM   = 10_000   # charge max que tu observes (~10k)
HEADROOM_FACTOR    = 0.95     # on vise 10 pods vers ~95% de la charge max
THRESHOLD_STRATEGY = "linear" # "linear" ou "geometric"

def build_thresholds(max_rpm: int, headroom: float, strategy: str):
    """
    Construit 9 seuils croissants mappés sur 10 pods.
    - linear: coupures régulières (1000,2000,...,9000 pour 10k)
    - geometric: plus serré en bas, plus espacé en haut
    """
    top = max(1, int(max_rpm * headroom))
    if strategy == "geometric":
        cuts = np.geomspace(max(1, top // 100), top, 10)[:-1]  # 9 seuils
        cuts = np.clip(cuts, 1, top - 1)
        thresholds = sorted({int(c) for c in cuts})
        # si des doublons réduisent le nombre, on repasse en linéaire
        if len(thresholds) < 9:
            step = top // 10
            thresholds = [step * i for i in range(1, 10)]
    else:
        # linéaire par défaut
        step = max(1, top // 10)
        thresholds = [step * i for i in range(1, 10)]  # 9 seuils
    return thresholds

SCALE_THRESHOLDS = build_thresholds(MAX_EXPECTED_RPM, HEADROOM_FACTOR, THRESHOLD_STRATEGY)
print(f"[INFO] Seuils utilisés: {SCALE_THRESHOLDS}")

# === Chargement du modèle et du scaler ===
model  = load_model(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
print(f"[INFO] Scaler min: {getattr(scaler, 'data_min_', 'NA')}, max: {getattr(scaler, 'data_max_', 'NA')}")

history = []

# === Récupération depuis Prometheus ===
def fetch_prometheus(prom_url: str = PROM_URL, query: str = QUERY, timeout: int = 3):
    try:
        r = requests.get(f"{prom_url}/api/v1/query", params={"query": query}, timeout=timeout)
        r.raise_for_status()
        payload = r.json()
        result = payload.get("data", {}).get("result", [])
        if not result:
            return None
        return float(result[0]["value"][1])
    except Exception as e:
        print(f"[ERREUR] Échec de récupération Prometheus: {e}")
        return None

# === Boucle principale ===
while True:
    v = fetch_prometheus()
    timestamp = datetime.now()

    if v is not None:
        print(f"[{timestamp}] ➤ Valeur Prometheus récupérée : {v}")

        # Filtrage de valeurs aberrantes
        if 0 < v < 1_000_000:
            history.append(v)
        else:
            print(f"[{timestamp}] Valeur ignorée : hors plage raisonnable")
            time.sleep(5)
            continue

        if len(history) >= N_STEPS:
            # Préparation de la séquence
            recent_seq = history[-N_STEPS:]
            print(f"[{timestamp}] Dernière séquence brute : {recent_seq}")

            seq = np.array(recent_seq).reshape(-1, 1)
            try:
                scaled = scaler.transform(seq)
            except Exception as e:
                print(f"[ERREUR] Scaling échoué : {e}")
                time.sleep(5)
                continue

            X = scaled.reshape((1, N_STEPS, 1))

            # Prédiction
            pred_norm = model.predict(X, verbose=0)[0][0]
            try:
                pred_real = scaler.inverse_transform([[pred_norm]])[0][0]
            except Exception as e:
                print(f"[ERREUR] Inverse scaling échoué : {e}")
                time.sleep(5)
                continue

            pred_real = max(0, pred_real)  # éviter négatifs
            print(f"[{timestamp}] Prédiction normalisée : {pred_norm:.5f}")
            print(f"[{timestamp}] Prédiction réelle (requêtes/min) : {pred_real:.2f}")

            # === Décision de scaling (if/elif jusqu'à 10 pods) ===
            t = SCALE_THRESHOLDS  # 9 seuils croissants
            if pred_real < t[0]:            reps = 1
            elif pred_real < t[1]:          reps = 2
            elif pred_real < t[2]:          reps = 3
            elif pred_real < t[3]:          reps = 4
            elif pred_real < t[4]:          reps = 5
            elif pred_real < t[5]:          reps = 6
            elif pred_real < t[6]:          reps = 7
            elif pred_real < t[7]:          reps = 8
            elif pred_real < t[8]:          reps = 9
            else:                            reps = 10

            reps = max(MIN_REPLICAS, min(MAX_REPLICAS, reps))
            print(f"[{timestamp}] ➤ Décision de scaling : {reps} pods")

            subprocess.run(['kubectl', 'scale', 'deployment/nginx-deployment', f'--replicas={reps}'])
            print(f"[{timestamp}]  Déploiement mis à l’échelle.")
    else:
        print(f"[{timestamp}]  Aucune valeur Prometheus récupérée.")

    time.sleep(5)

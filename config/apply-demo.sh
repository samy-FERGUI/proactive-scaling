#!/usr/bin/env bash

set -euo pipefail

CLEAN=false
for arg in "$@"; do
  [[ $arg == "--clean" ]] && CLEAN=true
done

if $CLEAN; then
  echo "Suppression de tout cluster existant"
  minikube delete
fi

# 1) Démarrage de Minikube si nécessaire
if ! minikube status &>/dev/null; then
  echo "Démarrage d'un nouveau cluster Minikube..."
  minikube start \
    --memory=4096 \
    --cpus=2 \
    --addons=metrics-server \
    --kubernetes-version=stable
else
  echo "Minikube est déjà démarré"
fi

# 2) Diriger Docker vers le daemon de Minikube
echo "Configuration de l'environnement Docker local pour Minikube"
eval "$(minikube docker-env)"

# 3) (Re)construction de ton image custom
echo "(Re)construction de l'image Docker custom : nginx-with-status"
docker build -t nginx-with-status ./nginx-custom/

# 4) Appliquer tous les manifests (apply = idempotent)
echo "Déploiement / mise à jour des composants Kubernetes..."
manifests=(
  prometheus-rbac.yaml
  kube-state-metrics.yaml
  nginx-deployment.yaml
  nginx-service.yaml
  nginx-exporter.yaml
  nginx-hpa.yaml
  prometheus-config.yaml
  prometheus-deployment.yaml
  prometheus-service.yaml
  grafana-deployment.yaml
  grafana-service.yaml
)

for m in "${manifests[@]}"; do
  echo "kubectl apply -f $m"
  kubectl apply -f "$m"
done

echo "Déploiement / mise à jour terminé."

# 5) Attendre que Grafana soit disponible
echo "⏳ Attente du démarrage de Grafana..."
kubectl wait \
  --for=condition=available \
  --timeout=120s \
  deployment/grafana

echo
echo Tout est prêt !"

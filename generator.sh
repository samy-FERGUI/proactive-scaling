#!/bin/bash

TARGET_URL="http://127.0.0.1:50707"
END_TIME=$((SECONDS + 900))  # 900s = 15 minutes

echo "Test de charge aléatoire sur 15 minutes vers $TARGET_URL"

while [ $SECONDS -lt $END_TIME ]; do
    # Générer aléatoirement les paramètres de charge
    THREADS=$((RANDOM % 4 + 1))      # 1 à 4 threads
    CONNECTIONS=$((RANDOM % 200 + 1)) # 1 à 200 connexions
    DURATION=$((RANDOM % 15 + 5))    # 5 à 20 secondes

    echo "Phase : $THREADS threads, $CONNECTIONS connexions, $DURATION s"
    wrk -t$THREADS -c$CONNECTIONS -d${DURATION}s $TARGET_URL

    # Pause aléatoire pour simuler zéro requêtes
    PAUSE=$((RANDOM % 15)) # 0 à 7 secondes
    if [ $PAUSE -gt 0 ]; then
        echo "Pause de $PAUSE s (trafic nul)"
        sleep $PAUSE
    fi
done

echo "Test de charge terminé."

#!/usr/bin/env bash
# Starts the Flask API (run from anywhere).
cd "$(dirname "$0")"
[ -f backend/.env ] || { echo "Missing backend/.env — copy backend/.env.example and edit it."; exit 1; }
python backend/app.py

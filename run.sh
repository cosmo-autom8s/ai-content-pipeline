#!/bin/bash
# Build frontend and start the dashboard server on port 8088

set -e

cd "$(dirname "$0")"

echo "Building frontend..."
cd frontend && npm run build && cd ..

echo "Starting server on http://localhost:8088"
source venv/bin/activate
uvicorn api.server:app --port 8088 --host 0.0.0.0

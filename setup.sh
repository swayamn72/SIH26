#!/usr/bin/env bash
set -euo pipefail

echo "=== MuleGuard Setup ==="

# Create data directories
mkdir -p data/uploads data/db data/exports

# Copy env if not exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  A .env file has been created from .env.example."
  echo "   Please add your GROQ_API_KEY to .env before continuing:"
  echo "   Get a free key at: https://console.groq.com"
  echo ""
  read -p "Press Enter once you have added your GROQ_API_KEY to .env..."
fi

echo ""
echo "Starting MuleGuard..."
echo "This will build the Docker image and start the service."
echo ""

docker compose up -d --build

echo ""
echo "✅ MuleGuard is running!"
echo "   → App:      http://localhost:8000"
echo "   → API Docs: http://localhost:8000/api/docs"

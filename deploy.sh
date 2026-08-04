#!/usr/bin/env bash
set -euo pipefail

# Navigate to script directory
cd "$(dirname "$0")"

echo "🔄 Stopping existing container..."
docker compose down

echo "🔨 Building image (no cache)..."
docker compose build --no-cache

echo "🚀 Starting container..."
docker compose up -d

echo "📋 Following logs (Ctrl+C to exit)..."
docker compose logs -f

#!/usr/bin/env bash
set -euo pipefail

SERVER="lidopad_static"
APP_DIR="/opt/bm_push_bot"

echo "=== Deploy to $SERVER ==="

echo "1. Upload code..."
rsync -avz --delete \
  --exclude '.venv' \
  --exclude 'data' \
  --exclude '.env' \
  --exclude '.git' \
  --exclude '__pycache__' \
  ./ "$SERVER:$APP_DIR/"

echo "2. Build & restart container..."
ssh "$SERVER" "cd $APP_DIR && docker compose -f docker-compose.prod.yml up -d --build"

echo "3. Run migrations..."
ssh "$SERVER" "cd $APP_DIR && docker compose -f docker-compose.prod.yml exec -T web python manage.py migrate"

echo "4. Collect static..."
ssh "$SERVER" "cd $APP_DIR && docker compose -f docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput"

echo "=== Done ==="

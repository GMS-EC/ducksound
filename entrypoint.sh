#!/bin/bash
set -e

echo "================================================"
echo "🎵 DuckSound - Entrypoint"
echo "================================================"

# === 1. Esperar por servicios externos ===
if [ -n "$DATABASE_URL" ]; then
    echo "⌛ Esperando PostgreSQL..."
    for i in $(seq 1 30); do
        if python -c "import socket; s=socket.create_connection(('postgres', 5432), 2); s.close()" 2>/dev/null; then
            echo "✅ PostgreSQL listo"
            break
        fi
        if [ "$i" -eq 30 ]; then echo "⚠️ PostgreSQL no disponible"; fi
        sleep 1
    done
fi

if [ -n "$REDIS_HOST" ] && [ "$REDIS_HOST" != "localhost" ]; then
    echo "⌛ Esperando Redis..."
    for i in $(seq 1 30); do
        if python -c "import socket; s=socket.create_connection(('$REDIS_HOST', ${REDIS_PORT:-6379}), 2); s.close()" 2>/dev/null; then
            echo "✅ Redis listo"
            break
        fi
        if [ "$i" -eq 30 ]; then echo "⚠️ Redis no disponible"; fi
        sleep 1
    done
fi

# === 2. Migraciones automáticas ===
echo "🔄 Ejecutando migraciones..."
cd /app
python -c "
from app import app, db
from sqlalchemy import text

with app.app_context():
    db.create_all()
    
    for col in [
        'ALTER TABLE artistas ADD COLUMN IF NOT EXISTS musicbrainz_id VARCHAR(36)',
        'ALTER TABLE artistas ADD COLUMN IF NOT EXISTS nombre_normalizado VARCHAR(200)',
        'ALTER TABLE albumes ADD COLUMN IF NOT EXISTS musicbrainz_id VARCHAR(36)',
    ]:
        try:
            db.session.execute(text(col))
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    for idx in [
        'CREATE INDEX IF NOT EXISTS idx_artistas_nombre_normalizado ON artistas(nombre_normalizado)',
        'CREATE INDEX IF NOT EXISTS idx_artistas_mbid ON artistas(musicbrainz_id)',
        'CREATE INDEX IF NOT EXISTS idx_albumes_mbid ON albumes(musicbrainz_id)',
    ]:
        try:
            db.session.execute(text(idx))
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    print('✅ Migraciones completadas')
" 2>&1 | grep -v '^\s*$'

# === 3. Iniciar servicio ===
MODE="${1:-web}"

case "$MODE" in
    web)
        echo "🚀 Iniciando servidor web..."
        exec gunicorn app:app \
            --bind 0.0.0.0:${PORT:-8604} \
            --workers ${WEB_WORKERS:-4} \
            --threads ${WEB_THREADS:-2} \
            --worker-class gthread \
            --timeout 120 \
            --access-logfile - \
            --error-logfile - \
            --log-level ${LOG_LEVEL:-info}
        ;;
    worker)
        echo "🚀 Iniciando worker..."
        exec python run_worker.py
        ;;
    migrate-only)
        echo "✅ Migraciones ejecutadas."
        exit 0
        ;;
    *)
        echo "Modo: \$MODE"
        echo "Uso: entrypoint.sh web | worker | migrate-only"
        exit 1
        ;;
esac

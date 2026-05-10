#!/bin/bash
set -e

echo "================================================"
echo "🎵 DuckSound - Entrypoint"
echo "================================================"

# === 1. Esperar por Redis si está configurado ===
if [ -n "$REDIS_HOST" ] && [ "$REDIS_HOST" != "localhost" ]; then
    echo "⌛ Esperando Redis en $REDIS_HOST:$REDIS_PORT..."
    for i in $(seq 1 30); do
        if python -c "import socket; s=socket.create_connection(('$REDIS_HOST', $REDIS_PORT or 6379), 2); s.close()" 2>/dev/null; then
            echo "✅ Redis listo"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "⚠️ Redis no disponible, continuando de todas formas..."
        fi
        sleep 1
    done
fi

# === 2. Ejecutar migraciones automáticas ===
echo "🔄 Ejecutando migraciones de base de datos..."
cd /app
python -c "
from app import app, db
from sqlalchemy import text

with app.app_context():
    # WAL mode y timeout
    db.session.execute(text('PRAGMA journal_mode=WAL'))
    db.session.execute(text('PRAGMA busy_timeout=30000'))
    db.session.commit()
    
    # Migraciones de columnas
    migraciones = [
        'ALTER TABLE artistas ADD COLUMN musicbrainz_id VARCHAR(36)',
        'ALTER TABLE artistas ADD COLUMN nombre_normalizado VARCHAR(200)',
        'ALTER TABLE albumes ADD COLUMN musicbrainz_id VARCHAR(36)',
        'CREATE INDEX IF NOT EXISTS idx_artistas_nombre_normalizado ON artistas(nombre_normalizado)',
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_artistas_mbid ON artistas(musicbrainz_id)',
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_albumes_mbid ON albumes(musicbrainz_id)',
    ]
    for m in migraciones:
        try:
            db.session.execute(text(m))
            db.session.commit()
            print(f'  ✅ {m.split()[0]} {m.split()[2] if len(m.split()) > 2 else \"\"}')
        except Exception:
            db.session.rollback()
    
    print('✅ Migraciones completadas')
" 2>&1 | grep -v '^$'

# === 3. Determinar modo de inicio ===
MODE="${1:-web}"

case "$MODE" in
    web)
        echo "🚀 Iniciando servidor web DuckSound..."
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
        echo "🚀 Iniciando worker DuckSound..."
        exec python run_worker.py
        ;;
    migrate-only)
        echo "✅ Solo migraciones ejecutadas. Saliendo."
        exit 0
        ;;
    *)
        echo "Modo desconocido: $MODE"
        echo "Usos: entrypoint.sh web | worker | migrate-only"
        exit 1
        ;;
esac

#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────
# Colores ANSI para el banner
# ─────────────────────────────────────────────────────────────
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
WHITE='\033[1;37m'
DIM='\033[2;37m'
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

# ─────────────────────────────────────────────────────────────
# Banner principal de arranque
# ─────────────────────────────────────────────────────────────
print_banner() {
    local MODE="$1"
    local VERSION="1.0.0"

    echo ""
    echo -e "${DIM}────────────────────────────────────────────────────────${RESET}"
    echo ""
    echo -e "${CYAN}    ██████╗ ██╗   ██╗ ██████╗██╗  ██╗${RESET}"
    echo -e "${CYAN}    ██╔══██╗██║   ██║██╔════╝██║ ██╔╝${RESET}"
    echo -e "${CYAN}    ██║  ██║██║   ██║██║     █████╔╝ ${RESET}"
    echo -e "${CYAN}    ██║  ██║██║   ██║██║     ██╔═██╗ ${RESET}"
    echo -e "${CYAN}    ██████╔╝╚██████╔╝╚██████╗██║  ██╗${RESET}"
    echo -e "${CYAN}    ╚═════╝  ╚═════╝  ╚═════╝╚═╝  ╚═╝${RESET}"
    echo ""
    echo -e "${CYAN}  ███████╗ ██████╗ ██╗   ██╗███╗   ██╗██████╗ ${RESET}"
    echo -e "${CYAN}  ██╔════╝██╔═══██╗██║   ██║████╗  ██║██╔══██╗${RESET}"
    echo -e "${CYAN}  ███████╗██║   ██║██║   ██║██╔██╗ ██║██║  ██║${RESET}"
    echo -e "${CYAN}  ╚════██║██║   ██║██║   ██║██║╚██╗██║██║  ██║${RESET}"
    echo -e "${CYAN}  ███████║╚██████╔╝╚██████╔╝██║ ╚████║██████╔╝${RESET}"
    echo -e "${CYAN}  ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═════╝ ${RESET}"
    echo ""
    echo -e "${WHITE}         🎵 Personal Hi-Res Music Server${RESET}"
    echo ""
    echo -e "${DIM}────────────────────────────────────────────────────────${RESET}"
    echo ""

    # Información del sistema y configuración actual
    echo -e "  ${DIM}Versión    :${RESET}  ${YELLOW}v${VERSION}${RESET}"
    echo -e "  ${DIM}Modo       :${RESET}  ${WHITE}${MODE}${RESET}"
    echo -e "  ${DIM}Puerto     :${RESET}  ${WHITE}${PORT:-8604}${RESET}"
    echo -e "  ${DIM}Workers    :${RESET}  ${WHITE}${WEB_WORKERS:-4} workers × ${WEB_THREADS:-2} threads${RESET}"
    echo -e "  ${DIM}Base datos :${RESET}  ${WHITE}${DB_HOST:-postgres}:${DB_PORT:-5432}/${DB_NAME:-ducksound}${RESET}"
    echo -e "  ${DIM}Redis      :${RESET}  ${WHITE}${REDIS_HOST:-redis}:${REDIS_PORT:-6379}${RESET}"
    echo ""
    echo -e "${DIM}────────────────────────────────────────────────────────${RESET}"
    echo ""
}

# ─────────────────────────────────────────────────────────────
# 1. Esperar por servicios externos antes de arrancar
# ─────────────────────────────────────────────────────────────
wait_for_service() {
    local NAME="$1"
    local HOST="$2"
    local PORT="$3"

    echo -e "  ${DIM}⌛ Esperando ${NAME}...${RESET}"
    for i in $(seq 1 30); do
        if python -c "import socket; s=socket.create_connection(('${HOST}', ${PORT}), 2); s.close()" 2>/dev/null; then
            echo -e "  ${GREEN}✔ ${NAME} listo${RESET}"
            return 0
        fi
        if [ "$i" -eq 30 ]; then
            echo -e "  ${RED}✘ ${NAME} no disponible tras 30 intentos${RESET}"
        fi
        sleep 1
    done
}

# Esperar PostgreSQL si hay DATABASE_URL configurado
if [ -n "$DATABASE_URL" ]; then
    wait_for_service "PostgreSQL" "postgres" "5432"
fi

# Esperar Redis si hay host remoto configurado
if [ -n "$REDIS_HOST" ] && [ "$REDIS_HOST" != "localhost" ]; then
    wait_for_service "Redis" "$REDIS_HOST" "${REDIS_PORT:-6379}"
fi

# ─────────────────────────────────────────────────────────────
# 2. Migraciones automáticas de base de datos
# ─────────────────────────────────────────────────────────────
echo -e "  ${DIM}🔄 Ejecutando migraciones de base de datos...${RESET}"
cd /app
python -c "
from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    db.create_all()

    for col in [
        'ALTER TABLE artistas ADD COLUMN IF NOT EXISTS musicbrainz_id VARCHAR(36)',
        'ALTER TABLE artistas ADD COLUMN IF NOT EXISTS nombre_normalizado VARCHAR(200)',
        'ALTER TABLE albums ADD COLUMN IF NOT EXISTS musicbrainz_id VARCHAR(36)',
    ]:
        try:
            db.session.execute(text(col))
            db.session.commit()
        except Exception:
            db.session.rollback()

    for idx in [
        'CREATE INDEX IF NOT EXISTS idx_artistas_nombre_normalizado ON artistas(nombre_normalizado)',
        'CREATE INDEX IF NOT EXISTS idx_artistas_mbid ON artistas(musicbrainz_id)',
        'CREATE INDEX IF NOT EXISTS idx_albums_mbid ON albums(musicbrainz_id)',
    ]:
        try:
            db.session.execute(text(idx))
            db.session.commit()
        except Exception:
            db.session.rollback()

    print('  \033[0;32m✔ Migraciones completadas\033[0m')
" 2>&1 | grep -v '^\s*$'

echo ""

# ─────────────────────────────────────────────────────────────
# 3. Determinar modo de arranque y mostrar banner
# ─────────────────────────────────────────────────────────────
MODE="${1:-web}"

case "$MODE" in
    web)
        print_banner "Servidor Web (Gunicorn)"
        echo -e "  ${GREEN}▶ Iniciando Gunicorn...${RESET}"
        echo ""
        exec gunicorn "app:app" \
            --bind "0.0.0.0:${PORT:-8604}" \
            --workers "${WEB_WORKERS:-4}" \
            --threads "${WEB_THREADS:-2}" \
            --worker-class gthread \
            --timeout 120 \
            --access-logfile - \
            --error-logfile - \
            --log-level "${LOG_LEVEL:-info}"
        ;;
    worker)
        print_banner "Background Worker (RQ)"
        echo -e "  ${GREEN}▶ Iniciando worker RQ...${RESET}"
        echo ""
        exec python run_worker.py
        ;;
    migrate-only)
        echo -e "  ${GREEN}✔ Solo migraciones — finalizando.${RESET}"
        exit 0
        ;;
    *)
        echo -e "  ${RED}✘ Modo desconocido: ${MODE}${RESET}"
        echo -e "  Uso: entrypoint.sh ${WHITE}web${RESET} | ${WHITE}worker${RESET} | ${WHITE}migrate-only${RESET}"
        exit 1
        ;;
esac

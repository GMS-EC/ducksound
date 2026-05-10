FROM python:3.10-slim

# Evitar prompts
ENV DEBIAN_FRONTEND=noninteractive

# Dependencias del sistema (libsndfile es necesario para soundfile)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libsndfile1 \
       ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements y proyecto
COPY requirements.txt ./
RUN pip install --upgrade pip wheel
RUN pip install -r requirements.txt

# Copiar el resto del código
COPY . /app

# Hacer entrypoint ejecutable
RUN chmod +x entrypoint.sh

# Exponer puerto
EXPOSE 8604

# Variables por defecto
ENV FLASK_ENV=production
ENV WEB_WORKERS=4
ENV WEB_THREADS=2
ENV LOG_LEVEL=info

# Entrypoint: ejecuta migraciones y luego inicia el servicio indicado
# Modos: entrypoint.sh web | worker | migrate-only
ENTRYPOINT ["./entrypoint.sh"]
CMD ["web"]


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

# Exponer puerto Flask
EXPOSE 8604

# Variables por defecto
ENV FLASK_ENV=production

# Comando por defecto: servidor WSGI de producción con workers y threads
CMD ["gunicorn", "--bind", "0.0.0.0:8604", "--workers", "4", "--threads", "2", "--timeout", "120", "app:app"]


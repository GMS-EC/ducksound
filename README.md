# 🦆 DuckSound

**DuckSound** es un servidor de streaming de música personal, self-hosted, con interfaz web moderna estilo Spotify. Escanea tu biblioteca de audio local, extrae y enriquece metadatos automáticamente, y te permite escuchar tu música desde cualquier dispositivo en tu red local.

![Flask](https://img.shields.io/badge/Flask-3.0-blue)
![Python](https://img.shields.io/badge/Python-3.10+-yellow)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-AGPL_v3-blue)

---

## ✨ Funcionalidades

### 🎵 Reproductor de música
- **Reproductor web persistente** que mantiene la reproducción al navegar entre páginas (arquitectura iframe/postMessage)
- Controles completos: play/pausa, siguiente, anterior, avance/retroceso 10s, barra de progreso clickeable
- **Cola de reproducción** dinámica con visualización en tiempo real
- **Shuffle y Repeat** (ninguno / una / todas)
- **Crossfade** configurable entre canciones para transiciones suaves
- **Color adaptativo** — el acento de la interfaz cambia dinámicamente según la portada del álbum
- Soporte para **MP3, FLAC, WAV, M4A y OGG**

### 🎤 Letras sincronizadas y karaoke
- Soporte nativo para archivos **.lrc** (letras con marcas de tiempo)
- **Descarga automática** de letras sincronizadas desde [LRCLIB](https://lrclib.net) durante el escaneo
- **Highlight en tiempo real** de la línea que se está cantando con scroll automático
- **Click en línea** para saltar a ese punto de la canción
- **Traducción de letras** integrada al idioma preferido del usuario vía LibreTranslate / Google Translate

### 📚 Biblioteca inteligente
- **Escaneo recursivo** de carpetas con detección de formatos (MP3, FLAC, WAV, M4A, OGG)
- **Extracción de metadatos** ID3v2 / Vorbis Comments (título, artista, álbum, género, número de pista)
- **Inferencia por carpetas** — si no hay metadatos, infiere artista y álbum desde la estructura `Artista/Álbum/cancion.mp3`
- **Normalización** de nombres de artistas y detección de versiones de álbumes (Deluxe, Remastered, Live, etc.)
- **Reparación de rutas** — detecta canciones que cambiaron de ubicación y actualiza sus rutas automáticamente
- Navegación por **artistas**, **álbumes**, **explorar** y **carpetas** (vista tipo árbol)

### 🌐 Enriquecimiento automático de metadatos
- **Fotos de artistas** en alta resolución desde [Deezer API](https://developers.deezer.com)
- **Biografías** de artistas desde [Wikipedia](https://www.wikipedia.org) (español con fallback a inglés)
- **Portadas de álbumes** desde [Deezer API](https://developers.deezer.com) e [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/)
- **Año de lanzamiento** de álbumes desde Deezer
- Portadas locales extraídas desde tags APIC/FLAC embebidos en los archivos de audio
- Fallback inteligente: API → archivo embebido → placeholder SVG con nota musical

### 🎯 Recomendaciones y descubrimiento
- **Motor de recomendaciones híbrido** con 5 factores ponderados:
  - Género (35%), Artista (25%), Análisis acústico (20%), Álbum (10%), Duración (10%)
- **Similitud acústica** basada en dynamic range, RMS level y bit rate
- **Diversidad forzada** — limita canciones del mismo álbum/artista para ampliar el descubrimiento
- **Daily Mixes** personalizados generados diariamente desde favoritos, géneros e historial
- **Artistas relacionados** por géneros compartidos
- Panel de **canciones similares** con porcentaje de similitud visible

### 📊 Análisis de audio
- **Métricas de calidad** por canción: sample rate, bit depth, canales, bit rate
- **Análisis de señal** con librosa/numpy: dynamic range, peak level, RMS level, frecuencia de Nyquist, total de samples
- Información técnica accesible vía API (`/api/audio-info/<id>`)

### 👤 Usuarios y personalización
- **Sistema de autenticación** con hash seguro (Werkzeug) y roles (admin / usuario)
- **Favoritos (Me gusta)** por usuario con toggle rápido desde el reproductor
- **Colecciones** personalizadas para agrupar canciones
- **Historial de escucha** con tracking de skips (respeta la configuración de privacidad)
- **Perfil de usuario** con estadísticas: top canciones, top artistas, total de reproducciones, horas escuchadas, escuchas últimas 24h
- Preferencias configurables: **crossfade**, **idioma de traducción**, **tracking de actividad**

### 🔧 Panel de administración
- **Dashboard admin** con acciones rápidas: escanear, gestionar usuarios, estadísticas
- **Escaneo de biblioteca** asíncrono con barra de progreso en tiempo real y fase de enriquecimiento
- **Estadísticas globales**: total de canciones/artistas/álbumes/usuarios, top canciones, top artista, top género
- **Gestión de usuarios**: crear, listar, asignar roles
- **Verificador de actualizaciones** — compara la versión instalada con el último release en GitHub
- **Changelog integrado** — historial de versiones parseado desde `CHANGELOG.md`
- Protección de endpoints admin por **sesión** o **token Bearer** (`ADMIN_SECRET_TOKEN`)

---

## 🏗️ Arquitectura y APIs

La documentación técnica detallada sobre la estructura del proyecto, el stack tecnológico y la referencia completa de los API Endpoints se ha movido a su propio archivo.

👉 **[Ver Documentación de Arquitectura y APIs (ARCHITECTURE.md)](ARCHITECTURE.md)**

---

## 🚀 Instalación

### Requisitos previos
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado
- Una carpeta con tu música (MP3, FLAC, WAV, M4A, OGG)

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/GamersEC/ducksound.git
cd ducksound
```

### Paso 2: Configurar variables de entorno

Copia el archivo de ejemplo y edítalo con tus valores:

```bash
cp .env.example .env
```

Edita `.env`:

```env
# Ruta a tu carpeta de música en el host
MUSIC_PATH=/ruta/a/tu/musica

# Token para proteger los endpoints de administración
ADMIN_SECRET_TOKEN=tu-token-secreto
```

> **Eso es todo lo que necesitas configurar.** Los datos de la app (base de datos, letras descargadas, carátulas) se almacenan automáticamente en un volumen Docker.

### Paso 3: Construir y levantar

```bash
docker compose build
docker compose up -d
```

### Paso 4: Abrir la app

Abre tu navegador en **http://localhost:8604**

**Credenciales por defecto:**
| Usuario | Contraseña |
|---------|------------|
| `ducksound` | `ducksound` |

> ⚠️ Cambia la contraseña del admin desde el perfil después del primer inicio de sesión.

### Paso 5: Escanear tu música

1. Inicia sesión como admin
2. Ve a **Panel de Administración → Iniciar escaneo completo**
3. El escaneo detectará canciones, extraerá metadatos, descargará portadas y letras, y enriquecerá artistas/álbumes automáticamente
4. ¡Disfruta tu música!

---

## 🐳 Despliegue

### Docker Compose (recomendado)

```yaml
services:
  web:
    build: .
    container_name: ducksound_web
    volumes:
      - ${MUSIC_PATH}:/music:ro
      - ducksound_data:/data
    environment:
      - ADMIN_SECRET_TOKEN=${ADMIN_SECRET_TOKEN}
    ports:
      - '8604:8604'

volumes:
  ducksound_data:
    driver: local
```

### Portainer / CasaOS

1. Crea un nuevo stack con el `docker-compose.yml`
2. Configura las variables de entorno `MUSIC_PATH` y `ADMIN_SECRET_TOKEN`
3. Despliega el stack

---

## 📁 Volúmenes

DuckSound usa **dos volúmenes**:

| Volumen | Montaje | Contenido | Modo |
|---------|---------|-----------|------|
| Tu carpeta de música | `/music` | Tu biblioteca musical | Solo lectura |
| `ducksound_data` | `/data` | Datos de la app | Lectura/escritura |

```
/music              ← tu música (solo lectura, configurada en MUSIC_PATH)
/data               ← volumen Docker gestionado automáticamente
  ├── db/           ← ducksound.db (base de datos SQLite)
  ├── lyrics/       ← archivos .lrc descargados
  └── album_art/    ← carátulas extraídas/descargadas
```

> **Solo configuras `MUSIC_PATH`** en tu `.env`. Todo lo demás lo gestiona Docker automáticamente.

---

## ⚙️ Variables de entorno

| Variable | Requerida | Descripción | Default |
|----------|-----------|-------------|---------|
| `MUSIC_PATH` | ✅ | Ruta a tu carpeta de música en el host | — |
| `ADMIN_SECRET_TOKEN` | ✅ | Token para proteger endpoints `/admin/*` | — |
| `FLASK_ENV` | ❌ | Entorno de Flask | `production` |
| `SECRET_KEY` | ❌ | Clave secreta para sesiones Flask | Auto-generada |

---

## 💻 Desarrollo local (sin Docker)

```bash
# Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python app.py
```

> En modo local, configura la ruta a tu música en `config.py` (variable `MEDIA_FOLDER`).

---

## 📄 Licencia

Este proyecto está licenciado bajo la **GNU Affero General Public License v3.0 (AGPLv3)**.

Esto significa que DuckSound es de código abierto y completamente libre. Eres libre de usarlo, modificarlo y compartirlo. Sin embargo, si modificas el código y lo ofreces como un servicio a través de una red (por ejemplo, alojándolo públicamente), **estás obligado a compartir el código fuente de tus modificaciones** bajo la misma licencia. 

Consulta el archivo [LICENSE](LICENSE) para más detalles.

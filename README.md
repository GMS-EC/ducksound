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

## 🏗️ Arquitectura

```
DuckSound
├── app.py                  # App Flask principal: auth, dashboard, favoritos, colecciones,
│                           # daily mixes, perfil, streaming de audio/letras/portadas, traducción
├── routes.py               # Blueprints: admin (escaneo, usuarios, stats, updates),
│                           # api (JSON endpoints), browse (exploración de artistas/álbumes)
├── models.py               # Modelos SQLAlchemy: Usuario, Artista, Album, Cancion, Playlist,
│                           # Coleccion, Favorito, HistorialEscucha, DailyMix
├── config.py               # Configuración: detección Docker/local, rutas, DB, versión app
├── scan_songs.py           # Escáner de biblioteca: extracción de metadatos, búsqueda de LRC,
│                           # inferencia por carpetas, descarga de portadas/letras
├── audio_analyzer.py       # Análisis de calidad: mutagen (metadatos) + librosa (señal)
├── metadata_fetcher.py     # Enriquecimiento: Deezer API (fotos, portadas) + Wikipedia (bios)
├── metadata_normalizer.py  # Normalización: limpieza de nombres, detección de versiones
├── recommender.py          # Motor de recomendaciones: scoring híbrido de 5 factores
├── templates/              # 23 templates Jinja2 (base, dashboard, player, profile, admin...)
├── static/
│   ├── css/style.css       # Design system completo (dark theme, variables, animaciones)
│   ├── js/
│   │   ├── player_parent.js  # Bridge parent: controles, letras, similares, cola, color adaptativo
│   │   ├── player_frame.js   # Audio engine en iframe: reproducción, crossfade, gestión de cola
│   │   └── player.js         # Legacy/helpers
│   └── img/                # Logo SVG, favicon, logo-app
├── Dockerfile              # Imagen: Python 3.10-slim + libsndfile + ffmpeg
├── docker-compose.yml      # Servicio web + volúmenes (música read-only + datos persistentes)
├── CHANGELOG.md            # Historial de versiones
└── requirements.txt        # Dependencias Python
```

### Stack tecnológico

| Componente | Tecnología |
|-----------|------------|
| Backend | Flask 3.0, SQLAlchemy, Werkzeug |
| Base de datos | SQLite (portátil, sin servidor) |
| Audio parsing | Mutagen (metadatos ID3/Vorbis), NumPy + SoundFile (análisis de señal) |
| APIs externas | Deezer (fotos, portadas, años), iTunes (portadas fallback), Wikipedia (biografías), LRCLIB (letras) |
| Traducción | LibreTranslate (primario) / Google Translate (fallback) |
| Frontend | HTML5, CSS3 (custom design system), JavaScript vanilla, Jinja2 |
| Reproductor | Arquitectura iframe + postMessage (persistencia de audio entre páginas) |
| Contenedor | Docker (Python 3.10-slim + libsndfile + ffmpeg) |

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

Abre tu navegador en **http://localhost:5000**

**Credenciales por defecto:**
| Usuario | Contraseña |
|---------|------------|
| `admin` | `admin123` |

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
      - '5000:5000'

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

## 🔌 API Endpoints

### Endpoints públicos (requieren sesión)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/canciones` | Lista todas las canciones |
| GET | `/api/cancion/<id>` | Detalle de una canción |
| GET | `/api/artist/<id>/albums` | Álbumes de un artista |
| GET | `/api/artist/<id>/canciones` | Canciones de un artista |
| GET | `/api/album/<id>/canciones` | Canciones de un álbum |
| GET | `/api/similares/<id>` | Canciones similares (top 10) |
| GET | `/api/audio-info/<id>` | Info técnica del audio |
| GET | `/api/related/artists/<id>` | Artistas relacionados |
| GET | `/audio/<id>` | Stream del archivo de audio |
| GET | `/lyrics/<id>` | Archivo .lrc de una canción |
| GET | `/album-art/<id>` | Imagen de portada (con fallback chain) |
| POST | `/api/play/<id>` | Registrar reproducción en historial |
| POST | `/api/translate` | Traducir texto de letras |

### Endpoints de favoritos

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/favoritos` | IDs de canciones favoritas |
| GET | `/api/favoritos/canciones` | Lista completa de favoritos |
| POST | `/api/favoritos/toggle/<id>` | Alternar favorito |

### Endpoints de colecciones

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/coleccion-lista` | Listar colecciones del usuario |
| POST | `/api/colecciones/crear` | Crear colección |
| POST | `/api/colecciones/<id>/add-cancion/<id>` | Añadir canción a colección |

### Endpoints admin (requieren sesión admin o token)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/admin` | Panel de administración |
| POST | `/admin/escanear/start` | Iniciar escaneo asíncrono |
| GET | `/admin/escanear/status/<task_id>` | Estado del escaneo |
| GET | `/admin/estadisticas` | Panel de estadísticas |
| GET | `/admin/check-update` | Verificar nueva versión en GitHub |
| POST | `/admin/enrich-artists` | Enriquecer metadatos de artistas |
| GET | `/admin/usuarios` | Listar usuarios |
| POST | `/admin/usuarios/crear` | Crear usuario |

Los endpoints admin aceptan autenticación por:
- Sesión de usuario con rol `admin`
- Header `Authorization: Bearer <ADMIN_SECRET_TOKEN>`
- Header `X-Admin-Token: <ADMIN_SECRET_TOKEN>`

---

## 🛠️ Comandos útiles

```bash
# Ver estado del contenedor
docker compose ps

# Ver logs en tiempo real
docker compose logs -f web

# Reiniciar el servicio
docker compose restart

# Apagar
docker compose down

# Apagar y borrar todos los datos (¡cuidado!)
docker compose down --volumes

# Reconstruir la imagen (después de actualizar código)
docker compose build && docker compose up -d
```

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

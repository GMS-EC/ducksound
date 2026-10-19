# 🏗️ Arquitectura y Referencia Técnica

## Diagrama de Arquitectura

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DuckSound Architecture                          │
│                                                                        │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │                    React 18 SPA (Frontend)                    │    │
│   │   TypeScript · Vite · Glassmorphism · NowPlaying Modal        │    │
│   │   PlayerContext · ContextMenuContext · Realtime SSE Client    │    │
│   └──────────────────────────────┬────────────────────────────────┘    │
│                                  │ REST API / SSE / Audio 206          │
│                                  ▼                                     │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │                  Flask 3.0 Backend Engine                     │    │
│   │  ├ routes/                                                    │    │
│   │  │  main.py · audio.py · api.py · admin.py · auth.py          │    │
│   │  ├ services/                                                  │    │
│   │  │  silence.py   (Gapless FFmpeg)                             │    │
│   │  │  tagger.py    (In-App Tag Editor)                          │    │
│   │  │  recipes.py   (Smart Mixes & Gap Rule)                     │    │
│   │  │  coverart.py  (Semantic Aspect Ratio Ranking)              │    │
│   │  │  color.py     (Pillow Dynamic Palette Extraction)          │    │
│   │  │  events.py    (Server-Sent Events Bus)                     │    │
│   │  │  watcher.py   (Real-time Library Watchdog)                 │    │
│   │  │  scanner.py · metadata.py · lyrics.py · queue.py           │    │
│   │  └────────────────────────────────────────────────────────────┘    │
│                                  │                                     │
│         ┌────────────────────────┴────────────────────────┐            │
│         ▼                                                 ▼            │
│  ┌──────────────┐                                  ┌─────────────┐     │
│  │ SQLite (WAL) │                                  │    /data    │     │
│  │ o PostgreSQL │                                  │  (lyrics,   │     │
│  └──────────────┘                                  │   covers)   │     │
│                                                    └─────────────┘     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Estructura del Proyecto

```
DuckSound/
├── app.py                      # Punto de entrada de la aplicación Flask
├── config.py                   # Configuración central (rutas, base de datos, CORS, versión)
├── entrypoint.sh               # Migraciones automáticas + inicio de servicios
├── Dockerfile                  # Multi-stage: Node 20 (Vite build) + Python 3.10-slim
├── docker-compose.yml          # Despliegue unificado ultra-ligero
├── requirements.txt            # Dependencias Python
├── CHANGELOG.md                # Historial de versiones Keep a Changelog
├── ARCHITECTURE.md             # Esta documentación técnica
│
├── app/                        # Backend Flask RESTful & SSE
│   ├── __init__.py             # Factory create_app(), Blueprints, middleware
│   ├── models.py               # SQLAlchemy: Usuario, Artista, Album, Cancion, AlbumGuardado, Favorito
│   │
│   ├── routes/
│   │   ├── api.py              # Endpoints JSON: biblioteca, canciones, recetas, búsqueda fuzzy, tags
│   │   ├── audio.py            # Streaming HTTP 206 con Byte-Ranges, portadas, letras
│   │   ├── main.py             # Rutas base, detalle de álbumes, artistas, carpetas
│   │   ├── admin.py            # Panel administrativo: escaneo, gestión, estadísticas
│   │   └── auth.py             # Autenticación, tokens de sesión y CSRF
│   │
│   └── services/
│       ├── silence.py          # FFmpeg silencedetect para True Gapless playback
│       ├── tagger.py           # In-App Tagger (Mutagen ID3, FLAC, Vorbis, M4A)
│       ├── recipes.py          # Recetas dinámicas, balance_mix (Gap Rule) y estaciones
│       ├── coverart.py         # Ranking semántico de carátulas y aspecto 1:1
│       ├── color.py            # Extracción cromática adaptativa con Pillow
│       ├── events.py           # Bus en tiempo real con Server-Sent Events (SSE)
│       ├── watcher.py          # Vigilancia reactiva de archivos en disco (Watchdog)
│       ├── scanner.py          # Motor de escaneo completo e incremental
│       ├── audio_analyzer.py   # Análisis acústico (BPM, RMS, Dynamic Range, Peak)
│       ├── transcoder.py       # Transcodificación al vuelo con caché en disco
│       ├── lyrics.py           # Descarga y sincronización de letras (LRCLIB, Genius)
│       ├── metadata.py         # Integración y deduplicación con MusicBrainz
│       ├── recommender.py      # Motor de recomendación por similitud acústica
│       └── queue.py            # Cola de tareas asíncronas Redis / RQ
│
├── frontend/                   # Frontend SPA React 18
│   ├── package.json            # Dependencias npm (React 18, Vite, Lucide, Tailwind)
│   ├── vite.config.ts          # Configuración del bundler y proxy de desarrollo
│   ├── index.html              # Shell HTML5 de la aplicación
│   │
│   └── src/
│       ├── App.tsx             # Enrutamiento React Router y suscripción a eventos SSE
│       ├── index.css           # Design system glassmorphism, temas y estilos globales
│       │
│       ├── contexts/
│       │   ├── PlayerContext.tsx     # Estado global de audio, gapless, colas y volumen
│       │   ├── AuthContext.tsx       # Ciclo de vida de autenticación y usuario
│       │   └── ContextMenuContext.tsx # Menú contextual flotante interactivo
│       │
│       ├── components/
│       │   ├── NowPlayingModal.tsx   # Modal inmersivo a pantalla completa con letras karaoke
│       │   ├── EditTagsModal.tsx     # Modal de edición de etiquetas de audio en vivo
│       │   ├── AudioInfoModal.tsx    # Modal de especificaciones técnicas y análisis acústico
│       │   ├── PlayerBar.tsx         # Barra inferior de reproducción persistente
│       │   ├── RightPanel.tsx        # Panel lateral (Ahora suena, letras y cola de reproducción)
│       │   ├── Sidebar.tsx           # Navegación lateral persistente
│       │   ├── SearchDialog.tsx      # Diálogo de búsqueda rápida
│       │   └── ContextMenu.tsx       # Menú contextual de canciones y colecciones
│       │
│       └── pages/
│           ├── LibraryPage.tsx       # Biblioteca unificada (Favoritos, Álbumes, Playlists)
│           ├── DashboardPage.tsx     # Portada con mezclas inteligentes y novedades
│           ├── AlbumDetailPage.tsx   # Vista de álbum con paleta adaptativa y multi-disco
│           ├── ArtistDetailPage.tsx  # Vista de artista y discografía completa
│           ├── FoldersPage.tsx       # Explorador físico de directorios musicales
│           ├── ExplorePage.tsx       # Exploración por géneros y recomendaciones
│           ├── ProfilePage.tsx       # Perfil, métricas y preferencias de usuario
│           └── AdminPage.tsx         # Panel de control y administración del servidor
│
└── tests/                      # Suite de pruebas automatizadas
    ├── test_backend_routes.py  # 21 tests de integración para rutas y servicios
    └── test_normalizacion.py   # Tests de normalización y deduplicación
```

---

## 🧱 Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Frontend | React 18, TypeScript, Vite, Glassmorphism CSS |
| Estado Frontend | Context API (`PlayerContext`, `AuthContext`, `ContextMenuContext`) |
| Backend | Flask 3.0, SQLAlchemy, Werkzeug |
| Base de datos | SQLite 3 (WAL mode) / PostgreSQL 16 |
| Cache / Cola | Redis 7 + RQ / Worker interno |
| Streaming | HTTP 206 Partial Content (Byte-Ranges), Gapless con `silencedetect` |
| Editor de Tags | Mutagen (ID3v2, Vorbis Comments, MP4 Atoms) |
| Carátulas y Color | Pillow (extracción cromática y ranking semántico de imagen) |
| Eventos Push | Server-Sent Events (SSE) y Watchdog |
| Servidor web | Gunicorn (gthread) |
| Contenedores | Docker (multi-stage build) y Docker Compose |

---

## 🔌 API Endpoints

### Endpoints públicos (requieren sesión)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/canciones` | Todas las canciones |
| GET | `/api/cancion/<id>` | Detalle de canción |
| GET | `/api/cancion/<id>/lyrics` | Letra (caché + descarga bajo demanda) |
| GET | `/api/artist/<id>/albums` | Álbumes de un artista |
| GET | `/api/artist/<id>/canciones` | Canciones de un artista |
| GET | `/api/album/<id>/canciones` | Canciones de un álbum |
| GET | `/api/similares/<id>` | Canciones similares (top 10) |
| GET | `/api/audio-info/<id>` | Info técnica: sample_rate, bit_depth, channels, BPM, RMS, Peak, Dynamic Range, Nyquist, bit_rate |
| GET | `/api/related/artists/<id>` | Artistas relacionados |
| GET | `/audio/<id>` | Stream del archivo de audio (Hi-Res o transcodificado según calidad del usuario) |
| GET | `/lyrics/<id>` | Contenido de letras (con descarga automática) |
| GET | `/album-art/<id>` | Portada (fallback: API → tag → placeholder) |
| POST | `/api/play/<id>` | Registrar reproducción |
| POST | `/api/translate` | Traducir texto |
| GET | `/api/stats` | Estadísticas por ventana de tiempo (`?period=week\|month\|day\|all`) |
| GET | `/api/events/stream` | Bus en tiempo real con Server-Sent Events (SSE) |
| GET | `/api/events/status` | Estado de conexión del bus SSE |

### Biblioteca y Álbumes Guardados

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/biblioteca/albums` | Álbumes guardados en la biblioteca del usuario |
| POST | `/api/biblioteca/albums/<id>/toggle` | Guardar o quitar un álbum de la biblioteca |
| GET | `/api/biblioteca/albums/<id>/check` | Verificar si un álbum está guardado |

### Editor de Etiquetas (In-App Tagger)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/song/<id>/tags` | Leer tags físicos del archivo de audio (Mutagen) |
| POST | `/api/song/<id>/tags` | Escribir tags en archivo físico y sincronizar base de datos |

### Recetas, Mezclas y Estaciones

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/recipes/balance` | Balancear cola aplicando la regla de distanciamiento (Gap Rule) |
| GET | `/api/station/track/<id>` | Radio dinámica a partir de la firma acústica de una pista |
| GET | `/api/station/artist/<id>` | Radio dinámica centrada en un artista y artistas relacionados |

### Paletas y Colores Adaptativos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/album/<id>/colors` | Paleta cromática dominante extraída de la carátula con Pillow |
| GET | `/api/song/<id>/colors` | Paleta cromática para ambientar el reproductor en tiempo real |

### Favoritos

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/favoritos` | IDs de favoritos |
| GET | `/api/favoritos/canciones` | Lista completa |
| POST | `/api/favoritos/toggle/<id>` | Alternar favorito |

### Colecciones

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/coleccion-lista` | Listar colecciones |
| POST | `/api/colecciones/crear` | Crear colección |
| POST | `/api/colecciones/<id>/add-cancion/<id>` | Añadir canción |

### Admin (requieren sesión admin o token)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/admin` | Panel de administración |
| POST | `/admin/escanear/start` | Iniciar escaneo completo (encola RQ) |
| POST | `/admin/escanear/quick` | Iniciar escaneo rápido (encola RQ) |
| GET | `/admin/escanear/status/<task_id>` | Estado del escaneo (desde Redis) |
| GET | `/admin/escanear/active` | Escaneo activo actual |
| GET | `/admin/estadisticas` | Estadísticas globales |
| GET | `/admin/check-update` | Verificar versión en GitHub |
| POST | `/admin/enrich-artists` | Enriquecer metadatos |
| GET | `/admin/usuarios` | Listar usuarios |
| POST | `/admin/usuarios/crear` | Crear usuario |
| GET | `/api/lyrics-progress` | Progreso descarga de letras (desde Redis) |
| GET | `/api/mb-progress` | Progreso MusicBrainz (desde Redis) |

Autenticación admin:
- Sesión Flask con rol `admin`
- Header `Authorization: Bearer <ADMIN_SECRET_TOKEN>`
- Header `X-Admin-Token: <ADMIN_SECRET_TOKEN>`

---

## 🔄 Flujo de datos

### Escaneo de biblioteca (completo o rápido)

```
Usuario click "Escanear" en panel Admin
        ↓
POST /admin/escanear/start  (o /quick)
        ↓
Guarda tarea en Redis (scan_task_set)
        ↓
Encola job RQ → RQ Worker lo recibe
        ↓
escanear_carpeta_audio() o escaneo_rapido()
        ↓
  ┌─────────────────────────────────┐
  │  extraer_metadatos_paralelo()   │
  │  (ThreadPoolExecutor, 6 hilos)  │
  │  ├ TinyTag → duración          │
  │  ├ Mutagen → cabeceras técnicas │
  │  └ librosa (si disponible) →   │
  │    RMS, Peak, BPM, Dynamic Range│
  └─────────────────────────────────┘
        ↓
  Detecta archivos nuevos +
  canciones existentes con sample_rate == None
        ↓
  Inserta/actualiza en PostgreSQL (batch de 50)
        ↓
Progress callback escribe en Redis (scan_task_set)
        ↓
Admin page poll cada 1.2s → GET /admin/escanear/status/{id}
        ↓
Lee de Redis → muestra barra de progreso en UI
        ↓
Post-escaneo (worker, 2do plano):
  ├ descargar_letras_segundo_plano()
  ├ enriquecer_artistas_sin_mbid()
  └ run_pretranscode_library()
```

### Calidad de Audio — ¿bloquea al usuario?

```
Escaneo lanzado desde Admin UI:
  → Encola en Redis (RQ)
  → Worker lo procesa en proceso separado
  → Gunicorn (web) NUNCA se bloquea ✅

Análisis técnico dentro del escaneo:
  → Mutagen: solo lee cabeceras de archivo, O(ms) por canción ✅
  → librosa (opcional): analiza hasta 30s de audio en worker,
     NO en el hilo del servidor web ✅
```

### Deduplicación con MusicBrainz

```
obtener_o_crear_artista(nombre):
    1. normalizar_artista(nombre)  → "Blade And Bath"
    2. Buscar por nombre_normalizado en BD
    3. Buscar en MusicBrainz API → MBID
    4. Buscar por MBID en BD
    5. Fuzzy match (token_set_ratio >= 80%)
    6. Crear nuevo artista con MBID + nombre_normalizado
```

### Letras (3 fuentes)

```
obtener_o_descargar_letra(cancion_id):
    1. Cache en RAM (TTL 1h) ← instantáneo
    2. Archivo .lrc local en disco
    3. Búsqueda en disco (rescate)
    4. LRCLIB API (letras sincronizadas)
    5. Lyrics.ovh API (texto plano)
    6. Genius scraping (texto plano)
```

### Calidad de audio por usuario (preferencia de perfil)

```
Perfil → selecciona calidad:
  ├ "Hi-Res Lossless" → stream directo del archivo original (FLAC, WAV, sin pérdida)
  └ "Normal / Comprimida" → stream transcodificado a MP3/OGG por ffmpeg
         (el worker pre-transcodifica en 2do plano para reducir latencia)
```

---

## 📦 Servicios Docker

### Despliegue Estándar (Single-Container Ultra-Ligero)

DuckSound opera por defecto en una arquitectura unificada ultra-ligera en un solo contenedor con SQLite en modo WAL y worker de fondo integrado:

```yaml
services:
  ducksound:
    build: .
    container_name: ducksound
    restart: unless-stopped
    volumes:
      - type: bind
        source: ${MUSIC_PATH}
        target: /music
        read_only: true
      - ducksound_data:/data
    environment:
      - ADMIN_USERNAME=${ADMIN_USERNAME:-ducksound}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD:-ducksound}
      - ADMIN_SECRET_TOKEN=${ADMIN_SECRET_TOKEN:-ducksound_admin_token}
      - SECRET_KEY=${SECRET_KEY:-}
      - PORT=8604
      - WEB_WORKERS=2
      - WEB_THREADS=2
      - LOG_LEVEL=info
    ports:
      - '8604:8604'

volumes:
  ducksound_data:
    driver: local
```

> **Nota:** Para despliegues distribuidos o corporativos, DuckSound también soporta bases de datos externas PostgreSQL (`DATABASE_URL` o `DB_HOST`) y colas externas Redis (`REDIS_HOST`).

---

## 📁 Volúmenes

| Volumen | Contenido |
|---|---|
| Tu música (`/music`, ro) | Biblioteca musical local montada en solo lectura |
| `ducksound_data` (`/data`, rw) | Base de datos SQLite (`ducksound.db`), letras (`.lrc`), carátulas (`album_art`), miniaturas y caché de transcodificación |

---

## ⚙️ Variables de entorno

| Variable | Requerida | Descripción | Default |
|---|---|---|---|
| `MUSIC_PATH` | ✅ | Ruta física absoluta a tu música en el host | — |
| `ADMIN_SECRET_TOKEN` | ✅ | Token Bearer para endpoints de `/admin/*` y API administrativa | `ducksound_admin_token` |
| `ADMIN_USERNAME` | ❌ | Nombre de usuario administrador inicial | `ducksound` |
| `ADMIN_PASSWORD` | ❌ | Contraseña del usuario administrador inicial | `ducksound` |
| `PORT` | ❌ | Puerto de enlace del servidor web | `8604` |
| `WEB_WORKERS` | ❌ | Número de workers Gunicorn | `2` |
| `WEB_THREADS` | ❌ | Hilos por worker Gunicorn | `2` |
| `DATABASE_URL` | ❌ | URL de conexión de base de datos externa (PostgreSQL) | SQLite en `/data/ducksound.db` |
| `REDIS_HOST` | ❌ | Host de servidor Redis opcional | — |
| `LOG_LEVEL` | ❌ | Nivel de registro (debug, info, warning, error) | `info` |
| `SECRET_KEY` | ❌ | Clave secreta para cookies de sesión Flask | Auto-generada y persistida en `.secret_key` |

---

## 🗄️ Modelo de Datos — Tabla `canciones`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Identificador único |
| `titulo` | VARCHAR(200) | Título de la canción |
| `artista_id` | FK → artistas | Artista principal |
| `album_id` | FK → albums | Álbum |
| `duracion` | INTEGER | Duración en segundos |
| `ruta_archivo_audio` | VARCHAR(500) | Ruta física absoluta al archivo |
| `ruta_archivo_lrc` | VARCHAR(500) | Ruta al archivo de letra `.lrc` |
| `ruta_imagen_album` | VARCHAR(500) | Ruta a la carátula |
| `numero_pista` | INTEGER | Número de pista en el álbum |
| `numero_disco` | INTEGER | Número de disco (multi-CD) |
| `genero` | VARCHAR(100) | Género musical (ID3/Vorbis) |
| `sample_rate` | INTEGER | Tasa de muestreo en Hz (ej. 44100, 96000) |
| `bit_depth` | INTEGER | Profundidad de bits (ej. 16, 24) |
| `channels` | INTEGER | Canales de audio (1=Mono, 2=Stereo) |
| `nyquist_freq` | FLOAT | Frecuencia de Nyquist en kHz |
| `dynamic_range` | FLOAT | Rango dinámico en dB |
| `peak_level` | FLOAT | Nivel de pico máximo en dBFS |
| `rms_level` | FLOAT | Sonoridad RMS promedio en dBFS |
| `bpm` | FLOAT | Tempo en Beats Por Minuto |
| `total_samples` | BIGINTEGER | Total de muestras en el archivo |
| `bit_rate` | INTEGER | Tasa de bits en bps (ej. 1411200 = 1411 kbps) |
| `fecha_agregada` | DATETIME | Fecha de indexación |

---

## 📄 Licencia

**GNU Affero General Public License v3.0 (AGPLv3)**

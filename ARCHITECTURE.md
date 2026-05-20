# 🏗️ Arquitectura y Referencia Técnica

## Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                      DuckSound Server                        │
│                                                              │
│  ┌─────────────┐    ┌──────────┐    ┌──────────────────┐    │
│  │  Gunicorn    │    │  Redis   │    │   RQ Worker      │    │
│  │  4 workers   │◀──▶│  Queue + │◀──▶│  (proceso       │    │
│  │  2 threads   │    │  Cache   │    │   separado)      │    │
│  │              │    └──────────┘    │                  │    │
│  │  ├ routes/  │         │          │  ├ run_full_scan │    │
│  │  │  main.py │         │          │  ├ run_quick_scan│    │
│  │  │  audio.py│         │          │  ├ enriquecer    │    │
│  │  │  api.py  │         │          │  └ descargar_lrc │    │
│  │  │  admin.py│         │          └──────────────────┘    │
│  │  └  browse.py         │                                  │
│  └──────┬──────┘         │                                  │
│         │                ▼                                  │
│         ▼        ┌──────────┐                               │
│  ┌──────────┐    │  /data   │                               │
│  │PostgreSQL│    │ (letras, │                               │
│  │(usuarios,│    │  covers) │                               │
│  │  música, │    └──────────┘                               │
│  │  stats)  │                                               │
│  └──────────┘                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Estructura del Proyecto

```
DuckSound/
├── app.py                  # Punto de entrada de la aplicación Flask
├── app/
│   ├── __init__.py         # Factory create_app(), blueprints, smart_url_for()
│   ├── models.py           # SQLAlchemy: Usuario, Artista, Album, Cancion, Playlist
│   │
│   ├── routes/
│   │   ├── main.py         # Dashboard, perfil, letras, favoritos, artistas, álbumes
│   │   ├── audio.py        # Streaming de audio, portadas, transcoding
│   │   ├── api.py          # API JSON: canciones, info técnica, similares, playlists
│   │   ├── admin.py        # Panel admin: escaneo, usuarios, estadísticas
│   │   └── browse.py       # Exploración: géneros, artistas, álbumes, búsqueda
│   │
│   ├── services/
│   │   ├── scanner.py      # Motor de escaneo completo e incremental (análisis paralelo)
│   │   ├── audio_analyzer.py  # Análisis técnico: sample_rate, bit_depth, BPM, RMS, Peak
│   │   ├── transcoder.py   # Transcodificación bajo demanda (MP3/OGG para baja calidad)
│   │   ├── lyrics.py       # LRCLIB + Lyrics.ovh + Genius (descarga en 2do plano)
│   │   ├── metadata.py     # MusicBrainz API (MBID, deduplicación, enriquecimiento)
│   │   ├── recommender.py  # Motor de recomendaciones acústico-híbrido
│   │   ├── queue.py        # Conexión Redis, RQ queue, enqueue helper
│   │   └── tasks.py        # Funciones RQ: run_full_scan, run_quick_scan
│   │
│   ├── templates/          # 20+ templates Jinja2
│   │   ├── base.html       # Layout principal + reproductor + modal Audio Quality
│   │   ├── dashboard.html  # Página principal del usuario
│   │   ├── profile.html    # Perfil, estadísticas, preferencias de calidad
│   │   ├── admin/          # Panel de administración
│   │   └── ...
│   │
│   └── static/
│       ├── css/style.css   # Design system dark theme + responsive + audio-info grid
│       ├── js/
│       │   ├── player_parent.js   # Bridge iframe: controles, letras, cola, toast
│       │   ├── player_frame.js    # Engine de audio: reproducción, crossfade, cola
│       │   └── album_card_player.js  # Play desde tarjetas de álbum
│       └── img/            # Logo SVG, favicon
│
├── config.py               # Config: Docker/local, PostgreSQL, rutas, versión
├── run_worker.py           # Entrypoint del worker RQ
├── merge_duplicates.py     # Script de fusión de artistas/álbumes duplicados
├── clean_db.py             # Script de limpieza de base de datos
├── entrypoint.sh           # Migraciones automáticas + inicio de servicios
├── Dockerfile              # Python 3.10-slim + libsndfile + ffmpeg
├── docker-compose.yml      # 4 servicios: postgres + redis + web + worker
├── CHANGELOG.md            # Historial de versiones
└── requirements.txt        # Dependencias Python
```

---

## 🧱 Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Backend | Flask 3.0, SQLAlchemy, Werkzeug |
| Arquitectura | Blueprints modulares (`main`, `audio`, `api`, `admin`, `browse`) |
| Base de datos | PostgreSQL 16 |
| Cache / Queue | Redis 7 + RQ (Redis Queue) |
| Audio parsing | Mutagen (cabeceras rápidas), TinyTag (duración), librosa/numpy (DSP avanzado, opcional) |
| Transcodificación | ffmpeg (bajo demanda, en worker, basado en preferencia de calidad del usuario) |
| APIs externas | MusicBrainz (MBID), Deezer (fotos/portadas), LRCLIB + Lyrics.ovh + Genius (letras) |
| Traducción | LibreTranslate (primario) / Google Translate (fallback) |
| Frontend | HTML5, CSS3 (custom design system dark), JavaScript vanilla, Jinja2 |
| Reproductor | Arquitectura iframe + postMessage (persistente entre páginas) |
| Servidor web | Gunicorn (4 workers, 2 threads, gthread) |
| Contenedor | Docker + docker-compose (4 servicios) |
| CI/CD | GitHub Actions (pytest + build Docker) |

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

```yaml
services:
  postgres:  # Base de datos principal
    image: postgres:16-alpine
    volumes: postgres_data:/var/lib/postgresql/data

  redis:     # Cola RQ + cache de estado + caché de recomendaciones
    image: redis:7-alpine
    volumes: redis_data:/data

  web:       # Servidor Flask + Gunicorn (4 workers, 2 threads)
    build: .
    command: web  # entrypoint.sh web
    depends_on: [postgres, redis]
    ports: 8604:8604

  worker:    # Procesador de tareas background (RQ)
    build: .
    command: worker  # entrypoint.sh worker
    depends_on: [postgres, redis]
    # Tareas: escaneo, letras, MusicBrainz, pretranscodificación
```

---

## 📁 Volúmenes

| Volumen | Contenido |
|---|---|
| Tu música (`/music`, ro) | Biblioteca musical del usuario (solo lectura) |
| `ducksound_data` (`/data`, rw) | Letras (.lrc), carátulas (covers), transcodes cacheados |
| `postgres_data` | Datos de PostgreSQL |
| `redis_data` | Datos de Redis |

---

## ⚙️ Variables de entorno

| Variable | Requerida | Descripción | Default |
|---|---|---|---|
| `MUSIC_PATH` | ✅ | Ruta a tu música en el host | — |
| `ADMIN_SECRET_TOKEN` | ✅ | Token para endpoints `/admin/*` | — |
| `DB_PASSWORD` | ❌ | Contraseña PostgreSQL | `ducksound` |
| `REDIS_HOST` | ❌ | Host de Redis | `redis` |
| `LOG_LEVEL` | ❌ | Nivel de log | `info` |
| `SECRET_KEY` | ❌ | Clave de sesión Flask | Auto-generada |

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

# 🏗️ Arquitectura y Referencia Técnica

## Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                      DuckSound Server                        │
│                                                              │
│  ┌─────────────┐    ┌──────────┐    ┌──────────────────┐    │
│  │  Gunicorn    │    │  Redis   │    │   RQ Worker      │    │
│  │  1 worker    │◀──▶│  Queue + │◀──▶│  (proceso       │    │
│  │  8 threads   │    │  State   │    │   separado)      │    │
│  │              │    └──────────┘    │                  │    │
│  │  ├ app.py   │         │          │  ├ run_full_scan │    │
│  │  ├ routes.py│         │          │  ├ run_quick_scan│    │
│  │  └ tasks.py │         │          │  └ enriquecer    │    │
│  └──────┬──────┘         │          └──────────────────┘    │
│         │                │                                  │
│         ▼                ▼                                  │
│  ┌──────────┐    ┌──────────┐                               │
│  │PostgreSQL│    │  /data   │                               │
│  │(usuarios,│    │ (letras, │                               │
│  │  música, │    │  covers) │                               │
│  │  stats)  │    └──────────┘                               │
│  └──────────┘                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Estructura del Proyecto

```
DuckSound/
├── app.py                  # Flask: auth, dashboard, perfil, streaming, traducción
├── routes.py               # Blueprints: admin, api (JSON), browse (exploración)
├── models.py               # SQLAlchemy: Usuario, Artista, Album, Cancion, etc.
├── config.py               # Config: Docker/local, PostgreSQL, rutas, versión
├── task_queue.py           # Conexión Redis, RQ queue, tracking de escaneo/letras/MB
├── tasks.py                # Funciones RQ: escaneo completo, escaneo rápido
├── run_worker.py           # Entrypoint del worker RQ
│
├── scan_songs.py           # Escáner de biblioteca, extracción de metadatos
├── audio_analyzer.py       # Análisis de calidad con librosa/numpy
│
├── metadata_normalizer.py  # Normalización de nombres, detección de versiones
├── metadata_fetcher.py     # Deezer API (fotos, portadas)
├── musicbrainz_client.py   # MusicBrainz API (MBID, romanización, rate limiting)
│
├── lyrics_fetcher.py       # LRCLIB + Lyrics.ovh + Genius (letras)
├── recommender.py          # Motor de recomendaciones híbrido
│
├── merge_duplicates.py     # Script de fusión de artistas/álbumes duplicados
├── templates/              # 23+ templates Jinja2
├── static/
│   ├── css/style.css       # Design system dark theme + responsive
│   ├── js/
│   │   ├── player_parent.js  # Bridge iframe: controles, letras, cola, toast
│   │   ├── player_frame.js   # Engine de audio: reproducción, crossfade, cola
│   │   └── album_card_player.js  # Play desde tarjetas de álbum
│   └── img/                # Logo SVG, favicon, logo-app
│
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
| Base de datos | PostgreSQL 16 |
| Cache / Queue | Redis 7 + RQ (Redis Queue) |
| Audio parsing | Mutagen, TinyTag, librosa, SoundFile |
| APIs externas | MusicBrainz (deduplicación), Deezer (fotos/portadas), LRCLIB + Lyrics.ovh + Genius (letras) |
| Traducción | LibreTranslate (primario) / Google Translate (fallback) |
| Frontend | HTML5, CSS3 (custom design system), JavaScript vanilla, Jinja2 |
| Reproductor | Arquitectura iframe + postMessage (persistente entre páginas) |
| Servidor web | Gunicorn (1 worker, 8 threads, gthread) |
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
| GET | `/api/audio-info/<id>` | Info técnica del audio |
| GET | `/api/related/artists/<id>` | Artistas relacionados |
| GET | `/audio/<id>` | Stream del archivo de audio |
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

### Escaneo de biblioteca

```
Usuario click "Escanear"
        ↓
routes.py → POST /admin/escanear/start
        ↓
Guarda tarea en Redis (scan_task_set)
        ↓
Encola job RQ (task_queue.enqueue)
        ↓
RQ Worker ejecuta tasks.run_full_scan(task_id)
        ↓
scan_songs.escanear_carpeta_audio(progress_callback)
        ↓
Progress callback escribe en Redis (scan_task_set)
        ↓
Admin page poll cada 1.2s → GET /admin/escanear/status/{id}
        ↓
Lee de Redis → muestra barra de progreso
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

---

## 📦 Servicios Docker

```yaml
services:
  postgres:  # Base de datos principal
    image: postgres:16-alpine
    volumes: postgres_data:/var/lib/postgresql/data

  redis:     # Cola RQ + estado persistente
    image: redis:7-alpine
    volumes: redis_data:/data

  web:       # Servidor Flask + Gunicorn
    build: .
    command: web  # entrypoint.sh web
    depends_on: [postgres, redis]
    ports: 8604:8604

  worker:    # Procesador de tareas background
    build: .
    command: worker  # entrypoint.sh worker
    depends_on: [postgres, redis]
```

---

## 📁 Volúmenes

| Volumen | Contenido |
|---|---|
| Tu música (`/music`, ro) | Biblioteca musical del usuario |
| `ducksound_data` (`/data`, rw) | Letras, carátulas |
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

## 📄 Licencia

**GNU Affero General Public License v3.0 (AGPLv3)**

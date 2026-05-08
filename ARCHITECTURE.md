# 🏗️ Arquitectura y Referencia Técnica

## 🏗️ Estructura del Proyecto

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

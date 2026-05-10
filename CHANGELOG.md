# Changelog

Todos los cambios notables de DuckSound serán documentados en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## [1.2.0] - 2026-05-10

### 🎯 Deduplicación 100% de Artistas y Álbumes
- **MusicBrainz ID**: Integración con MusicBrainz API para identificar artistas por UUID único.
- **Rate limiting**: Respeto de 1 request/segundo con User-Agent obligatorio.
- **nombre_normalizado**: Nueva columna que almacena el nombre canónico del artista.
- **Fuzzy matching**: Búsqueda por similitud (`token_set_ratio >= 80%`) como respaldo.
- **UNIQUE constraints**: Índices en BD para `musicbrainz_id` y `nombre_normalizado`.
- **Romanización automática**: Artistas en japonés/chino/coreano se convierten a su nombre latino vía MusicBrainz sort_name/aliases.
- **`merge_duplicates.py`**: Script con 3 niveles de fusión (MBID → nombre_normalizado → fuzzy 75%).

### 🔄 Sistema de Tareas Background Escalable
- **Redis + RQ**: Tareas post-escaneo (letras + MusicBrainz) ahora se encolan en Redis.
- **Worker dedicado**: Nuevo servicio `worker` en docker-compose para procesar colas.
- **Fallback automático**: Si Redis no está disponible, usa hilos como respaldo.
- **Entrypoint inteligente**: `entrypoint.sh web|worker|migrate-only` con migraciones automáticas al iniciar.
- **Migraciones automáticas**: WAL mode, columnas MBID, índices UNIQUE — todo se ejecuta solo.
- **Arquitectura multi-servicio**: docker-compose con 3 servicios (redis + web + worker).

### 🎨 Interfaz Spotify-Style
- **Rediseño completo del tracklist**: Grid `40px 40px 1fr 1fr 60px`, cover, hover effects.
- **Equalizer animado**: Barras verdes animadas reemplazan el número de pista al reproducir.
- **Indicador dinámico**: La clase `playing` se mueve automáticamente al cambiar de canción.
- **Up next mejorado**: Muestra hasta 20 canciones, incluye la canción actual como referencia.
- **Similares rediseñados**: Mismo estilo visual que las listas de canciones, con badge de porcentaje.
- **Panel derecho independiente**: Ya no se reemplaza durante navegación SPA — nunca pierde estado.
- **Traductor siempre visible**: Botón de traducir en el toolbar de letras, con check "Auto" tipo switch.

### 🚀 Optimizaciones de Rendimiento
- **Commits más frecuentes**: Batch size reducido de 100 a 50 canciones para write locks más cortos.
- **Caché de letras en RAM**: Las letras se cachean en memoria con TTL de 1 hora — segunda carga instantánea.
- **Timeouts de seguridad**: Traducción con timeout de 12 segundos para evitar botones trabados.
- **Arranque sin bloqueos**: Background tasks ya no bloquean el servidor web.

### 🐛 Correcciones
- **Botón de repeat fijo**: `fa-repeat-1` era un icono Pro inexistente. Reemplazado por badge CSS "1".
- **Normalización de artistas**: Separación por `, & / vs` + protección contra falsos como "Blade And Bath".
- **Unificación de "The"**: "Smith, The" → "The Smith" para evitar duplicados.
- **Scan no funcionaba**: Corregido error sintáctico al eliminar código legacy.

### 🧹 Limpieza
- **Código muerto eliminado**: `player.js`, `like_button_dynamic.js`, `global_gmsec.css`.
- **Funciones obsoletas**: `_extraer_metadatos_mutagen_legacy`, `descargar_letra_lrc`, `normalizar_titulo`.
- **Imports no usados**: `json`, `defaultdict`, `math`, `os` eliminados.
- **CSS duplicado**: `.lyrics-toolbar`, `.btn` repetidos eliminados.

### 🐳 Docker
- **Entrypoint automático**: `entrypoint.sh` ejecuta migraciones y configura el servicio.
- **Modos de inicio**: `web` (Gunicorn), `worker` (RQ), `migrate-only`.
- **Gunicorn con gthread**: 4 workers × 2 hilos para mejor concurrencia.
- **Healthcheck en Redis**: docker-compose espera a que Redis esté listo antes de iniciar web/worker.

---

## [1.1.0] - 2026-05-08

### 🚀 Optimizaciones de Rendimiento
- **Escaneo de música ultra-rápido**: Implementado commits en bloque cada 100 canciones en lugar de por cada canción
- **Análisis de audio optimizado**: librosa.load ahora analiza solo 30 segundos desde el segundo 30 (o carga completa si es < 60s)
- **Eliminadas peticiones HTTP síncronas**: Las letras ya no se descargan durante el escaneo principal
- **Enriquecimiento asíncrono**: Metadatos de artistas solo se procesan al final del escaneo

### 🎵 Sistema de Letras Mejorado
- **Detección local robusta**: Búsqueda de letras en múltiples ubicaciones (misma carpeta, LYRICS_FOLDER, por ID, case-insensitive)
- **Lógica de rescate**: Si una canción no tiene letra en BD, busca automáticamente en disco antes de ir a API
- **Endpoint API**: `/api/cancion/<int:cancion_id>/lyrics` con caché local y descarga bajo demanda
- **Headers User-Agent**: Corregido Error 403 de Wikipedia con `DuckSound/1.0 (contacto@ejemplo.com)`

### 🎧 Sistema de Recomendaciones Optimizado
- **Pesos balanceados**: Corregidos porcentajes (antes 6000%, ahora máximo 80%)
- **Mejor scoring**: Pesos ajustados a Género (35%), Acústico (35%), Artista (10%)

### 🖥️ Mejoras de UI/UX
- **Menú contextual**: Click derecho en canciones con opciones (Reproducir siguiente, Añadir a cola, Añadir a playlist, Ir al álbum/artista)
- **Sin reproducción automática**: La música ya no comienza sola al recargar la página
- **Sincronización de letras**: Corregido conflicto entre sistemas de letras, ahora sincroniza correctamente con la música actual

### 🐛 Correcciones de Bugs
- **Salto de carpetas de discos**: El escaneo ahora ignora carpetas "CD 1", "Disc 2", etc. y usa carpetas superiores
- **Logs optimizados**: El aviso de "librosa no disponible" solo se muestra una vez al inicio
- **Limpieza de temporales**: Eliminados scripts de desarrollo innecesarios

### 🔧 Mejoras Técnicas
- **User-Agent consistente**: Todas las peticiones a APIs externas usan `DuckSound/1.0 (app_music)`
- **Error 403 Wikipedia**: Solucionado con headers obligatorios
- **Imports optimizados**: Mejor manejo de dependencias faltantes
- **Caché mejorado**: Sistema de caché con TTL para recomendaciones

### 📱 PWA (Progressive Web App)
- **Service Worker**: Registro automático para instalación como app nativa
- **Manifest JSON**: Configuración para instalación en pantalla de inicio
- **Modo offline**: Soporte básico para funcionalidad sin internet

---

## [1.0.1] - Versiones anteriores
- Versión inicial estable
- Sistema básico de reproducción y escaneo
- Interfaz web responsive

## [1.0.0] - 2026-05-07

### 🎉 Lanzamiento Inicial — "First Flight"

#### Reproductor de Audio
- Reproductor web completo con controles de play/pausa, siguiente, anterior, avance y retroceso 10 segundos
- Barra de progreso clickeable con indicador de tiempo actual y duración total
- Control de volumen con slider, icono dinámico y toggle de mute
- Modos de reproducción: Shuffle (aleatorio) y Repeat (ninguno / una / todas)
- Crossfade configurable entre canciones para transiciones suaves
- Arquitectura persistente con iframe y postMessage — la música no se interrumpe al navegar
- Color adaptativo de la interfaz basado en los colores dominantes de la portada del álbum actual

#### Letras Sincronizadas
- Soporte para archivos .lrc con marcas de tiempo
- Descarga automática de letras desde LRCLIB durante el escaneo de biblioteca
- Highlight de la línea activa con scroll automático en tiempo real
- Click en cualquier línea para saltar a ese punto de la canción
- Traducción de letras al idioma preferido del usuario vía LibreTranslate y Google Translate

#### Biblioteca y Organización
- Escaneo recursivo de carpetas de audio (MP3, FLAC, WAV, M4A, OGG)
- Extracción de metadatos ID3v2 y Vorbis Comments (título, artista, álbum, género, número de pista, duración)
- Inferencia inteligente de artista y álbum desde la estructura de carpetas cuando no hay metadatos
- Normalización de nombres de artistas y detección de versiones de álbumes (Deluxe, Remastered, Live, etc.)
- Reparación automática de rutas para canciones que cambiaron de ubicación en disco
- Navegación completa: explorar, artistas, álbumes, carpetas (vista tipo árbol de directorios)
- Sistema de favoritos (Me gusta) con toggle rápido desde el reproductor
- Playlists personalizadas para agrupar canciones manualmente
- Daily Mixes generados automáticamente basados en favoritos, géneros e historial de escucha

#### Enriquecimiento de Metadatos
- Fotos de artistas en alta resolución desde Deezer API
- Biografías de artistas desde Wikipedia (español → inglés como fallback)
- Portadas de álbumes desde Deezer API e iTunes Search API
- Año de lanzamiento de álbumes desde Deezer
- Extracción de portadas embebidas en archivos de audio (APIC en MP3, PICTURE en FLAC)
- Fallback inteligente de portadas: API → tag embebido → placeholder SVG

#### Motor de Recomendaciones
- Modelo híbrido de scoring con 5 factores ponderados: género (35%), artista (25%), análisis acústico (20%), álbum (10%), duración (10%)
- Similitud acústica basada en dynamic range, RMS level y bit rate
- Diversidad forzada: máximo 2 canciones del mismo álbum y 3 del mismo artista en recomendaciones
- Artistas relacionados calculados por géneros compartidos
- Panel visual de canciones similares con porcentaje de afinidad

#### Análisis de Audio
- Extracción de métricas de calidad por canción: sample rate, bit depth, canales, bit rate
- Análisis de señal con NumPy y SoundFile: dynamic range, peak level, RMS level, frecuencia de Nyquist
- Datos accesibles vía API REST para cada canción

#### Usuarios y Personalización
- Sistema de autenticación con hash seguro (Werkzeug) y roles admin/usuario
- Creación automática de usuario admin en primer inicio (admin / admin123)
- Historial de escucha con tracking de skips (respeta configuración de privacidad del usuario)
- Perfil de usuario con estadísticas: top canciones, top artistas, total reproducciones, horas escuchadas, últimas 24h
- Preferencias configurables: crossfade, idioma de traducción, tracking de actividad
- Nombre público opcional diferente al nombre de usuario

#### Panel de Administración
- Dashboard admin con acciones rápidas de escaneo, usuarios y estadísticas
- Escaneo asíncrono con barra de progreso en tiempo real y fase de enriquecimiento
- Estadísticas globales: totales de canciones, artistas, álbumes, usuarios, reproducciones, favoritos, colecciones
- Top canciones global, top artista, top género más escuchado
- Gestión de usuarios: crear nuevos usuarios con roles, listar existentes
- Verificador de actualizaciones automático contra GitHub Releases
- Changelog integrado colapsable parseado desde CHANGELOG.md
- Protección por sesión admin y/o token Bearer (ADMIN_SECRET_TOKEN)

#### Despliegue
- Dockerfile optimizado: Python 3.10-slim + libsndfile + ffmpeg
- docker-compose.yml con dos volúmenes: música (read-only) + datos de la app (persistente)
- Detección automática de entorno Docker vs local en la configuración
- Mapeo inteligente de rutas Windows a rutas Docker (/music) para migración transparente
- Compatible con Docker Compose, Portainer y CasaOS
- Usuario solo configura MUSIC_PATH y ADMIN_SECRET_TOKEN

#### Interfaz
- Design system dark theme completo con variables CSS personalizadas
- Sidebar de navegación persistente con logo, menú y sección de usuario
- Panel lateral derecho con tres tabs: Cola de reproducción, Letras, Canciones similares
- Dashboard tipo Spotify con Daily Mixes, álbumes recientes, artistas recientes y canciones recientes
- 23 templates Jinja2 responsive con diseño coherente
- Micro-animaciones y transiciones suaves en toda la interfaz

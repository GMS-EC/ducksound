# Changelog

Todos los cambios notables de DuckSound serán documentados en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

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

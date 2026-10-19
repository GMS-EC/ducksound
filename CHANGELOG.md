# Changelog

Todos los cambios notables de DuckSound están documentados en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y se adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [2.0.0] - 2026-10-19

### 🚀 Transformación Total de la Plataforma (Next-Gen Architecture)

Esta versión representa una refundación técnica y visual completa de DuckSound. La plataforma evolucionó de una aplicación basada en plantillas tradicionales a una arquitectura desacoplada moderna: frontend SPA reactivo de alto rendimiento (React 18 + TypeScript + Vite) y backend Flask RESTful/SSE enriquecido con motores avanzados de audio, metadatos, recetas inteligentes y streaming continuo.

---

### 🎨 Frontend React 18 SPA (Arquitectura Moderna y Fluida)
- **Migración Integral a React 18 + TypeScript + Vite**: Sustitución definitiva de las plantillas Jinja2 por una Single Page Application (SPA) con tipado estricto, compilación instantánea y arquitectura modular.
- **Diseño Glassmorphism Premium**: Paleta cromática profunda en modo oscuro con bordes translúcidos, desenfoque de fondo (`backdrop-filter: blur`), gradientes adaptativos y microanimaciones suaves.
- **Gestión Global de Estado**:
  - `PlayerContext`: Motor de reproducción centralizado con soporte para colas dinámicas, reproducción sin pausa, volumen logarítmico persistente en `localStorage`, shuffle aleatorio sin reemplazo y bucle (repeat all / repeat one).
  - `AuthContext`: Gestión de ciclo de vida de sesión, autenticación con tokens y recuperación rápida de perfil.
  - `ContextMenuContext`: Menú contextual flotante personalizable accesible en toda la aplicación (Reproducir siguiente, Añadir a la cola, Añadir a playlist, Editar etiquetas, Ir al artista/álbum).
- **Modo Pantalla Completa con Letras Karaoke**:
  - Vista inmersiva con fondo desenfocado generado dinámicamente a partir de la carátula.
  - Letras sincronizadas línea por línea con tipografía grande, transiciones de opacidad y desplazamiento automático centrado.
  - Carátula con relación de aspecto cuadrada protegida contra desbordamientos en cualquier resolución de pantalla.
  - Barra de progreso interactiva con seeking preciso sin reinicios involuntarios.
- **Panel Lateral Dinámico (RightPanel)**:
  - Pestañas conmutables entre Cola de Reproducción ("Up Next") con drag/remove y Letras en tiempo real sincronizadas con la reproducción actual.
- **Modal de Edición de Etiquetas en Caliente (`EditTagsModal`)**:
  - Interfaz gráfica para editar título, artista, álbum, año, género, número de pista y disco directamente desde la interfaz web.

---

### 🔊 Motor de Audio Avanzado, Gapless y Transcodificación
- **Reproducción Continua (True Gapless Playback)**:
  - Módulo `app/services/silence.py` basado en el filtro `silencedetect` de FFmpeg para calcular milisegundos de silencio inicial (*leading silence*) y final (*trailing silence*).
  - Traspaso de metadatos de padding al frontend para crossfade y transiciones inmediatas sin pausas mecánicas de compresión.
- **Streaming HTTP 206 con Byte-Ranges**:
  - Streaming directo con cabeceras `Accept-Ranges: bytes`, `Content-Range` y `206 Partial Content` en `app/routes/audio.py` para rebobinado, adelanto instantáneo y carga parcial de búferes.
  - Transcodificación al vuelo a MP3 de alta fidelidad con caché en disco (`Config.TRANSCODE_CACHE_FOLDER`) para clientes con ancho de banda reducido o formatos incompatibles.
- **Resolución Universal de Rutas Físicas**:
  - Unificación de rutas de almacenamiento mediante `resolver_ruta_fisica()`, soportando indistintamente rutas absolutas Linux/Docker (`/music/...`) y montajes de host Windows (`E:/...`).

---

### 🏷️ Editor de Etiquetas en Almacenamiento (In-App Tagger)
- **Escritura Nativa de Tags en Archivos**:
  - Módulo `app/services/tagger.py` con Mutagen para modificar ID3v2.3/ID3v2.4 (MP3), Vorbis Comments (FLAC/OGG) y MP4 Atoms (M4A/AAC).
  - Actualización atómica en dos fases: escritura en archivo físico en disco y sincronización inmediata de registros correspondientes en base de datos.
  - Endpoints REST dedicados `GET /api/song/<id>/tags` y `POST /api/song/<id>/tags`.

---

### 🧠 Mezclas Inteligentes y Regla de Distanciamiento (Gap Rule)
- **Recetas Dinámicas (`app/services/recipes.py`)**:
  - `Top Mix` ("Tus Más Escuchadas"): Generación de mezclas ponderadas por historial de reproducciones del usuario excluyendo skips rápidos.
  - `Recent Mix` ("Recién Añadidas"): Mezcla de novedades y descubrimientos recientes de la biblioteca.
  - `Track Radio` ("Radio de la Canción"): Estación automática generada a partir de una semilla acústica combinando BPM, RMS, rango dinámico y género difuso.
  - `Artist Radio` ("Radio de Artista"): Mezcla centrada en un artista y artistas relacionados en catálogo.
- **Algoritmo `balance_mix` con Regla de Distanciamiento**:
  - Garantiza que canciones del mismo artista estén separadas por al menos 2 canciones de artistas diferentes, evitando agrupaciones monótonas en las mezclas automáticas.
  - En las radios de canción, la semilla inicial permanece fijada en la posición 0 mientras el resto de la cola se balancea.

---

### 🖼️ Motor Semántico de Carátulas y Paleta de Colores
- **Puntuación y Ranking Semántico (`app/services/coverart.py`)**:
  - Algoritmo de puntuación léxica de nombres de archivo: tokens prioritarios (`front: +8`, `cover: +7`, `folder: +6`, `album: +5`) frente a tokens de descarte (`back: -6`, `spine: -6`, `cd: -3`, `booklet: -8`).
  - Validación geométrica con Pillow: preferencia por relaciones de aspecto cuadradas ($1:1 \pm 10\%$) y resoluciones $\ge 500\text{px}$.
  - Integrado en `app/routes/audio.py:servir_album_art()` para seleccionar la portada frontal genuina antes de caer en extracciones binarias incrustadas o placeholders.
- **Extracción de Colores Dinámica (`app/services/color.py`)**:
  - Cuantización cromática con Pillow para extraer el color dominante y colores vibrantes de cada carátula.
  - Endpoints `/api/album/<id>/colors` y `/api/song/<id>/colors` para alimentar los temas reactivos y el brillo ambiental del reproductor.

---

### 🔍 Búsqueda Global con "Top Result" y Corrección de Cuellos de Botella
- **Identificación de "Mejor Resultado" (Top Result)**:
  - El buscador global en `app/routes/api.py` calcula puntuaciones RapidFuzz `WRatio` combinadas entre artistas, álbumes y canciones para determinar el resultado dominante y destacarlo como tarjeta principal en la interfaz.
- **Eliminación del Cuello de Botella `limit(200)`**:
  - Sustitución de la consulta ciega limitada a 200 canciones por un pool inteligente de candidatos: coincidencias directas por título, artista y álbum mediante `JOIN`, complementadas con temas populares para tolerar erratas tipográficas sin dejar canciones fuera de la búsqueda.
- **Caché Distribuida con Redis**:
  - Resultados indexados con clave `ducksound:cache:search:fuzzy:<query>` y TTL de 300 segundos para respuestas en menos de 5ms.

---

### 🔤 Ordenamiento Inteligente y Soporte Multi-Disco
- **Descarte de Artículos Gramaticales (`get_sort_name`)**:
  - Ordenamiento alfabético que ignora artículos iniciales ("The", "A", "An", "El", "La", "Los", "Las", "Un", "Una", "Le", "Les", "Der", "Die", "Das") para evitar la concentración masiva de artistas bajo las letras "T", "L" o "E".
- **Ordenamiento Numérico Natural (`natural_sort_key`)**:
  - Clasificación humana de cadenas alfanuméricas ("Pista 2" antes de "Pista 10").
- **Posicionamiento Multi-Disco (`get_track_sort_pos`)**:
  - Fórmula canónica $\text{pos} = (\text{disc} \text{ or } 1) \times 1000 + (\text{track} \text{ or } 1)$ en `app/routes/main.py:album_detail()`, garantizando el orden de reproducción fiel en álbumes dobles o recopilatorios de varios volúmenes.

---

### 📊 Estadísticas de Escucha por Ventanas Temporales
- **Endpoint Dinámico `GET /api/stats`**:
  - Consulta de métricas por período con `?period=week|month|day|all`.
  - Reporte de reproducciones completas, omisiones (skips), horas y minutos acumulados en formato legible ("X hrs, Y mins"), top canciones y top artistas en la ventana seleccionada.
  - Filtro dinámico compatible en la vista de perfil de usuario (`/profile`).

---

### ⚡ Bus de Eventos SSE y Vigilancia en Tiempo Real
- **Server-Sent Events (`app/services/events.py`)**:
  - Bus de eventos en tiempo real sin polling a través de `GET /api/events/stream` y `/api/events/status`.
- **Watchdog del Sistema de Archivos (`app/services/watcher.py`)**:
  - Detección reactiva de adiciones, modificaciones y eliminaciones de archivos de audio en la carpeta montada, manteniendo la biblioteca actualizada automáticamente.

---

### 🧹 Limpieza y Optimización Exhaustiva del Backend
- **Purgado de Código Muerto**:
  - Eliminación de más de 140 líneas de código duplicado e inalcanzable en `app/services/scanner.py`.
  - Eliminación de rutinas muertas en `app/routes/audio.py` (`_copy_locks`, `copiar_archivo_original`, `generar_streaming_dinamico`).
- **Eliminación de Consultas N+1**:
  - Optimización de favoritos en `api.py` y `main.py` mediante `JOIN` directo con `Cancion`, reduciendo 50 consultas individuales a 1 sola transacción SQL.
  - Optimización de `main.py:folders()` con carga en memoria de rutas para evitar recorridos recursivos con `count()` en cada directorio.
- **Refactorización de Seguridad en Administración**:
  - Implementación del hook `@admin_bp.before_request` en `app/routes/admin.py`, eliminando 22 verificaciones de autenticación inline redundantes.
- **Unificación de Endpoints**:
  - Consolidación de `/color` y `/colors`, `/cancion/<id>/color` y `/song/<id>/colors`.
  - Delegación de la reescritura de metadatos en `actualizar_tags_disco()` directamente a `app/services/tagger.py`.
  - Eliminación de sesiones expiradas en `session_manager.py` mediante `delete(synchronize_session=False)` atómico.
- **Suite de Pruebas Automatizadas**:
  - 24 tests de integración y normalización ejecutados y validados con 100% de éxito en Docker (`tests/test_backend_routes.py` y `tests/test_normalizacion.py`).

---

## [1.0.0] - 2026-06-04

### 🎉 Lanzamiento Inicial Estable — Versión Consolidada
- **Deduplicación de Artistas y Álbumes**: Integración con MusicBrainz API y UUID canónicos con rate limit estricto.
- **Fuzzy Matching**: Algoritmos de coincidencia difusa con RapidFuzz (`token_set_ratio >= 80%`).
- **Sistema de Tareas Asíncronas**: Colas de procesamiento en segundo plano con Redis y RQ.
- **Sincronización de Letras**: Soporte para archivos `.lrc` con marcas de tiempo y karaoke interactivo.
- **Transmisión de Audio**: Servidor Flask con soporte para formatos FLAC, MP3, WAV, M4A y OGG.
- **Infraestructura Docker**: Despliegue con Docker Compose en servicios separados `web`, `worker` y `redis`.

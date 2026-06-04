# Changelog

Todos los cambios notables de DuckSound serán documentados en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [1.0.0] - 2026-06-04

### 🎉 Lanzamiento Inicial Estable — Versión Consolidada

Este lanzamiento representa el estado consolidado de DuckSound como una aplicación de transmisión de audio moderna, altamente optimizada y robusta. Combina todas las fases de desarrollo en una única base estable `v1.0.0`.

### 🎯 Deduplicación 100% de Artistas y Álbumes
- **Integración con MusicBrainz**: Conexión con MusicBrainz API para identificar a cada artista mediante su UUID único.
- **Respeto de Rate Limit**: Control estricto de peticiones (1 request por segundo) con un User-Agent obligatorio.
- **Nombres Normalizados**: Columna `nombre_normalizado` en base de datos para almacenar el nombre canónico y evitar duplicaciones visuales.
- **Fuzzy Matching**: Algoritmos de comparación aproximada (`token_set_ratio >= 80%`) como respaldo inteligente si el ID de MusicBrainz no está disponible.
- **Romanización de Nombres**: Los nombres de artistas en alfabetos no latinos (japonés, chino, coreano) se traducen/romanizan automáticamente.
- **Fusión en Lote**: Script `merge_duplicates.py` con 3 niveles de fusión para consolidar la base de datos existente.

### 🔄 Sistema de Tareas en Segundo Plano (Background Tasks)
- **Cola en Redis (RQ)**: Las tareas pesadas post-escaneo (descarga de letras y enriquecimiento con MusicBrainz) se gestionan asíncronamente en segundo plano.
- **Worker Dedicado**: Servicio `worker` e entrypoint Docker optimizado para procesar la cola de tareas sin interferir con el servidor web.
- **Fallback a Hilos**: Si la base de datos Redis no está activa, la aplicación emplea hilos locales de forma transparente para evitar interrupciones.
- **Arranque Seguro**: El servidor web arranca de forma instantánea sin sufrir bloqueos causados por tareas persistentes.

### 🎨 Interfaz Premium
- **Rediseño del Tracklist**: Reestructuración completa con grid adaptable (`40px 40px 1fr 1fr 60px`), portadas miniatura y efectos interactivos.
- **Ecualizador Animado**: Gráfico dinámico de barras de audio animadas en color verde que sustituye al número de pista cuando la canción se está reproduciendo.
- **Estado Dinámico**: Sincronización automática de clases del reproductor visual en toda la interfaz al cambiar de pista.
- **Up Next (Cola de reproducción)**: Listado mejorado capaz de mostrar hasta 20 pistas con la canción actual resaltada como punto de referencia.
- **Recomendaciones y Relacionados**: Tarjetas y tracklists de recomendación visualmente unificados con un badge de porcentaje de afinidad.
- **Panel Lateral Fijo**: Rediseño modular e independiente que evita la pérdida de estado del reproductor o las letras al navegar por las páginas del panel principal.
- **Centrado y Navegación**: Vistas de administración y perfil centradas en pantalla con botones para regresar a la página anterior fácilmente.

### 🚀 Optimizaciones de Rendimiento
- **Escaneo Acelerado**: Inserción en bloques (batch commits) de 50 a 100 canciones en lugar de transacciones individuales por cada pista.
- **Análisis de Audio Eficiente**: La herramienta librosa.load analiza únicamente 30 segundos centrales (o pista completa si es menor a 60 segundos) para determinar rangos acústicos.
- **Caché en Memoria (RAM)**: Sistema de caché con TTL de 1 hora para las letras consultadas a la API y el ruteo interno, agilizando segundas cargas.
- **Timeouts de Red**: Límites de tiempo estrictos en peticiones externas para evitar botones o vistas congeladas ante demoras de APIs externas.

### 🎵 Sistema de Letras Mejorado
- **Detección Local Inteligente**: Búsqueda multirruta (mismo directorio, carpeta unificada de letras, case-insensitive) antes de consultar APIs externas.
- **Letras Sincronizadas (.lrc)**: Soporte nativo para marcas de tiempo, desplazamiento suave automático de la línea activa y salto inmediato haciendo clic sobre una frase.
- **Traducción al Instante**: Soporte de traducción bidireccional vía APIs de traducción externas e interruptor de traducción automática "Auto".

### 🎧 Motor de Recomendaciones Balanceado
- **Ponderación Acústica Inteligente**: Scoring basado en Género (35%), Acústico (35%), Artista (10%), Álbum (10%) y Duración (10%).
- **Cálculo de Afinidad**: Búsqueda por similitud de rangos dinámicos, RMS, Nyquist y bitrate.
- **Filtro de Diversidad**: Límite de un máximo de 2 canciones del mismo álbum y 3 del mismo artista en recomendaciones para mayor variedad musical.

### 🎮 Atajos de Teclado e Integración PWA
- **Control por Teclas**: `Espacio` (Play/Pause), `→ / ←` (Avance/Retroceso 10s), `Ctrl+→ / Ctrl+←` (Siguiente/Anterior), `↑ / ↓` (Volumen), `M` (Mute), `S` (Shuffle), `R` (Repeat), `L` (Letras), `U` (Cola).
- **Protección de Escritura**: Desactivación inmediata de atajos de teclado mientras el cursor se encuentre en cajas de entrada o búsqueda.
- **Progressive Web App**: Configuración de Service Worker y `manifest.json` para permitir la instalación nativa en dispositivos móviles y de escritorio.

### 🐳 Arquitectura de Despliegue y Base de Datos
- **Migración a PostgreSQL**: Migración del motor de base de datos a PostgreSQL como única fuente para alta concurrencia.
- **Docker Compose Completo**: Configuración de servicios orquestados en 3 contenedores: `web` (Gunicorn con gthread multitarea), `worker` (RQ) y `redis` (gestión de colas).
- **Entrypoint Automatizado**: Inicialización, aplicación de migraciones y validaciones del sistema automatizadas al encender la app.

### 🧹 Correcciones y Ajustes Generales
- **Corrección de Iconos**: Reemplazo de iconos Pro inexistentes de FontAwesome por elementos nativos de versión libre.
- **Ignorar Subcarpetas**: El motor de escaneo ignora subcarpetas de discos internos (ej. CD 1, Disc 2) organizando correctamente las pistas.
- **Limpieza de Código Legacy**: Eliminación de scripts de prueba antiguos y archivos CSS duplicados para una estructura ligera y moderna.
- **Comentarios en Español**: Documentación y comentarios internos detallados en español en la totalidad del backend y frontend del proyecto para un mantenimiento sumamente sencillo.

---

### 🔧 Refactorización Post-Lanzamiento (Hotfixes y Mejoras — v1.0.0)

#### 🐛 Correcciones de Rutas y Navegación
- **`smart_url_for` Robusto**: Corrección del helper de ruteo interno en `app/__init__.py` para que sea capaz de resolver automáticamente rutas con namespace legacy (ej. `browse.explore`) mapeándolas a los blueprints nuevos (`main`, `audio`, etc.) sin lanzar `BuildError`.
- **Error SQL en Perfil**: Corrección de una excepción `psycopg2 SyntaxError` en el endpoint `/profile` causada por el uso incorrecto de `sqlfunc.desc('plays')`. Reemplazado por `db.desc('plays')` siguiendo la API estándar de SQLAlchemy con PostgreSQL.

#### 🎧 Panel de Calidad de Audio (Audio Info)
- **Diagnóstico de datos vacíos**: Identificación de la causa raíz por la cual el botón de "Calidad de audio" en el reproductor mostraba solo la duración y guiones (`—`) en todos los campos técnicos: la clave del diccionario de análisis en `scanner.py` era `'audio_analysis'` pero el código de extracción guardaba el resultado bajo la clave `'analisis'`.
- **Corrección de clave de diccionario**: En ambas funciones de escaneo (`escanear_carpeta_audio` y `escaneo_rapido`), la asignación `aa = metadatos.get('audio_analysis', {})` fue corregida a `aa = metadatos.get('analisis') or metadatos.get('audio_analysis', {})` para garantizar compatibilidad hacia adelante y hacia atrás.
- **Campo BPM incluido**: Se agregó el campo `bpm` (tempo en Beats Por Minuto) al constructor `Cancion(...)` en ambas funciones de escaneo, al endpoint `/api/audio-info/<id>` y al grid del modal de calidad de audio en `base.html`, con el ícono `fa-heartbeat`.
- **Endpoint `/api/audio-info/<id>` mejorado**: La respuesta JSON ahora incluye el campo `bpm` además de los ya existentes (`sample_rate`, `bit_depth`, `channels`, `nyquist_freq`, `dynamic_range`, `peak_level`, `rms_level`, `total_samples`, `bit_rate`, `genero`).

#### 🔄 Scanner Inteligente de Metadatos Faltantes
- **Detección de registros incompletos en escaneo completo**: `escanear_carpeta_audio` ahora identifica canciones ya indexadas que carecen de `sample_rate` (datos técnicos nulos) y las re-analiza durante el escaneo completo, actualizando todos los campos de calidad sin duplicar registros.
- **Detección de registros incompletos en escaneo rápido**: `escaneo_rapido` ahora calcula la intersección entre `archivos_disco` y `canciones con sample_rate == None` para incluirlas en el pool de análisis paralelo. Esto permite que los archivos ya registrados pero incompletos reciban sus datos técnicos sin necesidad de un escaneo completo.
- **Resumen enriquecido**: El resumen devuelto por `escaneo_rapido` ahora incluye correctamente el campo `actualizadas` con el conteo de canciones que fueron actualizadas (no solo las nuevas), y el mensaje final lo refleja visualmente.
- **Sin bloqueo del servidor**: Todo el análisis de calidad de audio ocurre dentro del **worker RQ** (proceso separado), por lo que nunca bloquea el servidor web Gunicorn ni las peticiones de los demás usuarios.

#### ⚙️ Mejoras de Robustez del Analizador de Audio
- **Fallback de librosa documentado**: El `audio_analyzer.py` usa librosa cuando está disponible para análisis avanzado (RMS, Peak, Dynamic Range, BPM). Cuando librosa no está instalado en el contenedor, la app recae automáticamente en el análisis básico con Mutagen (extracción de cabeceras: `sample_rate`, `bit_depth`, `channels`, `bit_rate`) sin errores ni caídas.
- **Análisis paralelo con ThreadPoolExecutor**: El proceso `extraer_metadatos_paralelo` ya usa múltiples hilos (hasta 6 workers) para extraer metadatos técnicos de todos los archivos de forma concurrente, con un impacto mínimo en la I/O del disco.

#### 📝 Gestor, Editor y Sincronizador de Letras (LRC)
- **Panel CRUD en Administración**: Añadida la tarjeta de acción "Gestionar letras" en el panel principal con un buscador debounce de 300ms y badges informativos sobre el formato y sincronización.
- **Sincronizador Interactivo por Renglones**: Modal interactivo con editor plano y timeline de líneas que permite estampar marcas de tiempo en caliente presionando la `Barra Espaciadora` con scroll suave y centrado automático.
- **Control de Velocidad (playbackRate)**: Selector dinámico para reproducir el audio a velocidad reducida (0.5x a 1.5x) para mayor precisión.
- **Prevención de Condiciones de Carrera**: Sistema de descarte para peticiones asíncronas tardías cuando el usuario cambia de canción rápidamente e indicadores de carga (`fa-spinner`).

#### 💿 Gestor de Álbumes e Invalidation de Caché de Imágenes
- **Módulo CRUD de Álbumes**: Panel premium de gestión de álbumes (`admin_albumes.html`) y tarjeta de acción rápida en administración para editar títulos, años de lanzamiento, MBID y Deezer Album ID.
- **Metadatos y Portada Deezer**: El backend resuelve de forma transparente portadas de alta resolución desde Deezer, guardándolas como `portada_url` en base de datos.
- **Evicción de Caché Física y Cabeceras de Revalidación**: El servidor borra automáticamente los archivos de miniaturas WebP (`thumb_*.webp`) al cambiar la portada de un álbum, y sirve `/album-art/` bajo la directiva `Cache-Control: public, no-cache, must-revalidate`, forzando al navegador a solicitar cambios rápidos con ETag/304.
- **Refresco en Caliente del DOM**: Inyección dinámica en el cliente de query parameters (`?t=timestamp`) a todas las imágenes de portada del DOM tras guardar cambios, propagando el arte al mini-reproductor y tracklists al instante sin pausar la música.


# Changelog

Todos los cambios notables de DuckSound serán documentados en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [1.0.0] - 2026-05-20

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

### 🎨 Interfaz Premium (Estilo Spotify-Style)
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

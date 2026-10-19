# 🦆 DuckSound

**DuckSound** es un servidor de streaming de música personal, self-hosted, con interfaz web estilo Spotify, reproductor persistente, letras automatizadas desde múltiples fuentes, deduplicación con MusicBrainz, análisis técnico de calidad de audio y recomendaciones inteligentes.

![React](https://img.shields.io/badge/React-18-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)
![Vite](https://img.shields.io/badge/Vite-5-purple)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey)
![Python](https://img.shields.io/badge/Python-3.10+-yellow)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-AGPL_v3-blue)
[![Sponsor](https://img.shields.io/badge/Sponsor-Takenos-orange)](https://app.takenos.com/pay/b6515307-a660-446d-8117-3214a4a89a80)

<p align="center">
  <a href="https://github.com/GMS-EC/ducksound-android">📱 Cliente Android</a> •
  <a href="ARCHITECTURE.md">📖 Documentación de Arquitectura</a> •
  <a href="CHANGELOG.md">📋 Changelog</a> •
  <a href="https://app.takenos.com/pay/b6515307-a660-446d-8117-3214a4a89a80">💖 Donar (Takenos)</a>
</p>

---

## ✨ Funcionalidades

### 🎵 Reproductor de música & Frontend React 18 SPA
- **Single Page Application (SPA)** reactiva construida en React 18, TypeScript y Vite con diseño Glassmorphism y fluidez total.
- **Reproducción Continua (True Gapless)** y streaming HTTP con soporte `206 Partial Content` (byte ranges).
- **Vista de Pantalla Completa (`NowPlayingModal`)** con carátula cuadrada protegida, letras sincronizadas estilo Karaoke y buscador interactivo.
- **Cola de reproducción dinámica** con hasta 20 canciones en vista previa, shuffle y repeat.
- **Editor de Etiquetas en Caliente (`EditTagsModal`)** para editar metadatos en disco y base de datos directamente desde la web.
- **Atajos de teclado**: Espacio (play), ←/→ (10s), Ctrl+←/→ (anterior/siguiente), ↑/↓ (volumen), M (mute), S (shuffle), R (repeat).
- **Color adaptativo** dinámico según portada del álbum extraído con Pillow.
- Soporte para **MP3, FLAC, WAV, M4A y OGG**.
- **Panel de Calidad de Audio** — botón ⓘ en el reproductor muestra specs técnicas en tiempo real: Sample Rate, Bit Depth, Channels, Nyquist, Dynamic Range, Peak, RMS, Total Samples, Bit Rate y Tempo (BPM).

### 🎧 Calidad de audio seleccionable
- **Hi-Res Lossless** — stream directo del archivo original (FLAC, WAV) sin ninguna pérdida de calidad
- **Normal / Comprimida** — transcodificación bajo demanda a MP3/OGG vía ffmpeg para menor consumo de ancho de banda
- La preferencia se configura en el **Perfil de usuario** y se aplica globalmente a todas las reproducciones
- La transcodificación ocurre en el **worker background** (Redis/RQ) sin bloquear el servidor web

### 🎤 Letras sincronizadas
- Archivos **.lrc** con highlight en tiempo real y scroll automático
- **Descarga automática** desde LRCLIB, con fallbacks a **Lyrics.ovh** y **Genius**
- **Caché en RAM** con TTL de 1 hora — segunda carga instantánea
- **Traducción** al idioma del perfil vía LibreTranslate + Google Translate
- **Pre-carga en background** durante el escaneo para disponibilidad inmediata

### 📚 Biblioteca inteligente
### 🏷️ Editor de Etiquetas en Almacenamiento (In-App Tagger)
- **Modificación directa de tags en archivos físicos** usando Mutagen para formatos ID3v2.3/ID3v2.4 (MP3), Vorbis Comments (FLAC, OGG) y MP4 Atoms (M4A, AAC).
- Sincronización atómica dual: actualiza el archivo en disco y sincroniza inmediatamente los registros de la base de datos.
- Interfaz gráfica accesible mediante el menú contextual con `EditTagsModal`.

### 🧠 Mezclas Inteligentes & Regla de Distanciamiento (Gap Rule)
- **Algoritmo `balance_mix`**: Garantiza una separación mínima de 2 pistas entre canciones del mismo artista, evitando la monotonía en mezclas continuas.
- **Estaciones y Radios Dinámicas**:
  - *Track Radio*: Generada a partir de firmas acústicas (BPM, RMS, Dynamic Range y similitud difusa) fijando la semilla en la primera posición.
  - *Artist Radio*: Mezcla temática del artista con bandas relacionadas de la colección.
  - *Top Mix* & *Recent Mix*: Listas automáticas ponderadas por el historial de escucha o incorporaciones recientes.

### 🖼️ Motor Semántico de Carátulas y Paleta Cromática
- **Puntuación léxica de imágenes**: Priorización inteligente de archivos (`front`, `cover`, `folder`) frente a descartes (`back`, `spine`, `cd`, `booklet`).
- **Validación geométrica con Pillow**: Preferencia por relaciones de aspecto cuadradas ($1:1 \pm 10\%$) y resoluciones $\ge 500\text{px}$.
- **Extracción de paletas reactivas**: Generación en tiempo real del color dominante y de acento para iluminar el fondo y el reproductor de la SPA.

### 🔍 Buscador Global Optimizado con "Top Result"
- Búsqueda fuzzy tolerante a erratas impulsada por **RapidFuzz** con clave de resultado dominante (*Top Result*).
- Eliminación de cuellos de botella mediante un pool inteligente de candidatos clasificados por popularidad y matching relacional.
- Indexación veloz y respuestas sub-milisegundo.

### ⚡ Bus de Eventos SSE y Vigilancia en Tiempo Real
- **Server-Sent Events (`/api/events/stream`)**: Notificaciones automáticas push al navegador sin peticiones continuas de sondeo (polling).
- **Watchdog del Sistema de Archivos**: Detección reactiva de adiciones, modificaciones y borrados en la carpeta de música.

### 📚 Biblioteca inteligente
- **Escaneo recursivo** con detección de formatos (MP3, FLAC, WAV, M4A, OGG).
- **Análisis técnico en paralelo** con ThreadPoolExecutor (hasta 6 hilos concurrentes) usando Mutagen + librosa.
- **Extracción de metadatos** ID3v2 / Vorbis Comments e inferencia por carpetas.
- **Escaneo incremental (rápido)** — detecta automáticamente canciones nuevas *y* registros con datos técnicos incompletos.
- **Normalización y deduplicación 100% con MusicBrainz ID** — UUID único por artista, romanización automática de caracteres asiáticos.
- **Fuzzy matching** (`token_set_ratio ≥ 80%`) como respaldo para nombres con colaboraciones.

### 🌐 Enriquecimiento automático
- **Fotos de artistas** desde Deezer API.
- **Portadas de álbumes** desde Deezer + iTunes + extracción de tags embebidos.
- **Biografías** construidas desde datos de Deezer (discografía, oyentes).
- Fallback inteligente: API → tag embebido → placeholder SVG.

### 📊 Perfil y estadísticas por ventana temporal
- Métricas dinámicas por período (`?period=week|month|day|all`).
- Top canciones y artistas personales, omisiones (skips), horas y minutos acumulados legibles ("X hrs, Y mins").
- Preferencias configurables: calidad de audio, crossfade, idioma, tracking de actividad.

### 🔧 Panel de administración
- Escaneo asíncrono con barra de progreso en tiempo real.
- Tareas de fondo (letras, MusicBrainz, transcodificación) en workers dedicados o integrados.
- Estadísticas globales, gestión de usuarios, changelog integrado.
- Protección por sesión + token Bearer (`ADMIN_SECRET_TOKEN`).

---

## 🚀 Inicio rápido

```bash
git clone https://github.com/GMS-EC/ducksound.git
cd ducksound
cp .env.example .env
# Edita MUSIC_PATH y ADMIN_SECRET_TOKEN en .env
docker compose up --build -d
```

Abrir **http://localhost:8604** — usuario: `ducksound`, contraseña: `ducksound`

Ve a **Panel de Administración → Escaneo completo** para indexar tu música.

---

## 📚 Recursos y Documentación

| Recurso | Descripción | Enlace |
|---|---|---|
| 📱 Cliente Android | Aplicación nativa oficial en Kotlin con soporte offline | [ducksound-android](https://github.com/GMS-EC/ducksound-android) |
| 🏗️ Arquitectura | Stack, endpoints, servicios Docker y modelo de datos | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 📋 Historial | Historial de versiones y cambios del servidor | [CHANGELOG.md](CHANGELOG.md) |
| 📄 Licencia | Licencia de software libre AGPLv3 | [LICENSE](LICENSE) |

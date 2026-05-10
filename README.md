# 🦆 DuckSound v1.2.0

**DuckSound** es un servidor de streaming de música personal, self-hosted, con interfaz web estilo Spotify, reproductor persistente, letras automatizadas desde múltiples fuentes, deduplicación con MusicBrainz y recomendaciones inteligentes.

![Flask](https://img.shields.io/badge/Flask-3.0-blue)
![Python](https://img.shields.io/badge/Python-3.10+-yellow)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Redis](https://img.shields.io/badge/Redis-7-red)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-AGPL_v3-blue)

📖 **[Ver documentación completa de arquitectura →](ARCHITECTURE.md)** ·
📋 **[Ver changelog →](CHANGELOG.md)**

---

## ✨ Funcionalidades

### 🎵 Reproductor de música
- **Reproductor persistente** con arquitectura iframe/postMessage — la música no se detiene al navegar
- Controles: play/pausa, siguiente, anterior, avance/retroceso 10s, barra de progreso clickeable
- **Cola de reproducción dinámica** con hasta 20 canciones en vista previa
- **Shuffle, Repeat** (ninguno / una / todas) y **Crossfade** configurable
- **Atajos de teclado**: Espacio (play), ←/→ (10s), Ctrl+←/→ (anterior/siguiente), ↑/↓ (volumen), M (mute), S (shuffle), R (repeat)
- **Color adaptativo** dinámico según portada del álbum
- Soporte para **MP3, FLAC, WAV, M4A y OGG** sin pérdida de calidad

### 🎤 Letras sincronizadas
- Archivos **.lrc** con highlight en tiempo real y scroll automático
- **Descarga automática** desde LRCLIB, con fallbacks a **Lyrics.ovh** y **Genius**
- **Caché en RAM** con TTL de 1 hora — segunda carga instantánea
- **Traducción** al idioma del perfil vía LibreTranslate + Google Translate
- **Pre-carga en background** durante el escaneo para disponibilidad inmediata

### 📚 Biblioteca inteligente
- **Escaneo recursivo** con detección de formatos (MP3, FLAC, WAV, M4A, OGG)
- **Extracción de metadatos** ID3v2 / Vorbis Comments
- **Inferencia por carpetas** cuando no hay metadatos
- **Normalización** de nombres de artistas y detección de versiones de álbumes
- **Deduplicación 100% con MusicBrainz ID** — UUID único por artista, romanización automática de japonés/chino/coreano
- **Fuzzy matching** (`token_set_ratio ≥ 80%`) como respaldo para nombres con colaboraciones

### 🌐 Enriquecimiento automático
- **Fotos de artistas** desde Deezer API
- **Portadas de álbumes** desde Deezer + iTunes + extracción de tags embebidos
- **Biografías** construidas desde datos de Deezer (discografía, oyentes)
- Fallback inteligente: API → tag embebido → placeholder SVG

### 🎯 Recomendaciones y Daily Mixes
- **Motor híbrido** con 5 factores: Género (35%), Artista (25%), Acústico (20%), Álbum (10%), Duración (10%)
- **Similitud acústica** por dynamic range, RMS y BPM
- **Daily Mixes** (Morning Vibes, Afternoon Chill, Night Beats) basados en historial real + similitud
- **Diversidad forzada** — máximo 2 canciones del mismo álbum, 3 del mismo artista

### 📊 Perfil y estadísticas
- Top canciones y artistas personales, total de reproducciones, horas escuchadas, últimas 24h
- Preferencias configurables: crossfade, idioma, tracking de actividad
- **Estadísticas globales** en panel admin

### 🔧 Panel de administración
- Escaneo asíncrono con barra de progreso en tiempo real (persistente en Redis)
- **Workers RQ dedicados** — tareas background (letras, MusicBrainz) en procesos separados
- Estadísticas globales, gestión de usuarios, changelog integrado
- Protección por sesión + token Bearer (`ADMIN_SECRET_TOKEN`)

---

## 🚀 Inicio rápido

```bash
git clone https://github.com/GamersEC/ducksound.git
cd ducksound
cp .env.example .env
# Edita MUSIC_PATH y ADMIN_SECRET_TOKEN en .env
docker compose up --build -d
```

Abrir **http://localhost:8604** — usuario: `ducksound`, contraseña: `ducksound`

Ve a **Panel de Administración → Escaneo completo** para indexar tu música.

---

## 📚 Documentación

| Recurso | Enlace |
|---|---|
| 🏗️ Arquitectura, stack, endpoints, servicios Docker | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 📋 Historial de versiones y cambios | [CHANGELOG.md](CHANGELOG.md) |
| 📄 Licencia | [LICENSE](LICENSE)

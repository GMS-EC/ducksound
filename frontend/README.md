# 🎨 DuckSound Frontend (SPA)

Single Page Application (SPA) moderna, reactiva y de alto rendimiento para el servidor de música **DuckSound**.

Construida con **React 18**, **TypeScript**, **Vite** y una estética **Glassmorphism** en modo oscuro profundo con soporte PWA y sincronización en tiempo real.

---

## ⚡ Tecnologías

- **Core**: React 18 (Root API, Concurrent Mode)
- **Lenguaje**: TypeScript con tipado estricto
- **Bundler / Dev Server**: Vite con HMR ultra-rápido
- **Enrutamiento**: React Router v6
- **Iconografía**: Lucide React
- **Estilos**: Vanilla CSS con variables CSS personalizadas, Glassmorphism, desenfoque de fondo (`backdrop-filter: blur`), gradientes dinámicos y microanimaciones
- **Eventos en Vivo**: Server-Sent Events (SSE) hacia el backend Flask

---

## 🏗️ Arquitectura de la Aplicación

### Contextos Globales (`src/contexts/`)
- **`PlayerContext`**: Motor central de reproducción de audio. Gestiona reproducción continua (True Gapless), colas dinámicas, historial, volumen logarítmico persistente, shuffle aleatorio sin reemplazo, modos de repetición y detección de silencios.
- **`AuthContext`**: Ciclo de vida de autenticación, sesión de usuario, token Bearer y persistencia segura.
- **`ContextMenuContext`**: Menú contextual flotante extensible accesible en cualquier parte de la aplicación (añadir a cola, reproducir siguiente, iniciar radio, añadir a colección, editar metadatos).

### Componentes y Modales (`src/components/`)
- **`NowPlayingModal`**: Vista inmersiva a pantalla completa con letras karaoke sincronizadas, carátula cuadrada con relación de aspecto 1:1 protegida contra recortes, barra de progreso interactiva y gradiente ambiental reactivo.
- **`EditTagsModal`**: Editor en vivo de metadatos de audio (título, artista, álbum, año, género, pista, disco) con sincronización atómica dual.
- **`AudioInfoModal`**: Modal de inspección acústica en tiempo real (Sample Rate, Bit Depth, Canales, BPM, RMS, Rango Dinámico, Nyquist, Bitrate).
- **`PlayerBar`**: Barra de control inferior persistente con scrubber de alta precisión y controles rápidos.
- **`RightPanel`**: Panel lateral derecho con pestañas conmutables para la pista actual, letras sincronizadas con traducción automática y cola de reproducción interactiva.
- **`Sidebar`**: Barra de navegación lateral con acceso a Dashboard, Biblioteca, Exploración, Artistas, Álbumes y Administración.
- **`SearchDialog`**: Buscador interactivo global con coincidencias difusas y tarjeta destacada de mejor resultado (*Top Result*).

### Páginas (`src/pages/`)
- **`DashboardPage`**: Pantalla principal con mezclas inteligentes (*Daily Mixes*, novedades, descubrimientos).
- **`LibraryPage`**: Biblioteca personal unificada con pestañas para Canciones Favoritas, Álbumes Guardados y Playlists/Colecciones.
- **`AlbumDetailPage`**: Detalle del álbum con paleta cromática adaptativa, soporte multi-disco y ordenamiento numérico natural.
- **`ArtistDetailPage`**: Perfil de artista con discografía completa, canciones más populares y artistas similares.
- **`FoldersPage`**: Explorador directo de directorios físicos de la colección musical.
- **`ExplorePage`**: Exploración por géneros y recomendaciones basadas en firmas acústicas.
- **`ProfilePage`**: Métricas de escucha por período (semana, mes, histórico), calidad de audio seleccionable y gestión de sesiones activas.
- **`AdminPage`**: Panel de administración integral con progreso de escaneo en vivo, gestión de biblioteca y usuarios.

---

## 🛠️ Desarrollo Local

```bash
# Instalar dependencias
npm install

# Iniciar servidor de desarrollo con Hot Module Replacement
npm run dev

# Compilar para producción (genera bundle optimizado en dist/)
npm run build

# Previsualizar el build de producción
npm run preview
```

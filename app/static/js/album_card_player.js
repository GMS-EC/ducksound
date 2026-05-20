// Reproductor Integrado de Tarjetas de Álbumes e Híbridos (Daily Mix)
// Este script permite la reproducción instantánea de colecciones musicales directamente
// desde la interfaz gráfica sin interrumpir la experiencia de navegación del usuario.

/**
 * Solicita las canciones de un álbum al servidor y las inyecta en la cola del reproductor en el iframe.
 * @param {number|string} albumId - El ID identificador único del álbum a reproducir.
 */
function playAlbum(albumId) {
    fetch(`/api/album/${albumId}/canciones`)
        .then(r => r.json())
        .then(songs => {
            if (songs && songs.length > 0) {
                // Mapear los datos recibidos a un formato uniforme compatible con el reproductor
                songs = songs.map(s => ({
                    id: s.id,
                    titulo: s.titulo,
                    artista: s.artista,
                    audio: s.audio,
                    cover: s.cover,
                    lyrics: s.lyrics
                }));
                const iframe = document.getElementById('player-frame');
                if (iframe && iframe.contentWindow) {
                    // Enviar la nueva lista de reproducción (playlist) completa al reproductor
                    iframe.contentWindow.postMessage({
                        type: 'setPlaylist', 
                        playlist: songs
                    }, window.location.origin);
                    
                    // Iniciar la reproducción automática del primer tema del álbum tras una breve pausa
                    const first = songs[0];
                    if (first) {
                        setTimeout(() => {
                            iframe.contentWindow.postMessage({
                                type: 'playSong',
                                song: first
                            }, window.location.origin);
                        }, 100);
                    }
                }
            }
        })
        .catch(err => console.error('Error al reproducir el álbum:', err));
}

/**
 * Solicita las canciones de un Daily Mix y las carga en la lista de reproducción activa del iframe.
 * @param {number|string} mixId - El ID identificador del Daily Mix generado para el usuario.
 */
function playDailyMix(mixId) {
    fetch(`/api/daily-mix/${mixId}/songs`)
        .then(r => r.json())
        .then(songs => {
            if (songs && songs.length > 0) {
                // Mapear los campos del mix para cumplir con la firma del objeto Cancion en el reproductor
                songs = songs.map(s => ({
                    id: s.id,
                    titulo: s.titulo,
                    artista: s.artista,
                    audio: s.audio,
                    cover: s.cover,
                    lyrics: s.lyrics
                }));
                const iframe = document.getElementById('player-frame');
                if (iframe && iframe.contentWindow) {
                    // Enviar la playlist del mix diario al iframe
                    iframe.contentWindow.postMessage({
                        type: 'setPlaylist', 
                        playlist: songs
                    }, window.location.origin);
                    
                    // Reproducir el primer track del mix diario
                    const first = songs[0];
                    if (first) {
                        setTimeout(() => {
                            iframe.contentWindow.postMessage({
                                type: 'playSong',
                                song: first
                            }, window.location.origin);
                        }, 100);
                    }
                }
            }
        })
        .catch(err => console.error('Error al reproducir el daily mix:', err));
}

/**
 * Delegación de eventos a nivel global para interceptar los clics en los botones de "Play" de las tarjetas.
 * Evita la sobrecarga de listeners individuales en el DOM.
 * @param {Event} e - Objeto de evento de clic nativo del DOM.
 */
function handleCardPlayClick(e) {
    const btn = e.target.closest('.album-card-play');
    if (!btn) return;
    e.preventDefault();
    e.stopImmediatePropagation(); // Evita burbujeo no deseado o recarga de la SPA
    
    const albumId = btn.dataset.albumId;
    const mixId = btn.dataset.mixId;
    
    if (albumId) {
        playAlbum(albumId);
    } else if (mixId) {
        playDailyMix(mixId);
    }
}

/**
 * Configura y vincula la delegación de eventos al documento.
 * Remueve listeners duplicados previos antes de añadir uno nuevo.
 */
function setupAlbumCardPlayButtons() {
    document.removeEventListener('click', handleCardPlayClick);
    document.addEventListener('click', handleCardPlayClick);
}

// Inicializar el escuchador de eventos en la carga del script
setupAlbumCardPlayButtons();

// Re-vincular manejadores al cambiar de vista en la SPA (Single Page Application)
if (typeof window.initPageBindings === 'function') {
    const originalInitPageBindings = window.initPageBindings;
    window.initPageBindings = function() {
        originalInitPageBindings();
        setupAlbumCardPlayButtons();
    };
} else {
    window.initPageBindings = setupAlbumCardPlayButtons;
}

// Registrar en el ámbito global del navegador para su libre invocación
window.playAlbum = playAlbum;
window.playDailyMix = playDailyMix;
window.setupAlbumCardPlayButtons = setupAlbumCardPlayButtons;

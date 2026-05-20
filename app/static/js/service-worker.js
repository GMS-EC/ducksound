// Nombre del caché para versionar los recursos almacenados
const CACHE_NAME = 'ducksound-cache-v2';

// Evento de instalación: fuerza al service worker entrante a activarse inmediatamente
self.addEventListener('install', event => {
    self.skipWaiting();
});

// Evento de activación: limpia cachés antiguos para liberar espacio y evitar conflictos de versión
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

// Interceptor de peticiones HTTP (Fetch)
self.addEventListener('fetch', event => {
    const request = event.request;

    // Solo interceptar peticiones GET (recursos estáticos y páginas)
    if (request.method !== 'GET') return;

    const url = new URL(request.url);

    // Evitar interceptar flujos de audio, llamadas a la API o endpoints de administración y escaneo
    if (url.pathname.startsWith('/audio/') || 
        url.pathname.startsWith('/api/') || 
        url.pathname.startsWith('/scan/') || 
        url.pathname.startsWith('/admin/')) {
        return;
    }

    // 1. Peticiones de Navegación (HTML de páginas): estrategia Network-First
    // Intenta cargar del servidor para asegurar la versión más reciente; si falla (offline), usa el caché.
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request).catch(() => caches.match(request))
        );
        return;
    }

    // 2. Estilos y Scripts (CSS/JS): estrategia Network-First con persistencia en caché
    // Busca en la red, actualiza el caché con el nuevo clon del archivo y tiene fallback al caché si está desconectado.
    if (url.pathname.match(/\.(css|js)$/)) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
                    return response;
                })
                .catch(() => caches.match(request))
        );
        return;
    }

    // 3. Demás recursos (Imágenes, Fuentes, etc.): estrategia Cache-First con actualización asíncrona
    // Devuelve inmediatamente la versión del caché si existe para velocidad instantánea,
    // y al mismo tiempo dispara una petición de red en segundo plano para actualizar el caché silenciosamente.
    event.respondWith(
        caches.match(request).then(cached => {
            const fetchPromise = fetch(request)
                .then(response => {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
                    return response;
                })
                .catch(() => null);
            return cached || fetchPromise;
        })
    );
});

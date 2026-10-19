# -*- coding: utf-8 -*-
"""
Servicio de Vigilancia de Archivos en Tiempo Real (Watchdog) - DuckSound
Monitorea la carpeta de música y detecta archivos añadidos, modificados o eliminados
para mantener la biblioteca actualizada automáticamente sin intervención manual.
"""

import os
import time
import threading
from pathlib import Path
from config import Config

_watcher_thread = None
_watcher_running = False

class AudioFileHandler:
    """Manejador de eventos para archivos de audio."""
    def __init__(self, app):
        self.app = app
        self._pending_events = False
        self._last_event_time = 0
        self._lock = threading.Lock()
        
    def _is_audio(self, path):
        ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
        return ext in Config.ALLOWED_AUDIO_EXTENSIONS

    def dispatch(self, event):
        if getattr(event, 'is_directory', False):
            return
        src_path = getattr(event, 'src_path', '')
        if not src_path or not self._is_audio(src_path):
            return

        with self._lock:
            self._pending_events = True
            # Debounce de 3 segundos para que los archivos terminen de copiarse/moverse
            self._last_event_time = time.time()

    def process_pending(self):
        should_scan = False
        with self._lock:
            if self._pending_events and (time.time() - self._last_event_time >= 3.0):
                self._pending_events = False
                should_scan = True

        if should_scan:
            self._run_incremental_scan()

    def _run_incremental_scan(self):
        try:
            with self.app.app_context():
                from app.services.scanner import escanear_carpeta_audio
                print("👀 [DuckSound Watchdog] Cambio detectado en biblioteca. Ejecutando actualización incremental...")
                escanear_carpeta_audio(Config.AUDIO_FOLDER, es_rapido=True)
                print("✅ [DuckSound Watchdog] Biblioteca actualizada automáticamente con éxito.")
                try:
                    from app.services.events import event_bus
                    event_bus.dispatch('library_updated', {'source': 'watchdog', 'timestamp': time.time()})
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ [DuckSound Watchdog] Error en actualización incremental: {e}")


def iniciar_vigilancia(app):
    """Inicia el observador de watchdog en un hilo daemon en segundo plano."""
    global _watcher_thread, _watcher_running
    if _watcher_running:
        return

    try:
        from watchdog.observers.polling import PollingObserver
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("ℹ️ [DuckSound Watchdog] Módulo watchdog no disponible. Detección automática desactivada.")
        return

    music_folder = Path(Config.AUDIO_FOLDER)
    if not music_folder.exists():
        print(f"ℹ️ [DuckSound Watchdog] Carpeta {music_folder} no encontrada. Watchdog no iniciado.")
        return

    handler_impl = AudioFileHandler(app)

    class WatchdogBridge(FileSystemEventHandler):
        def on_any_event(self, event):
            handler_impl.dispatch(event)

    observer = PollingObserver(timeout=2.0)
    try:
        observer.schedule(WatchdogBridge(), str(music_folder.resolve()), recursive=True)
    except Exception as e:
        print(f"⚠️ [DuckSound Watchdog] No se pudo programar observer en {music_folder}: {e}")
        return

    def _loop():
        global _watcher_running
        _watcher_running = True
        try:
            observer.start()
            print(f"👀 [DuckSound Watchdog] Vigilancia en tiempo real activa en: {music_folder.resolve()}")
            while _watcher_running:
                handler_impl.process_pending()
                time.sleep(1.0)
        except Exception as e:
            print(f"⚠️ [DuckSound Watchdog] Error en bucle de vigilancia: {e}")
        finally:
            try:
                observer.stop()
                observer.join()
            except Exception:
                pass

    _watcher_thread = threading.Thread(target=_loop, daemon=True, name="DuckSound-Watchdog")
    _watcher_thread.start()

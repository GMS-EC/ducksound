# -*- coding: utf-8 -*-
"""
Bus de Eventos Server-Sent Events (SSE) - DuckSound
===================================================
Permite la transmisión unidireccional en tiempo real desde el servidor
hacia el cliente web (progreso de escáner, letras, actualización de metadatos, etc.)
eliminando la necesidad de polling repetitivo.
"""

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Generator, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Event:
    id: str
    type: str
    data: Any
    timestamp: float


class EventBus:
    """Bus central en memoria para Server-Sent Events (SSE)."""

    def __init__(self):
        self._listeners: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._counter = 0

    def dispatch(self, event_type: str, data: Any = None) -> None:
        """
        Envía un evento a todos los clientes web conectados.
        """
        now = time.time()
        with self._lock:
            self._counter += 1
            event = Event(
                id=str(self._counter),
                type=event_type,
                data=data or {},
                timestamp=now
            )
            dead_listeners = []
            for listener_id, q in self._listeners.items():
                try:
                    q.put_nowait(event)
                except queue.Full:
                    dead_listeners.append(listener_id)

            for d in dead_listeners:
                self._listeners.pop(d, None)

    def listen(self, timeout: float = 15.0) -> Generator[Tuple[str, dict], None, None]:
        """
        Generador que produce tuplas (id, payload) para el stream SSE.
        Si transcurren `timeout` segundos sin eventos, envía un pulso heartbeat.
        """
        q = queue.Queue(maxsize=150)
        listener_id = f"{time.time()}_{id(q)}"
        with self._lock:
            self._listeners[listener_id] = q

        try:
            while True:
                try:
                    event = q.get(timeout=timeout)
                    yield event.id, {
                        'event': event.type,
                        'data': event.data,
                        'timestamp': event.timestamp
                    }
                except queue.Empty:
                    # Pulso para mantener viva la conexión HTTP
                    yield "heartbeat", {
                        'event': 'heartbeat',
                        'data': {},
                        'timestamp': time.time()
                    }
        finally:
            with self._lock:
                self._listeners.pop(listener_id, None)

    def listener_count(self) -> int:
        """Retorna la cantidad de navegadores/clientes conectados actualmente al stream."""
        with self._lock:
            return len(self._listeners)


# Instancia singleton del bus de eventos para toda la aplicación
event_bus = EventBus()

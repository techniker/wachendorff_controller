"""
WebSocket manager for pushing live data to connected clients.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import WebSocket

from ..modbus.poller import LiveData

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts live data."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._last_data: Optional[LiveData] = None

    @property
    def client_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.info(f"WebSocket client connected ({self.client_count} total)")
        # Send current data immediately
        if self._last_data is not None:
            try:
                await ws.send_text(json.dumps(self._last_data.to_dict()))
            except Exception:
                pass

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
        logger.info(f"WebSocket client disconnected ({self.client_count} total)")

    def on_live_data(self, data: LiveData):
        """Callback for poller — schedules broadcast to all clients."""
        self._last_data = data
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast(data))
        except RuntimeError:
            pass

    async def _broadcast(self, data: LiveData):
        """Send data to all connected clients."""
        if not self._connections:
            return

        message = json.dumps(data.to_dict())
        disconnected = []

        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

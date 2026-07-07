import asyncio
import json
import logging
from typing import List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Quan ly danh sach cac WebSocket client dang ket noi.
    Cung cap ham broadcast de day du lieu JSON den tat ca client cuung mot luc.
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"[WS] Client connected. Total active: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            f"[WS] Client disconnected. Total active: {len(self.active_connections)}"
        )

    async def broadcast(self, data: dict) -> None:
        """
        Day du lieu JSON den tat ca client dang ket noi.
        Tu dong loai bo client bi ngat ket noi khoi danh sach.
        """
        if not self.active_connections:
            return

        payload = json.dumps(data, ensure_ascii=False)
        disconnected: List[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"[WS] Failed to send to client, will remove: {e}")
                disconnected.append(connection)

        for dead_conn in disconnected:
            self.disconnect(dead_conn)


# Singleton instance dung chung toan bo ung dung
manager = ConnectionManager()

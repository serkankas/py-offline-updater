from fastapi import WebSocket
from app.websockets.base import BaseWebsocketConsumer
from core.utils.dim import dimming_controller
from typing import Dict, Any

class DimmingConsumer(BaseWebsocketConsumer):
    def __init__(self, websocket: WebSocket):
        super().__init__(websocket)
        self.controller = dimming_controller

    async def connect(self):
        await super().connect()
        await self.send_current_status()

    async def receive(self, data: Dict[str, Any]):
        """
        Desteklenen mesaj formatları:
        - {"cmd": "up"} veya {"cmd": "down"} - seviye artır/azalt
        - {"level": 5} - direkt seviye ayarla (0-9 arası)
        - {"mode": "day"} - mod değiştir (day, dusk, night)
        - Kombinasyon: {"value": 7, "mode": "night"}
        """
        cmd = data.get("cmd")
        level = data.get("level")
        mode = data.get("mode")

        # cmd ile up/down kontrolü
        if cmd == "up":
            self.controller.level_up()
        elif cmd == "down":
            self.controller.level_down()

        if level is not None:
            try:
                self.controller.set_level(int(level))
            except (ValueError, TypeError):
                pass

        # mode ile mod değişikliği
        if mode is not None:
            self.controller.set_mode(mode)

    async def send_current_status(self):
        await self.websocket.send_json(self.controller.get_status())


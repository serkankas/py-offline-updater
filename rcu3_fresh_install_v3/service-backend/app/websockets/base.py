from fastapi import WebSocket

from typing import Dict, Any

class BaseWebsocketConsumer():
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.is_connected = False

    async def connect(self):
        """Override this method for custom connection logic"""
        await self.websocket.accept()
        self.is_connected = True

    async def disconnect(self, code: int = 1000):
        """Override this method for custom disconnect logic"""
        self.is_connected = False
        await self.websocket.close(code)

    async def receive(self, data: Dict[str, Any]):
        """Override this method to handle incoming messages"""
        pass

    async def receive_loop(self):
        """Main receive loop"""
        try:
            while self.is_connected:
                data = await self.websocket.receive_json()
                await self.receive(data)
        except Exception as e:
            print(f"Error in receive loop: {e}")
        finally:
            await self.disconnect()

    async def run(self):
        """Main entry point"""
        await self.connect()
        await self.receive_loop()


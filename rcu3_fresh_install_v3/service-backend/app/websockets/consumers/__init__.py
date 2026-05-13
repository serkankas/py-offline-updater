from fastapi import WebSocket
from app.websockets.consumers.dimming import DimmingConsumer
from app.websockets.managers import websocket_manager

async def dimming_websocket(websocket: WebSocket):
    consumer = DimmingConsumer(websocket)
    websocket_manager.add_connection("dimming", consumer)
    
    try:
        await consumer.run()
    except Exception as e:
        print(f"Dimming WebSocket error: {e}")
    finally:
        websocket_manager.remove_connection("dimming", consumer)

__all__ = ["dimming_websocket"]


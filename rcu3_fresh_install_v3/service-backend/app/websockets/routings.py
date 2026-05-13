from app.websockets.consumers import dimming_websocket

routes = [
    {"path": "/dimming", "endpoint": dimming_websocket}
]


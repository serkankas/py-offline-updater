"""
FastAPI application instance
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.settings import settings
from core.startup import initialize_system, shutdown_system, print_registered_routes
from app.api import api_router
from app.websockets.routings import routes as websocket_routes

app = FastAPI(
    title="VDR Service",
    description="VDR TCP Listener and System Controller",
    version="1.0.0",
    debug=settings.DEBUG
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router
app.include_router(api_router)

# WebSocket routes
for route in websocket_routes:
    app.add_websocket_route(route["path"], route["endpoint"])


@app.on_event("startup")
async def startup_event():
    await initialize_system()
    print_registered_routes(app)


@app.on_event("shutdown")
async def shutdown_event():
    await shutdown_system()
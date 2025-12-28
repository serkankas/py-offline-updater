"""FastAPI update service main application."""
import sys
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .config import config
from .api.endpoints import router
from update_engine.utils import setup_logging


# Setup logging
setup_logging(config.LOG_DIR / 'update_service.log')
logger = logging.getLogger('update_service')

# Ensure directories exist
config.ensure_directories()

# Create FastAPI app
app = FastAPI(
    title="py-offline-updater Service",
    description="Web service for managing offline updates",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)

# Frontend static files
frontend_dir = Path(__file__).parent / "frontend"

if frontend_dir.exists():
    # Mount static files
    static_dir = frontend_dir / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Serve index.html at root
    @app.get("/")
    async def read_root():
        """Serve frontend index.html."""
        index_file = frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "py-offline-updater Service", "version": "1.0.0"}


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Update service starting...")
    logger.info(f"Base directory: {config.BASE_DIR}")
    logger.info(f"Upload directory: {config.UPLOAD_DIR}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("Update service shutting down...")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info"
    )


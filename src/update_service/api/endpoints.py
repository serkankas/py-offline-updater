"""API endpoints for update service."""
import os
import sys
import uuid
import shutil
import asyncio
import logging
import psutil
import socket
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from update_engine.engine import UpdateEngine
from update_engine.state import StateManager
from ..config import config
from .models import (
    SystemInfo, ServiceStatus, UpdateJobInfo,
    UpdateProgress, UploadResponse, UpdateResponse, RollbackResponse,
    JobStatus, ChunkedUploadInitResponse, ChunkedUploadChunkResponse,
    ChunkedUploadFinalizeResponse
)
import math


router = APIRouter(prefix="/api")
logger = logging.getLogger('update_service')

# In-memory job storage (in production, use a database)
jobs: Dict[str, UpdateJobInfo] = {}
job_logs: Dict[str, List[str]] = {}

# In-memory chunked upload tracking
chunked_uploads: Dict[str, dict] = {}


@router.get("/system-info", response_model=SystemInfo)
async def get_system_info():
    """Get system information."""
    disk = psutil.disk_usage(str(config.BASE_DIR))
    memory = psutil.virtual_memory()
    
    return SystemInfo(
        hostname=socket.gethostname(),
        disk_usage={
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        },
        memory={
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent
        },
        uptime=psutil.boot_time()
    )



@router.post("/upload-update", response_model=UploadResponse)
async def upload_update(file: UploadFile = File(...)):
    """Upload an update package."""
    # Validate file extension
    if not any(file.filename.endswith(ext) for ext in config.ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {config.ALLOWED_EXTENSIONS}"
        )
    
    # Save uploaded file
    upload_path = config.UPLOAD_DIR / file.filename
    
    try:
        with open(upload_path, "wb") as buffer:
            content = await file.read()
            
            # Check file size
            if len(content) > config.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Max size: {config.MAX_UPLOAD_SIZE} bytes"
                )
            
            buffer.write(content)
        
        logger.info(f"Uploaded: {file.filename} ({len(content)} bytes)")
        
        return UploadResponse(
            filename=file.filename,
            size=len(content),
            message="File uploaded successfully"
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/init", response_model=ChunkedUploadInitResponse)
async def chunked_upload_init(filename: str, total_size: int):
    """Initialize a chunked upload session."""
    if not any(filename.endswith(ext) for ext in config.ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {config.ALLOWED_EXTENSIONS}"
        )

    if total_size > config.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {config.MAX_UPLOAD_SIZE} bytes"
        )

    upload_id = str(uuid.uuid4())
    total_chunks = math.ceil(total_size / config.CHUNK_SIZE)
    upload_path = config.UPLOAD_DIR / filename

    chunked_uploads[upload_id] = {
        "filename": filename,
        "total_size": total_size,
        "total_chunks": total_chunks,
        "received_chunks": 0,
        "received_bytes": 0,
        "upload_path": upload_path,
    }

    # Create empty file (truncate if exists)
    with open(upload_path, "wb") as f:
        pass

    logger.info(f"Chunked upload init: {filename} ({total_size} bytes, {total_chunks} chunks)")

    return ChunkedUploadInitResponse(
        upload_id=upload_id,
        filename=filename,
        total_size=total_size,
        chunk_size=config.CHUNK_SIZE,
        total_chunks=total_chunks,
        message="Upload session initialized"
    )


@router.post("/upload/chunk", response_model=ChunkedUploadChunkResponse)
async def chunked_upload_chunk(
    upload_id: str,
    chunk_index: int,
    file: UploadFile = File(...)
):
    """Receive a single chunk and append to file."""
    if upload_id not in chunked_uploads:
        raise HTTPException(status_code=404, detail="Upload session not found")

    session = chunked_uploads[upload_id]

    if chunk_index != session["received_chunks"]:
        raise HTTPException(
            status_code=400,
            detail=f"Expected chunk {session['received_chunks']}, got {chunk_index}"
        )

    try:
        chunk_data = await file.read()
        chunk_len = len(chunk_data)

        with open(session["upload_path"], "ab") as f:
            f.write(chunk_data)

        session["received_chunks"] += 1
        session["received_bytes"] += chunk_len

        percent = round(session["received_bytes"] / session["total_size"] * 100, 1)

        return ChunkedUploadChunkResponse(
            upload_id=upload_id,
            chunk_index=chunk_index,
            received_bytes=session["received_bytes"],
            total_bytes=session["total_size"],
            percent=percent,
            message=f"Chunk {chunk_index + 1}/{session['total_chunks']} received"
        )

    except Exception as e:
        logger.error(f"Chunk upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Chunk upload failed: {str(e)}")


@router.post("/upload/finalize", response_model=ChunkedUploadFinalizeResponse)
async def chunked_upload_finalize(upload_id: str):
    """Finalize chunked upload - verify completeness."""
    if upload_id not in chunked_uploads:
        raise HTTPException(status_code=404, detail="Upload session not found")

    session = chunked_uploads[upload_id]

    if session["received_chunks"] != session["total_chunks"]:
        raise HTTPException(
            status_code=400,
            detail=f"Missing chunks: received {session['received_chunks']}/{session['total_chunks']}"
        )

    # Verify file size on disk
    actual_size = session["upload_path"].stat().st_size
    if actual_size != session["total_size"]:
        # Cleanup bad file
        session["upload_path"].unlink(missing_ok=True)
        del chunked_uploads[upload_id]
        raise HTTPException(
            status_code=400,
            detail=f"Size mismatch: expected {session['total_size']}, got {actual_size}"
        )

    filename = session["filename"]
    total_size = session["total_size"]

    # Cleanup session
    del chunked_uploads[upload_id]

    logger.info(f"Chunked upload complete: {filename} ({total_size} bytes)")

    return ChunkedUploadFinalizeResponse(
        upload_id=upload_id,
        filename=filename,
        total_size=total_size,
        message="Upload completed successfully"
    )


@router.get("/active-job")
async def get_active_job():
    """Return the currently running or most recent job so frontend can reconnect after page refresh."""
    # Check for running job first
    for job in jobs.values():
        if job.status == JobStatus.RUNNING:
            return {"has_active_job": True, "job_id": job.job_id, "source": "running"}

    # Check for recently completed/failed job (still in memory)
    latest = None
    for job in jobs.values():
        if latest is None or (job.created_at and job.created_at > latest.created_at):
            latest = job
    if latest:
        return {"has_active_job": True, "job_id": latest.job_id, "source": "recent"}

    # No in-memory jobs — check state.json for interrupted update (after restart)
    state_manager = StateManager(config.STATE_FILE)
    state = state_manager.load()

    if state and state.get("status") in ("in_progress", "failed"):
        return {
            "has_active_job": True,
            "job_id": None,
            "source": "state_file",
            "status": state.get("status"),
            "description": state.get("description"),
            "current_action_name": state.get("current_action_name"),
            "completed_actions": len(state.get("completed_actions", [])),
            "last_updated": state.get("last_updated"),
        }

    return {"has_active_job": False}


@router.post("/apply-update", response_model=UpdateResponse)
async def apply_update(filename: str, background_tasks: BackgroundTasks):
    """Start update process in background."""
    upload_path = config.UPLOAD_DIR / filename
    
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail="Update package not found")
    
    # Check if another update is running
    if any(job.status == JobStatus.RUNNING for job in jobs.values()):
        raise HTTPException(
            status_code=409,
            detail="Another update is already in progress"
        )
    
    # Create job
    job_id = str(uuid.uuid4())
    job = UpdateJobInfo(
        job_id=job_id,
        status=JobStatus.PENDING,
        package_name=filename,
        created_at=datetime.now()
    )
    
    jobs[job_id] = job
    job_logs[job_id] = []
    
    # Start update in background
    background_tasks.add_task(run_update, job_id, upload_path)
    
    logger.info(f"Update job created: {job_id}")
    
    return UpdateResponse(
        job_id=job_id,
        message="Update started",
        status=JobStatus.PENDING
    )


@router.get("/update-status/{job_id}", response_model=UpdateJobInfo)
async def get_update_status(job_id: str):
    """Get update job status."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs[job_id]


@router.get("/update-stream/{job_id}")
async def update_stream(job_id: str):
    """Stream update progress via Server-Sent Events."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def event_generator():
        """Generate SSE events."""
        last_log_index = 0
        
        while True:
            # Send job status
            job = jobs[job_id]
            yield {
                "event": "status",
                "data": job.model_dump_json()
            }
            
            # Send new logs
            logs = job_logs[job_id]
            if len(logs) > last_log_index:
                new_logs = logs[last_log_index:]
                for log in new_logs:
                    yield {
                        "event": "log",
                        "data": log
                    }
                last_log_index = len(logs)
            
            # Stop if job is complete
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.ROLLED_BACK]:
                yield {
                    "event": "complete",
                    "data": job.model_dump_json()
                }
                break
            
            await asyncio.sleep(1)
    
    return EventSourceResponse(event_generator())


@router.post("/rollback/{job_id}", response_model=RollbackResponse)
async def rollback_update(job_id: str):
    """Rollback an update."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    # Get package path from job or state
    state_manager = StateManager(config.STATE_FILE)
    state = state_manager.load()
    
    if not state or 'package_path' not in state:
        raise HTTPException(status_code=400, detail="No update state found for rollback")
    
    package_path = Path(state['package_path'])
    
    if not package_path.exists():
        raise HTTPException(status_code=400, detail="Update package not found")
    
    try:
        logger.info(f"Starting rollback for job {job_id}")
        
        engine = UpdateEngine(package_path, config.BASE_DIR)
        success = engine.rollback()
        
        if success:
            job.status = JobStatus.ROLLED_BACK
            job.completed_at = datetime.now()
            logger.info(f"Rollback completed for job {job_id}")
            
            return RollbackResponse(
                job_id=job_id,
                message="Rollback completed successfully",
                success=True
            )
        else:
            logger.error(f"Rollback failed for job {job_id}")
            raise HTTPException(status_code=500, detail="Rollback failed")
            
    except Exception as e:
        logger.error(f"Rollback error: {e}")
        raise HTTPException(status_code=500, detail=f"Rollback error: {str(e)}")


def run_update(job_id: str, package_path: Path):
    """Run update process (background task).

    Runs as a sync function so FastAPI executes it in a thread pool,
    keeping the event loop free for SSE streaming.

    Args:
        job_id: Job ID
        package_path: Path to uploaded .tar.gz package
    """
    job = jobs[job_id]
    logs = job_logs[job_id]

    # Setup logging to capture logs
    class LogCapture(logging.Handler):
        def emit(self, record):
            log_entry = self.format(record)
            logs.append(log_entry)

    handler = LogCapture()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    update_logger = logging.getLogger('update_engine')

    extract_dir = None

    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()

        logs.append(f"Starting update: {package_path.name}")

        # Extract package to temp directory
        extract_dir = config.TEMP_DIR / job_id
        extract_dir.mkdir(parents=True, exist_ok=True)

        logs.append(f"Extracting package to {extract_dir}")

        import tarfile
        with tarfile.open(package_path, 'r:gz') as tar:
            tar.extractall(extract_dir)

        logs.append("Package extracted successfully")

        # Create engine with progress callback
        def on_progress(progress):
            job.progress = progress

        engine = UpdateEngine(extract_dir, config.BASE_DIR, progress_callback=on_progress)

        # Add LogCapture AFTER engine init (setup_logging clears handlers)
        update_logger.addHandler(handler)

        # Update job description from manifest
        job.description = engine.manifest.get('description')

        # Set initial progress
        job.progress = engine.get_progress()

        success = engine.run()

        if success:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            logs.append("Update completed successfully")
        else:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            job.error = "Update failed - check logs for details"
            logs.append("Update failed")

        # Final progress
        job.progress = engine.get_progress()
        
    except Exception as e:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now()
        job.error = str(e)
        logs.append(f"Update error: {e}")
        logger.error(f"Update error: {e}", exc_info=True)
    
    finally:
        update_logger.removeHandler(handler)
        
        # Cleanup extracted files
        if extract_dir and extract_dir.exists():
            try:
                shutil.rmtree(extract_dir, ignore_errors=True)
                logs.append(f"Cleaned up temp files: {extract_dir}")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")


"""Pydantic models for API."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Update job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class SystemInfo(BaseModel):
    """System information."""
    hostname: str
    disk_usage: Dict[str, Any]
    memory: Dict[str, Any]
    uptime: float


class ServiceStatus(BaseModel):
    """Service status information."""
    name: str
    active: bool
    status: str


class BackupInfo(BaseModel):
    """Backup information."""
    name: str
    path: str
    created_at: Optional[str]
    sources: List[Dict[str, Any]]


class UpdateJobInfo(BaseModel):
    """Update job information."""
    job_id: str
    status: JobStatus
    description: Optional[str] = None
    package_name: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class UpdateProgress(BaseModel):
    """Update progress information."""
    status: str
    total_actions: int
    completed_actions: int
    current_action: Optional[int] = None
    current_action_name: Optional[str] = None
    description: Optional[str] = None


class UploadResponse(BaseModel):
    """File upload response."""
    filename: str
    size: int
    message: str


class UpdateResponse(BaseModel):
    """Update start response."""
    job_id: str
    message: str
    status: JobStatus


class RollbackResponse(BaseModel):
    """Rollback response."""
    job_id: str
    message: str
    success: bool


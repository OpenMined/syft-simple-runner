"""Pydantic models for syft-simple-runner API."""

from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel


class JobHistoryItem(BaseModel):
    """Single job history item."""
    uid: str
    name: str
    status: str
    requester_email: str
    target_email: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time: Optional[float] = None
    success: bool
    logs: Optional[str] = None
    tags: List[str] = []


class JobHistoryResponse(BaseModel):
    """Response for job history endpoint."""
    jobs: List[JobHistoryItem]
    total: int
    status: str = "success"


class StatusResponse(BaseModel):
    """Application status response."""
    app: str
    version: str
    timestamp: datetime
    syftbox: Dict[str, Any]
    components: Dict[str, str]


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    status: str = "success"


class JobStatsResponse(BaseModel):
    """Job statistics response."""
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    running_jobs: int
    pending_jobs: int
    success_rate: float
    status: str = "success" 
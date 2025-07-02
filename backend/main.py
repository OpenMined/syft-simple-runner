"""
FastAPI backend for syft-simple-runner job history UI
"""

import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path as PathLib

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from loguru import logger
from syft_core import Client

from .models import (
    JobHistoryResponse, JobHistoryItem, StatusResponse,
    MessageResponse, JobStatsResponse
)
from .utils import (
    get_job_history,
    get_job_stats,
    clear_old_job_history
)

try:
    import syft_code_queue as q
    from syft_code_queue import JobStatus
except ImportError:
    logger.error("syft-code-queue not available - job browsing features will be limited")
    q = None
    # Mock JobStatus for when syft-code-queue is not available
    class JobStatus:
        pending = "pending"
        approved = "approved"
        running = "running"
        completed = "completed"
        failed = "failed"
        rejected = "rejected"


def get_client() -> Client:
    """Get SyftBox client."""
    try:
        return Client.load()
    except Exception as e:
        logger.error(f"Failed to load SyftBox client: {e}")
        raise HTTPException(status_code=500, detail="SyftBox client not available")


app = FastAPI(
    title="Syft Simple Runner API",
    description="View execution history and statistics for Syft Simple Runner",
    version="0.2.2",
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:*",
        "http://127.0.0.1:*"
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now()}


@app.get("/api/status")
async def get_status(client: Client = Depends(get_client)) -> StatusResponse:
    """Get application status."""
    return StatusResponse(
        app="Syft Simple Runner",
        version="0.2.2",
        timestamp=datetime.now(),
        syftbox={
            "status": "connected",
            "user_email": client.email
        },
        components={
            "backend": "running",
            "runner": "active",
            "job_history": "available",
            "job_browser": "enabled" if q else "disabled"
        }
    )


@app.get(
    "/api/v1/jobs/history",
    response_model=JobHistoryResponse,
    tags=["jobs"],
    summary="Get job execution history",
    description="Get the history of jobs that have been executed by this runner"
)
async def get_job_history_endpoint(
    limit: int = 50,
    status_filter: Optional[str] = None,
    client: Client = Depends(get_client),
) -> JobHistoryResponse:
    """Get job execution history."""
    try:
        jobs = get_job_history(client, limit=limit, status_filter=status_filter)
        return JobHistoryResponse(
            jobs=jobs,
            total=len(jobs),
            status="success"
        )
    except Exception as e:
        logger.error(f"Failed to get job history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/jobs/stats",
    response_model=JobStatsResponse,
    tags=["jobs"],
    summary="Get job execution statistics",
    description="Get statistics about job execution performance"
)
async def get_job_stats_endpoint(
    client: Client = Depends(get_client),
) -> JobStatsResponse:
    """Get job execution statistics."""
    try:
        stats = get_job_stats(client)
        return JobStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get job stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/jobs/history/{job_uid}",
    tags=["jobs"],
    summary="Get single job details",
    description="Get detailed information about a specific job"
)
async def get_job_details_endpoint(
    job_uid: str,
    client: Client = Depends(get_client),
) -> Dict[str, Any]:
    """Get details for a specific job."""
    try:
        jobs = get_job_history(client, limit=1000)  # Get more jobs to find the specific one
        job = next((j for j in jobs if j.uid == job_uid), None)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        return {
            "job": job.dict(),
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/jobs/history/{job_uid}/logs",
    tags=["jobs"],
    summary="Get job logs",
    description="Get execution logs for a specific job"
)
async def get_job_logs_endpoint(
    job_uid: str,
    client: Client = Depends(get_client),
) -> Dict[str, Any]:
    """Get logs for a specific job."""
    try:
        jobs = get_job_history(client, limit=1000)
        job = next((j for j in jobs if j.uid == job_uid), None)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        return {
            "uid": job.uid,
            "name": job.name,
            "logs": job.logs or "No logs available",
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete(
    "/api/v1/jobs/history/cleanup",
    response_model=MessageResponse,
    tags=["jobs"],
    summary="Clean up old job history",
    description="Remove job history older than specified days"
)
async def cleanup_job_history_endpoint(
    keep_days: int = 30,
    client: Client = Depends(get_client),
) -> MessageResponse:
    """Clean up old job history."""
    try:
        count = clear_old_job_history(client, keep_days)
        return MessageResponse(
            message=f"Cleaned up {count} old job records",
            status="success"
        )
    except Exception as e:
        logger.error(f"Failed to cleanup job history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend application."""
    try:
        # Try to serve the built frontend
        frontend_path = PathLib(__file__).parent.parent / "frontend" / "out" / "index.html"
        if frontend_path.exists():
            return HTMLResponse(content=frontend_path.read_text())
        else:
            # Fallback to a simple status page
            return HTMLResponse(content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Syft Simple Runner</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    h1 {{ color: #333; margin-bottom: 20px; }}
                    .status {{ background: #e8f5e8; padding: 15px; border-radius: 4px; margin: 20px 0; }}
                    .info {{ background: #e8f4fd; padding: 15px; border-radius: 4px; margin: 20px 0; }}
                    a {{ color: #0066cc; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🚀 Syft Simple Runner</h1>
                    <div class="status">
                        <strong>Status:</strong> Backend API Running
                    </div>
                    <div class="info">
                        <p><strong>API Documentation:</strong> <a href="/docs">/docs</a></p>
                        <p><strong>Health Check:</strong> <a href="/health">/health</a></p>
                        <p><strong>Job History API:</strong> <a href="/api/v1/jobs/history">/api/v1/jobs/history</a></p>
                        <p><strong>Job Statistics:</strong> <a href="/api/v1/jobs/stats">/api/v1/jobs/stats</a></p>
                    </div>
                    <p>The frontend is being built. For now, you can access the API endpoints directly.</p>
                </div>
            </body>
            </html>
            """)
    except Exception as e:
        logger.error(f"Error serving root: {e}")
        return HTMLResponse(content="<h1>Syft Simple Runner Backend</h1><p>API is running. Frontend not available.</p>")


# Mount static files if frontend exists
frontend_static = PathLib(__file__).parent.parent / "frontend" / "out"
if frontend_static.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_static)), name="static") 
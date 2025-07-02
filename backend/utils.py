"""Utility functions for syft-simple-runner backend."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from loguru import logger
from syft_core import Client

from .models import JobHistoryItem

try:
    import syft_code_queue as q
    from syft_code_queue import JobStatus, create_client
except ImportError:
    logger.error("syft-code-queue not available - job history will be limited")
    q = None
    create_client = None
    class JobStatus:
        pending = "pending"
        approved = "approved"
        running = "running"
        completed = "completed"
        failed = "failed"
        rejected = "rejected"


def get_job_history(client: Client, limit: int = 50, status_filter: Optional[str] = None) -> List[JobHistoryItem]:
    """Get job execution history from the syft-code-queue."""
    try:
        # Try to get jobs from syft-code-queue
        if q and create_client:
            try:
                queue_client = create_client()
                # Get jobs for this user
                all_jobs = queue_client.list_jobs(target_email=client.email)
                
                # Filter and convert to JobHistoryItem
                history_items = []
                for job in all_jobs:
                    # Apply status filter if provided
                    if status_filter and job.status.value != status_filter:
                        continue
                    
                    # Calculate execution time if possible
                    execution_time = None
                    if hasattr(job, 'started_at') and hasattr(job, 'completed_at'):
                        if job.started_at and job.completed_at:
                            try:
                                start = datetime.fromisoformat(job.started_at.replace('Z', '+00:00'))
                                end = datetime.fromisoformat(job.completed_at.replace('Z', '+00:00'))
                                execution_time = (end - start).total_seconds()
                            except:
                                pass
                    
                    # Determine success status
                    success = job.status.value == JobStatus.completed
                    
                    # Get logs if available
                    logs = getattr(job, 'logs', None) or "No logs available"
                    
                    history_item = JobHistoryItem(
                        uid=job.uid,
                        name=job.name,
                        status=job.status.value,
                        requester_email=job.requester_email,
                        target_email=job.target_email,
                        created_at=job.created_at,
                        started_at=getattr(job, 'started_at', None),
                        completed_at=getattr(job, 'completed_at', None),
                        execution_time=execution_time,
                        success=success,
                        logs=logs,
                        tags=getattr(job, 'tags', [])
                    )
                    history_items.append(history_item)
                
                # Sort by created_at descending and limit
                history_items.sort(key=lambda x: x.created_at, reverse=True)
                return history_items[:limit]
                
            except Exception as e:
                logger.warning(f"Failed to get jobs from syft-code-queue: {e}")
        
        # Fallback: try to read from local job history storage
        return _get_local_job_history(client, limit, status_filter)
        
    except Exception as e:
        logger.error(f"Error getting job history: {e}")
        return []


def _get_local_job_history(client: Client, limit: int = 50, status_filter: Optional[str] = None) -> List[JobHistoryItem]:
    """Get job history from local storage as fallback."""
    try:
        # Get the app data directory
        app_data_dir = client.app_data("syft-simple-runner")
        history_dir = app_data_dir / "job_history"
        
        if not history_dir.exists():
            return []
        
        history_items = []
        
        # Read all job history files
        for job_file in history_dir.glob("*.json"):
            try:
                with open(job_file, 'r') as f:
                    job_data = json.load(f)
                
                # Apply status filter if provided
                if status_filter and job_data.get('status') != status_filter:
                    continue
                
                history_item = JobHistoryItem(**job_data)
                history_items.append(history_item)
                
            except Exception as e:
                logger.warning(f"Failed to read job history file {job_file}: {e}")
                continue
        
        # Sort by created_at descending and limit
        history_items.sort(key=lambda x: x.created_at, reverse=True)
        return history_items[:limit]
        
    except Exception as e:
        logger.error(f"Error getting local job history: {e}")
        return []


def store_job_history(client: Client, job_data: Dict[str, Any]) -> bool:
    """Store job execution history locally."""
    try:
        # Get the app data directory
        app_data_dir = client.app_data("syft-simple-runner")
        history_dir = app_data_dir / "job_history"
        history_dir.mkdir(parents=True, exist_ok=True)
        
        # Create history file
        job_file = history_dir / f"{job_data['uid']}.json"
        
        with open(job_file, 'w') as f:
            json.dump(job_data, f, indent=2)
        
        logger.debug(f"Stored job history for {job_data['uid']}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing job history: {e}")
        return False


def get_job_stats(client: Client) -> Dict[str, Any]:
    """Get job execution statistics."""
    try:
        jobs = get_job_history(client, limit=1000)  # Get more jobs for stats
        
        total_jobs = len(jobs)
        successful_jobs = len([j for j in jobs if j.success])
        failed_jobs = len([j for j in jobs if not j.success and j.status not in ['pending', 'running']])
        running_jobs = len([j for j in jobs if j.status == 'running'])
        pending_jobs = len([j for j in jobs if j.status == 'pending'])
        
        success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0.0
        
        return {
            "total_jobs": total_jobs,
            "successful_jobs": successful_jobs,
            "failed_jobs": failed_jobs,
            "running_jobs": running_jobs,
            "pending_jobs": pending_jobs,
            "success_rate": round(success_rate, 2),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error getting job stats: {e}")
        return {
            "total_jobs": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "running_jobs": 0,
            "pending_jobs": 0,
            "success_rate": 0.0,
            "status": "error"
        }


def clear_old_job_history(client: Client, keep_days: int = 30) -> int:
    """Clear old job history records."""
    try:
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        # Get the app data directory
        app_data_dir = client.app_data("syft-simple-runner")
        history_dir = app_data_dir / "job_history"
        
        if not history_dir.exists():
            return 0
        
        cleaned_count = 0
        
        # Check each job history file
        for job_file in history_dir.glob("*.json"):
            try:
                with open(job_file, 'r') as f:
                    job_data = json.load(f)
                
                # Parse the created_at date
                created_at = datetime.fromisoformat(job_data['created_at'].replace('Z', '+00:00'))
                
                # Remove if older than cutoff
                if created_at < cutoff_date:
                    job_file.unlink()
                    cleaned_count += 1
                    logger.debug(f"Cleaned up old job history: {job_data['uid']}")
                    
            except Exception as e:
                logger.warning(f"Failed to process job history file {job_file}: {e}")
                continue
        
        return cleaned_count
        
    except Exception as e:
        logger.error(f"Error clearing old job history: {e}")
        return 0 
"""
Simplified queue implementation using syft-objects.
This is a copy of the syft-queue implementation for syft-simple-runner.
"""

from pathlib import Path
from typing import Union, Optional, List
from uuid import UUID, uuid4
from datetime import datetime
import enum
import json
import tempfile
import os
import subprocess
import random
import string
import time
import syft_objects as syo


class JobStatus(str, enum.Enum):
    """Status of a job in the queue."""
    
    inbox = "inbox"          # Waiting for approval
    approved = "approved"    # Approved, waiting to run
    running = "running"      # Currently executing
    completed = "completed"  # Finished successfully
    failed = "failed"        # Execution failed
    rejected = "rejected"    # Rejected by data owner
    timedout = "timedout"    # Timed out waiting for approval


class Job:
    """
    A job object that uses syft-objects natively for storage.
    
    All job metadata is stored in a syft-object that appears in syo.objects.
    Supports relative paths for portability across pipeline stages.
    """
    
    def __init__(self, folder_path: Union[str, Path], owner_email: str = None, **kwargs):
        """
        Initialize a Job.
        
        Args:
            folder_path: Path to the job folder
            owner_email: Email of the owner (if None, will auto-detect)
            **kwargs: Job attributes (uid, name, requester_email, etc.)
        """
        self.object_path = Path(folder_path).absolute()
        self.object_path.mkdir(parents=True, exist_ok=True)
        
        # Set job attributes
        self.uid = kwargs.get('uid', uuid4())
        self.name = kwargs.get('name', '')
        self.requester_email = kwargs.get('requester_email', '')
        self.target_email = kwargs.get('target_email', '')
        self.code_folder = kwargs.get('code_folder', '')
        self.description = kwargs.get('description', '')
        self.created_at = kwargs.get('created_at', datetime.now())
        self.timeout_seconds = kwargs.get('timeout_seconds', 86400)  # 24 hours
        self.tags = kwargs.get('tags', [])
        self.status = kwargs.get('status', JobStatus.inbox)
        self.updated_at = kwargs.get('updated_at', datetime.now())
        self.started_at = kwargs.get('started_at', None)
        self.completed_at = kwargs.get('completed_at', None)
        self.output_folder = kwargs.get('output_folder', None)
        self.error_message = kwargs.get('error_message', None)
        self.exit_code = kwargs.get('exit_code', None)
        self.logs = kwargs.get('logs', None)
        
        # New fields for relative path support
        self.base_path = kwargs.get('base_path', str(self.object_path))
        self.code_folder_relative = kwargs.get('code_folder_relative', None)
        self.output_folder_relative = kwargs.get('output_folder_relative', None)
        self.code_folder_absolute_fallback = kwargs.get('code_folder_absolute_fallback', None)
        self.output_folder_absolute_fallback = kwargs.get('output_folder_absolute_fallback', None)
        
        # Create syft-object for this job
        self._create_syft_object(owner_email)
    
    def _create_syft_object(self, owner_email: str = None):
        """Create the syft-object for this job."""
        metadata = self.to_dict()
        
        # Create the syft-object
        obj = syo.syobj(
            folder_path=self.object_path,
            metadata=metadata,
            owner_email=owner_email
        )
        
        # Save the object
        obj.save()
    
    def update_status(self, new_status: JobStatus, error_message: Optional[str] = None):
        """Update job status and persist."""
        self.status = new_status
        self.updated_at = datetime.now()
        
        if error_message:
            self.error_message = error_message
        
        if new_status == JobStatus.running:
            self.started_at = datetime.now()
        elif new_status in [JobStatus.completed, JobStatus.failed, JobStatus.rejected, JobStatus.timedout]:
            self.completed_at = datetime.now()
        
        # Update the syft-object
        self._create_syft_object()
    
    def to_dict(self) -> dict:
        """Convert job to dictionary for serialization."""
        def serialize_value(v):
            if isinstance(v, UUID):
                return str(v)
            elif isinstance(v, datetime):
                return v.isoformat()
            elif isinstance(v, Path):
                return str(v)
            elif isinstance(v, JobStatus):
                return v.value
            else:
                return v
        
        return {
            "uid": serialize_value(self.uid),
            "name": self.name,
            "requester_email": self.requester_email,
            "target_email": self.target_email,
            "code_folder": serialize_value(self.code_folder),
            "description": self.description,
            "created_at": serialize_value(self.created_at),
            "timeout_seconds": self.timeout_seconds,
            "tags": self.tags,
            "status": serialize_value(self.status),
            "updated_at": serialize_value(self.updated_at),
            "started_at": serialize_value(self.started_at),
            "completed_at": serialize_value(self.completed_at),
            "output_folder": serialize_value(self.output_folder),
            "error_message": self.error_message,
            "exit_code": self.exit_code,
            "logs": self.logs,
            "base_path": self.base_path,
            "code_folder_relative": self.code_folder_relative,
            "output_folder_relative": self.output_folder_relative,
            "code_folder_absolute_fallback": self.code_folder_absolute_fallback,
            "output_folder_absolute_fallback": self.output_folder_absolute_fallback,
        }


class Queue:
    """
    A queue that manages jobs using syft-objects natively.
    
    Queue structure:
    queue_folder/
    ├── inbox/
    ├── approved/
    ├── running/
    ├── completed/
    ├── failed/
    ├── rejected/
    └── timedout/
    """
    
    def __init__(self, folder_path: Union[str, Path], name: str = "default-queue", owner_email: str = None, **kwargs):
        """
        Initialize a Queue.
        
        Args:
            folder_path: Path where the queue will be created
            name: Name of the queue
            owner_email: Email of the owner (if None, will auto-detect)
            **kwargs: Additional queue configuration
        """
        self.object_path = Path(folder_path).absolute()
        self.name = name
        self.owner_email = owner_email
        
        # Create queue directories
        self._initialize_directories()
        
        # Create queue metadata object
        self._create_syft_object()
    
    def _initialize_directories(self):
        """Create the queue directory structure."""
        for status in JobStatus:
            status_dir = self.object_path / status.value
            status_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_syft_object(self):
        """Create the syft-object for this queue."""
        metadata = {
            "name": self.name,
            "created_at": datetime.now().isoformat(),
            "owner_email": self.owner_email
        }
        
        obj = syo.syobj(
            folder_path=self.object_path,
            metadata=metadata,
            owner_email=self.owner_email
        )
        obj.save()
    
    def create_job(self, name: str, requester_email: str, target_email: str, **kwargs) -> Job:
        """
        Create a new job in the queue.
        
        Args:
            name: Name of the job
            requester_email: Email of the requester
            target_email: Email of the target (data owner)
            **kwargs: Additional job parameters
            
        Returns:
            Job: The created job
        """
        job_uid = uuid4()
        job_dir = self.object_path / JobStatus.inbox.value / str(job_uid)
        
        job = Job(
            job_dir,
            owner_email=self.owner_email,
            uid=job_uid,
            name=name,
            requester_email=requester_email,
            target_email=target_email,
            status=JobStatus.inbox,
            **kwargs
        )
        
        return job
    
    def list_jobs(self, status: Optional[JobStatus] = None, target_email: Optional[str] = None) -> List[Job]:
        """
        List jobs in the queue.
        
        Args:
            status: Filter by status (if None, return all)
            target_email: Filter by target email
            
        Returns:
            List[Job]: List of jobs matching criteria
        """
        jobs = []
        statuses = [status] if status else list(JobStatus)
        
        for job_status in statuses:
            status_dir = self.object_path / job_status.value
            if not status_dir.exists():
                continue
                
            for job_dir in status_dir.iterdir():
                if not job_dir.is_dir():
                    continue
                    
                try:
                    # Load job from syft-object
                    obj = syo.syobj(job_dir)
                    if obj and obj.metadata:
                        # Filter by target_email if specified
                        if target_email and obj.metadata.get('target_email') != target_email:
                            continue
                            
                        # Create Job instance from metadata
                        job = Job(job_dir, owner_email=self.owner_email, **obj.metadata)
                        jobs.append(job)
                except Exception as e:
                    print(f"Error loading job from {job_dir}: {e}")
                    continue
        
        return jobs
    
    def get_job_by_uid(self, job_uid: Union[str, UUID]) -> Optional[Job]:
        """Get a job by its UID."""
        if isinstance(job_uid, str):
            job_uid = UUID(job_uid)
            
        for status in JobStatus:
            job_dir = self.object_path / status.value / str(job_uid)
            if job_dir.exists():
                try:
                    obj = syo.syobj(job_dir)
                    if obj and obj.metadata:
                        return Job(job_dir, owner_email=self.owner_email, **obj.metadata)
                except Exception:
                    continue
        return None
    
    def move_job(self, job: Job, new_status: JobStatus):
        """Move a job to a new status directory."""
        old_dir = job.object_path
        new_dir = self.object_path / new_status.value / str(job.uid)
        
        if old_dir != new_dir:
            # Create new directory
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # Move the job directory
            if old_dir.exists():
                old_dir.rename(new_dir)
                
            # Update job path
            job.object_path = new_dir
            job.update_status(new_status)


def q(name: str = "default-queue", owner_email: str = None, force: bool = False, **kwargs) -> Queue:
    """
    Create a new queue with automatic path creation (short alias).
    
    Queues are created in SyftBox/datasites/<email>/app_data/syft-queues/ by default.
    Falls back to current directory if SyftBox is not configured.
    
    Args:
        name: Name of the queue (will be used as folder name)
        owner_email: Email of the owner (if None, will auto-detect)
        force: If True, replace existing queue with same name
        **kwargs: Additional queue configuration
        
    Returns:
        Queue: The created queue object
    """
    # Try to get SyftBox path
    syftbox_path = os.getenv('SYFTBOX_PATH')
    if syftbox_path and owner_email:
        base_path = Path(syftbox_path) / "datasites" / owner_email / "app_data" / "syft-queues"
    else:
        # Fallback to temp directory
        base_path = Path(tempfile.gettempdir()) / "syft-queues"
    
    folder_path = base_path / name
    
    if folder_path.exists() and not force:
        # Return existing queue
        return Queue(folder_path, name, owner_email=owner_email, **kwargs)
    
    return Queue(folder_path, name, owner_email=owner_email, **kwargs)
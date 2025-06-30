"""
Local models for syft-simple-runner to work independently.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import json

class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QueueConfig:
    """Configuration for the job queue."""
    
    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.jobs_dir = self.base_path / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
    
    def get_job_file(self, job_id: str) -> Path:
        """Get the path to a job file."""
        return self.jobs_dir / f"{job_id}.json"
    
    def list_jobs(self) -> List[str]:
        """List all job IDs."""
        return [f.stem for f in self.jobs_dir.glob("*.json")]


class SimpleJob:
    """Simple job representation for the runner."""
    
    def __init__(self, job_data: Dict[str, Any]):
        self.uid = job_data.get("uid", "")
        self.name = job_data.get("name", "Unnamed Job")
        self.status = JobStatus(job_data.get("status", "pending"))
        self.requester_email = job_data.get("requester_email", "")
        self.target_email = job_data.get("target_email", "")
        self.script_content = job_data.get("script_content", "")
        self.requirements_content = job_data.get("requirements_content", "")
        self.created_at = job_data.get("created_at", datetime.now().isoformat())
        self.approved_at = job_data.get("approved_at")
        self.completed_at = job_data.get("completed_at")
        self.logs = job_data.get("logs", "")
        self.exit_code = job_data.get("exit_code")
    
    @classmethod
    def from_file(cls, job_file: Path) -> "SimpleJob":
        """Load job from JSON file."""
        with open(job_file, 'r') as f:
            data = json.load(f)
        return cls(data)
    
    def save_to_file(self, job_file: Path):
        """Save job to JSON file."""
        data = {
            "uid": self.uid,
            "name": self.name,
            "status": self.status.value,
            "requester_email": self.requester_email,
            "target_email": self.target_email,
            "script_content": self.script_content,
            "requirements_content": self.requirements_content,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "completed_at": self.completed_at,
            "logs": self.logs,
            "exit_code": self.exit_code,
        }
        with open(job_file, 'w') as f:
            json.dump(data, f, indent=2)

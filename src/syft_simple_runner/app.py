#!/usr/bin/env python3
"""
Syft Simple Runner App - SyftBox Integration

This module runs as a SyftBox app, continuously polling for approved code execution jobs.
"""

import time
import json
from pathlib import Path
from loguru import logger
from datetime import datetime
import signal
import sys
from time import sleep
from typing import Optional

from syft_code_queue import CodeJob, JobStatus, QueueConfig, create_client

try:
    from syft_core import Client as SyftBoxClient
except ImportError:
    logger.warning("syft_core not available - using mock client")
    # Fallback for development/testing
    class MockSyftBoxClient:
        def __init__(self):
            self.email = "demo@example.com"
        
        def app_data(self, app_name):
            import tempfile
            return Path(tempfile.gettempdir()) / f"syftbox_demo_{app_name}"
        
        @classmethod
        def load(cls):
            return cls()
    
    SyftBoxClient = MockSyftBoxClient

from .runner import run_job


class SimpleRunnerApp:
    """Simple app that polls for and executes code jobs."""
    
    def __init__(self, config: Optional[QueueConfig] = None):
        """Initialize the app."""
        try:
            self.syftbox_client = SyftBoxClient.load()
            self.config = config or QueueConfig(queue_name="code-queue")
            self.client = create_client(config=self.config)

            logger.info(f"Initialized Simple Runner App for {self.email}")
        except Exception as e:
            logger.warning(f"Could not initialize Simple Runner: {e}")
            # Set up in demo mode
            self.syftbox_client = SyftBoxClient()
            self.config = config or QueueConfig(queue_name="code-queue")
            self.client = None
    
    @property
    def email(self) -> str:
        """Get the current user's email."""
        return self.syftbox_client.email
    
    def run(self, poll_interval: int = 1):
        """
        Start continuous job polling and execution.

        Args:
            poll_interval: Seconds between polling cycles
        """
        logger.info(f"🔄 Starting continuous job polling (every {poll_interval} second)...")
        
        cycle = 0
        while True:
            try:
                # Process one cycle
                self._process_cycle()
                cycle += 1
                
                # Sleep until next cycle
                sleep(poll_interval)
            
            except KeyboardInterrupt:
                logger.info("👋 Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in processing cycle {cycle}: {e}")
                # Continue running despite errors
                sleep(poll_interval)
    
    def _process_cycle(self):
        """Process one polling cycle."""
        if self.client is None:
            return

        # Log pending jobs
        self._log_pending_jobs()

        # Execute approved jobs
        self._execute_approved_jobs()
    
    def _log_pending_jobs(self):
        """Log information about pending jobs."""
        if self.client is None:
            return
        
        # Get pending jobs for this user
        pending_jobs = self.client.list_jobs(target_email=self.email, status=JobStatus.pending)
        
        if pending_jobs:
            logger.info(f"📋 {len(pending_jobs)} job(s) pending approval:")
            for job in pending_jobs:
                logger.info(f"   • {job.name} from {job.requester_email}")
        # Don't log when no jobs - too verbose for continuous polling
    
    def _execute_approved_jobs(self):
        """Execute all approved jobs."""
        if self.client is None:
            return
        
        # Get approved jobs for this user
        approved_jobs = self.client.list_jobs(target_email=self.email, status=JobStatus.approved)
        
        if not approved_jobs:
            # Don't log when no jobs - too verbose for continuous polling
            return
        
        logger.info(f"🚀 Executing {len(approved_jobs)} approved job(s)")
        
        for job in approved_jobs:
            self._execute_single_job(job)
    
    def _execute_single_job(self, job: CodeJob):
        """Execute a single job."""
        if self.client is None:
            return

        logger.info(f"Starting execution of job: {job.name}")
        
        start_time = datetime.now()
        
        try:
            # Update status to running
            job.update_status(JobStatus.running)
            self.client._save_job(job)
            
            # Get the job directory
            job_dir = self.client._get_job_dir(job)
            code_dir = job_dir / "code"
            run_script = code_dir / "run.sh"

            # Validate script
            if not self._validate_script(run_script):
                job.update_status(JobStatus.rejected, "Script contains potentially dangerous commands")
                self.client._save_job(job)
                self._store_job_history(job, start_time, datetime.now(), False, "Script validation failed")
                return

            # Create output directory
            output_dir = job_dir / "output"
            output_dir.mkdir(exist_ok=True)
            job.output_folder = output_dir

            # Execute the script
            success, logs = run_job(job, code_dir, output_dir)
            
            # Update job status and logs
            if success:
                job.update_status(JobStatus.completed)
            else:
                job.update_status(JobStatus.failed, "Execution failed")
            
            # Save logs
            job.logs = logs
            
            # Store job history
            end_time = datetime.now()
            self._store_job_history(job, start_time, end_time, success, logs)
            
        except Exception as e:
            logger.error(f"Error executing job {job.name}: {e}")
            job.update_status(JobStatus.failed, str(e))
            job.logs = str(e)
            
            # Store job history for failed execution
            end_time = datetime.now()
            self._store_job_history(job, start_time, end_time, False, str(e))
        
        finally:
            # Always save the final job state
            self.client._save_job(job)
    
    def _store_job_history(self, job: CodeJob, start_time: datetime, end_time: datetime, success: bool, logs: str):
        """Store job execution history locally."""
        try:
            # Get the app data directory
            app_data_dir = self.syftbox_client.app_data("syft-simple-runner")
            history_dir = app_data_dir / "job_history"
            history_dir.mkdir(parents=True, exist_ok=True)
            
            # Calculate execution time
            execution_time = (end_time - start_time).total_seconds()
            
            # Create job history data
            job_data = {
                "uid": job.uid,
                "name": job.name,
                "status": job.status.value,
                "requester_email": job.requester_email,
                "target_email": job.target_email,
                "created_at": job.created_at,
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "execution_time": execution_time,
                "success": success,
                "logs": logs,
                "tags": getattr(job, 'tags', [])
            }
            
            # Store in history file
            history_file = history_dir / f"{job.uid}.json"
            with open(history_file, 'w') as f:
                json.dump(job_data, f, indent=2)
            
            logger.debug(f"Stored job history for {job.uid}")
            
        except Exception as e:
            logger.warning(f"Failed to store job history: {e}")
    
    def _validate_script(self, script_path: Path) -> bool:
        """Validate that a script is safe to execute."""
        try:
            # Basic validation - check that script exists and is readable
            if not script_path.exists():
                logger.error(f"Script does not exist: {script_path}")
                return False

            # Read script content
            script_content = script_path.read_text()

            # Check for potentially dangerous commands
            dangerous_commands = [
                "rm -rf",
                "sudo",
                "> /dev/null",
                "2>&1",
                "wget",
                "curl",
                "nc",
                "netcat",
            ]
        
            for cmd in dangerous_commands:
                if cmd in script_content:
                    logger.warning(f"Script contains dangerous command: {cmd}")
                    return False

            return True
        except Exception as e:
            logger.error(f"Failed to validate script: {e}")
            return False


def main():
    """Main entry point for the SyftBox app."""
    try:
        app = SimpleRunnerApp()
        app.run()
    except Exception as e:
        logger.error(f"App failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()

"""Safe code execution runner for syft-simple-runner."""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Tuple

from loguru import logger
from syft_code_queue import CodeJob


def run_job(job: CodeJob, code_dir: Path, output_dir: Path) -> Tuple[bool, str]:
    """
    Run a code job in a safe environment.

    Args:
        job: The job to run
        code_dir: Directory containing the code
        output_dir: Directory to store output

    Returns:
        Tuple of (success, logs)
    """
    try:
        # Validate script exists
        run_script = code_dir / "run.sh"
        if not run_script.exists():
            return False, f"run.sh not found in {code_dir}"

        # Make script executable
        run_script.chmod(0o755)

        # Set up environment
        env = os.environ.copy()
        env["OUTPUT_DIR"] = str(output_dir)
        env["CODE_DIR"] = str(code_dir)
        env["JOB_ID"] = str(job.uid)
        env["JOB_NAME"] = job.name

        # Create log file
        job_dir = code_dir.parent  # code_dir is job_dir/code, so parent is job_dir
        log_file = job_dir / "execution.log"

        # Write initial log header
        with open(log_file, "w") as f:
            f.write(f"Job: {job.name} ({job.uid})\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write(f"Working Directory: {code_dir}\n")
            f.write(f"Output Directory: {output_dir}\n")
            f.write("-" * 80 + "\n\n")

        # Run the script and capture output in real-time
        process = subprocess.Popen(
            [str(run_script)],
            cwd=code_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Capture output
        stdout, stderr = process.communicate()

        # Format logs
        logs = []
        logs.append("STDOUT:")
        logs.append(stdout)
        logs.append("\nSTDERR:")
        logs.append(stderr)
        logs.append(f"\nExit Code: {process.returncode}")
        logs.append(f"Completed: {datetime.now().isoformat()}")
        log_content = "\n".join(logs)

        # Write logs to file
        with open(log_file, "a") as f:
            f.write(log_content)

        # Check result
        success = process.returncode == 0
        if not success:
            logger.warning(f"Job {job.uid} failed with exit code {process.returncode}")
            logger.warning(f"Error output:\n{stderr}")

        return success, log_content

    except Exception as e:
        error_msg = f"Error running job: {e}"
        logger.error(error_msg)

        # Try to write error to log file
        try:
            job_dir = code_dir.parent
            log_file = job_dir / "execution.log"
            with open(log_file, "w") as f:
                f.write(f"Job: {job.name} ({job.uid})\n")
                f.write(f"Error: {error_msg}\n")
                f.write(f"Time: {datetime.now().isoformat()}\n")
        except Exception:
            pass  # If we can't write to log file, just continue

        return False, error_msg 
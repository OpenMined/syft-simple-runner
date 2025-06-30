"""Simple code execution runner for SyftBox."""

from .app import SimpleRunnerApp
from .runner import run_job

__version__ = "0.2.1"
__all__ = ["SimpleRunnerApp", "run_job"]

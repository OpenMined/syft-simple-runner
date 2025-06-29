#!/bin/bash
set -e

# SyftBox app entry point for syft-simple-runner  
# This script starts the long-running job polling service

echo "🚀 Syft Simple Runner - Starting service..."

# Create virtual environment with uv (remove old one if exists)
echo "📦 Setting up virtual environment with uv..."
rm -rf .venv
uv venv -p 3.12

# Install dependencies using uv
echo "📦 Installing dependencies..."
uv pip install -e .

# Run the queue processor (long-running service)
echo "🔄 Starting job polling service..."
uv run python -m syft_simple_runner.app

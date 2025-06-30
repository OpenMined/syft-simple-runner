#!/bin/bash
set -e

# SyftBox app entry point for syft-simple-runner  
# This script starts the long-running job polling service

echo "🚀 Syft Simple Runner - Starting service..."

# Disable interactive prompts and shell customizations for non-interactive environments
export ZSH_DISABLE_COMPFIX=true
export NONINTERACTIVE=1

# Create virtual environment with uv (remove old one if exists)
echo "📦 Setting up virtual environment with uv..."
rm -rf .venv

# Let uv handle Python version management - it will download if needed
echo "🐍 Creating virtual environment with Python 3.12..."
uv venv --python 3.12

# Activate the virtual environment to ensure we use the correct Python
source .venv/bin/activate

# Install dependencies using the virtual environment's pip
echo "📦 Installing dependencies..."
python -m pip install --no-cache-dir -e .

# Run the queue processor (long-running service)
echo "🔄 Starting job polling service..."
python -m syft_simple_runner.app

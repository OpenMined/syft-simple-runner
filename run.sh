#!/bin/bash
set -e

# SyftBox app entry point for syft-simple-runner  
# This script starts the job polling service and web UI

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

# Set the virtual environment path for uv to use
export VIRTUAL_ENV="$(pwd)/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies using uv sync (which respects the virtual environment)
echo "📦 Installing dependencies..."
uv sync

# Build frontend if bun is available and frontend directory exists
if command -v bun &> /dev/null && [ -d "frontend" ]; then
    echo "📦 Building frontend with bun..."
    cd frontend
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing frontend dependencies..."
        bun install
    fi
    echo "🔨 Building frontend..."
    bun run build || echo "⚠️  Frontend build failed, continuing with backend only"
    cd ..
else
    echo "⚠️  bun not found or frontend directory missing, skipping frontend build"
fi

# Start the backend API server in the background
echo "🌐 Starting web UI backend on port ${SYFTBOX_ASSIGNED_PORT:-8002}..."
SYFTBOX_ASSIGNED_PORT=${SYFTBOX_ASSIGNED_PORT:-8002}
uv run uvicorn backend.main:app --host 0.0.0.0 --port $SYFTBOX_ASSIGNED_PORT &
BACKEND_PID=$!

# Ensure backend is killed on script exit
trap 'kill $BACKEND_PID' EXIT

echo "⏳ Waiting for backend to start..."
sleep 3

# Run the job polling service (long-running service)
echo "🔄 Starting job polling service..."
uv run python -m syft_simple_runner.app

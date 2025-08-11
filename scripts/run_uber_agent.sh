#!/bin/bash

echo "=== Starting Uber Services Agent ==="

echo "SUI configuration will be loaded from .env file"

export PORT=10004

echo "✅ Configuration:"
echo "   - SUI configuration: From .env file"
echo "   - Port: $PORT"

cd "$(dirname "$0")/../samples/python/agents/uber_services" || exit 1

echo "📂 Working directory: $(pwd)"

if [ ! -d ".venv" ]; then
    echo "🔧 Creating virtual environment..."
    python -m venv .venv
fi

echo "🚀 Activating virtual environment..."
source .venv/bin/activate

echo "📦 Installing dependencies..."
if [ -f "pyproject.toml" ]; then
    # First install the root project (includes common dependencies)
    pip install -e ../../
    # Then install the current project
    pip install -e .
else
    echo "❌ pyproject.toml file not found"
    exit 1
fi

# 启动 Uber Agent
echo ""
echo "🚗 Uber Services Agent (port $PORT) is running..."
echo "   Access Agent Card: http://localhost:$PORT/.well-known/agent.json"
echo "   SUI configuration from .env file"
echo "   Use Ctrl+C to stop the service"
echo ""

python __main__.py --host localhost --port $PORT

echo "👋 Uber Services Agent stopped" 
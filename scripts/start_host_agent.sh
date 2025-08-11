#!/bin/bash

cd "$(dirname "$0")/../demo/ui" || exit

source .venv/bin/activate

echo "Check SUI configuration..."
echo "SUI configuration will be loaded from .env file"

echo "Running Host Agent UI..."
uv run main.py

# If you need to specify a port, you can use:
# uv run main.py --port 12000 
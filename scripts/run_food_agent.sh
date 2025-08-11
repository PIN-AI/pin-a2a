#!/bin/bash

cd "$(dirname "$0")/../samples/python" || exit

source .venv/bin/activate

echo "Check SUI configuration..."
echo "SUI configuration will be loaded from .env file"

echo "Running Food Ordering Service Agent..."
uv run agents/food_ordering_services --host 0.0.0.0 --port 10003

# If you need to specify a port, you can use:
# uv run agents/food_ordering_services --port 10002 
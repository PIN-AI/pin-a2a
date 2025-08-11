#!/bin/bash

cd "$(dirname "$0")/../samples/python" || exit

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "Virtual environment activated"
fi

echo "Check SUI configuration..."
echo "SUI configuration will be loaded from .env file"

# Load .env file from agent directory if it exists
ENV_FILE="agents/food_ordering_services/.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading .env file from $ENV_FILE..."
    # More robust .env parsing that handles comments and special characters
    while IFS= read -r line; do
        # Skip empty lines and comments
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        # Extract key=value pairs and export them
        if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            value="${BASH_REMATCH[2]}"
            # Remove quotes if present
            value="${value%\"}"
            value="${value#\"}"
            export "$key=$value"
        fi
    done < "$ENV_FILE"
else
    echo "No .env file found at $ENV_FILE"
fi

# Check for required environment variables
if [ -z "$GOOGLE_API_KEY" ] && [ "$GOOGLE_GENAI_USE_VERTEXAI" != "TRUE" ]; then
    echo "Warning: GOOGLE_API_KEY not set and GOOGLE_GENAI_USE_VERTEXAI is not TRUE"
    echo "The agent may fail to start without proper API configuration"
fi

echo "Running Food Ordering Service Agent..."
echo "Command: PYTHONPATH=. python -m agents.food_ordering_services --host 0.0.0.0 --port 10003"

# Check if the module can be imported first
echo "Testing module import..."
PYTHONPATH=. python -c "
try:
    from agents.food_ordering_services.__main__ import main
    print('✓ Module import successful')
except Exception as e:
    print(f'✗ Module import failed: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "Module import failed, cannot start agent"
    exit 1
fi

# Run with error handling
echo "Starting agent..."
echo "If the agent starts successfully, you should see server startup messages..."
echo "Press Ctrl+C to stop the agent"
echo "----------------------------------------"

PYTHONPATH=. python -m agents.food_ordering_services --host 0.0.0.0 --port 10003 --verify-signatures 2>&1 | tee agent.log || {
    echo "----------------------------------------"
    echo "Agent failed to start. Exit code: $?"
    echo "Check agent.log for details"
    exit 1
}

# If you need to specify a port, you can use:
# PYTHONPATH=. python -m agents.food_ordering_services --host 0.0.0.0 --port 10002 
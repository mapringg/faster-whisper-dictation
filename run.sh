#!/bin/bash

set -e  # Exit on error

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}


# Check if we're in the correct directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source .env file from home directory if it exists
if [ -f "$HOME/.env" ]; then
    log "Loading environment from $HOME/.env"
    source "$HOME/.env"
fi

# Source .env file from project directory if it exists (overrides home .env)
if [ -f "$SCRIPT_DIR/.env" ]; then
    log "Loading environment from $SCRIPT_DIR/.env"
    source "$SCRIPT_DIR/.env"
fi

# Parse command line arguments to check for transcriber selection
TRANSCRIBER="openai"  # Default to OpenAI
for arg in "$@"; do
    if [[ $arg == "--transcriber" ]]; then
        TRANSCRIBER="${2:-openai}"
        break
    fi
done

# Check for appropriate API key based on transcriber
if [ "$TRANSCRIBER" = "openai" ]; then
    if [ -z "$OPENAI_API_KEY" ]; then
        log "Error: OPENAI_API_KEY environment variable is not set"
        log "Please set it directly, in ./env, or in ~/.env file."
        exit 1
    fi
else
    if [ -z "$GROQ_API_KEY" ]; then
        log "Error: GROQ_API_KEY environment variable is not set"
        log "Please set it directly, in ./env, or in ~/.env file."
        exit 1
    fi
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    log "Error: Virtual environment not found in $SCRIPT_DIR/.venv"
    log "Please run setup.sh first to create the virtual environment"
    exit 1
fi

# Activate virtual environment
log "Activating virtual environment"
source ".venv/bin/activate"

# Check if required Python packages are installed based on OS
if [[ "$(uname)" == "Darwin" ]]; then
    if ! python -c "import sounddevice; import soundfile; import pynput" 2>/dev/null; then
        log "Error: Required Python packages are missing"
        log "Please run setup.sh to install the required packages"
        exit 1
    fi
elif [[ "$(uname)" == "Linux" ]]; then
    if ! python -c "import sounddevice; import soundfile;" 2>/dev/null; then
        log "Error: Required Python packages are missing"
        log "Please run setup.sh to install the required packages"
        exit 1
    fi
else
    if ! python -c "import sounddevice; import soundfile; import pynput" 2>/dev/null; then
        log "Error: Required Python packages are missing"
        log "Please run setup.sh to install the required packages"
        exit 1
    fi
fi

# Run the dictation tool
log "Starting dictation service..."
exec python "$SCRIPT_DIR/main.py" "$@"

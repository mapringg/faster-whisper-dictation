#!/bin/bash

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Installing required packages for memory monitoring..."
source .venv/bin/activate
pip install psutil matplotlib

log "Starting the application in one terminal..."
osascript -e 'tell application "Terminal" to do script "cd '$PWD' && source setup.sh"'
sleep 5  # Give time for the app to start

log "Finding the Python process ID..."
PROCESS_ID=$(ps -ef | grep "python.*main.py" | grep -v grep | awk '{print $2}')

if [ -z "$PROCESS_ID" ]; then
    log "Error: Could not find running Python process. Make sure the application has started."
    exit 1
fi

log "Found Python process with ID: $PROCESS_ID"
log "Starting memory monitoring for 5 minutes..."

python memory_monitor.py --pid $PROCESS_ID --duration 300 --interval 5 --output memory_usage_before_fix.png

log "Memory monitoring complete. Check the memory_usage_before_fix.png file for results."
log "To test again after applying the fix, run this script again."
log "To stop the application, use the 'Exit' option in the status icon menu."
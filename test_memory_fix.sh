#!/bin/bash

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if this is running as root
if [ "$(id -u)" = "0" ]; then
    log "This script should not be run as root"
    exit 1
fi

# Default values
DURATION=3600  # 1 hour by default
INTERVAL=10    # 10 seconds between samples
OUTPUT="memory_usage_after_fix.png"
VERBOSE=0

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --duration|-d)
            DURATION="$2"
            shift 2
            ;;
        --interval|-i)
            INTERVAL="$2"
            shift 2
            ;;
        --output|-o)
            OUTPUT="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=1
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --duration, -d NUM   Monitor for NUM seconds (default: 3600)"
            echo "  --interval, -i NUM   Sample every NUM seconds (default: 10)"
            echo "  --output, -o FILE    Save memory graph to FILE (default: memory_usage_after_fix.png)"
            echo "  --verbose, -v        Show detailed output"
            echo "  --help, -h           Show this help message"
            exit 0
            ;;
        *)
            log "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Make the duration and interval arguments integers
DURATION=$(echo $DURATION | awk '{print int($1)}')
INTERVAL=$(echo $INTERVAL | awk '{print int($1)}')

# Validate arguments
if [ $DURATION -lt 60 ]; then
    log "Duration must be at least 60 seconds"
    exit 1
fi

if [ $INTERVAL -lt 1 ]; then
    log "Interval must be at least 1 second"
    exit 1
fi

log "Installing required packages for memory monitoring..."
source .venv/bin/activate
pip install -q psutil matplotlib

# Check if we're on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    log "Starting the application in a new terminal window..."
    osascript -e 'tell application "Terminal" to do script "cd '$PWD' && source setup.sh"'
else
    log "Starting the application in the background..."
    nohup ./setup.sh > /tmp/dictation_setup.log 2>&1 &
fi

log "Waiting for application to start..."
sleep 10  # Give more time for the app to fully initialize

log "Finding the Python process ID..."
PROCESS_ID=$(ps -ef | grep "python.*main.py" | grep -v grep | awk '{print $2}')

if [ -z "$PROCESS_ID" ]; then
    log "Error: Could not find running Python process. Make sure the application has started."
    log "Check /tmp/dictation_setup.log for startup errors."
    exit 1
fi

log "Found Python process with ID: $PROCESS_ID"
log "Starting memory monitoring for $(($DURATION / 60)) minutes with samples every $INTERVAL seconds..."
log "Memory data will be saved to $OUTPUT"

# More detailed output if verbose mode is enabled
if [ $VERBOSE -eq 1 ]; then
    log "Initial process info:"
    ps -o pid,ppid,user,%cpu,%mem,vsz,rss,tt,state,start,time,command -p $PROCESS_ID
fi

# Run the memory monitor
python memory_monitor.py --pid $PROCESS_ID --duration $DURATION --interval $INTERVAL --output $OUTPUT

log "Memory monitoring complete. Check the $OUTPUT file for results."

# More detailed output if verbose mode is enabled
if [ $VERBOSE -eq 1 ]; then
    log "Final process info:"
    ps -o pid,ppid,user,%cpu,%mem,vsz,rss,tt,state,start,time,command -p $PROCESS_ID
fi

log "To stop the application, use the 'Exit' option in the status icon menu."
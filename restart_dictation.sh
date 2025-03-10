#!/bin/bash

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Wait for graphical session to be ready
for i in {1..30}; do
    if systemctl --user is-active graphical-session.target >/dev/null 2>&1; then
        log "Graphical session is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        log "Timeout waiting for graphical session"
        exit 1
    fi
    sleep 1
done

# Check if the service is running
if systemctl --user is-active --quiet dictation.service; then
    log "Dictation service is already running"
    
    # Check if service is functioning properly
    if ! systemctl --user status dictation.service | grep -q "running"; then
        log "Service appears to be in a bad state, restarting..."
        systemctl --user restart dictation.service
    fi
else
    log "Starting dictation service..."
    systemctl --user restart dictation.service
fi

# Verify service started successfully
sleep 2
if ! systemctl --user is-active --quiet dictation.service; then
    log "Failed to start dictation service"
    systemctl --user status dictation.service
    exit 1
fi

log "Dictation service is running properly" 
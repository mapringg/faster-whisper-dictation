#!/bin/bash

# Wait for X server to be fully initialized
sleep 10

# Check if the service is running
if systemctl --user is-active --quiet dictation.service; then
    echo "Dictation service is already running."
else
    echo "Starting dictation service..."
    # Restart the user service (no elevated privileges needed)
    systemctl --user restart dictation.service
fi 
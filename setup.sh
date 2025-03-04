#!/bin/bash

# Make run.sh executable
chmod +x run.sh

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Setting up for macOS..."
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p ~/Library/LaunchAgents
    
    # Copy plist file
    cp com.user.dictation.plist ~/Library/LaunchAgents/
    
    # Load the service
    launchctl unload ~/Library/LaunchAgents/com.user.dictation.plist 2>/dev/null
    launchctl load ~/Library/LaunchAgents/com.user.dictation.plist
    
    echo "macOS setup complete! The service will start automatically on login."
    echo "To check status: launchctl list | grep com.user.dictation"
    echo "Logs are available at: /tmp/dictation.stdout.log and /tmp/dictation.stderr.log"

elif [[ -f /etc/debian_version ]] || [[ -f /etc/linuxmint/info ]]; then
    echo "Setting up for Linux Mint/Debian..."
    
    # Copy service file
    sudo cp dictation.service /etc/systemd/system/
    
    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable dictation.service
    sudo systemctl start dictation.service
    
    echo "Linux setup complete! The service will start automatically on boot."
    echo "To check status: sudo systemctl status dictation.service"
    echo "To view logs: journalctl -u dictation.service"

else
    echo "Unsupported operating system"
    exit 1
fi 
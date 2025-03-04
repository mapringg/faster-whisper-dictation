#!/bin/bash

# Make run.sh executable
chmod +x run.sh
chmod +x restart_dictation.sh

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
    
    # Create user systemd directory if it doesn't exist
    mkdir -p ~/.config/systemd/user
    
    # Copy service file to user systemd directory
    cp dictation.service ~/.config/systemd/user/
    
    # Install autostart entry
    mkdir -p ~/.config/autostart
    cp dictation-autostart.desktop ~/.config/autostart/
    
    # Reload user systemd and enable service
    systemctl --user daemon-reload
    systemctl --user stop dictation.service 2>/dev/null
    systemctl --user enable dictation.service
    
    # Start the service
    systemctl --user start dictation.service
    
    echo "Linux setup complete! The service will start automatically on login."
    echo "To check status: systemctl --user status dictation.service"
    echo "To view logs: journalctl --user -u dictation.service"
    echo "An autostart entry has been added to restart the service after login."
    echo "If you encounter issues, try manually starting the service after login with:"
    echo "systemctl --user restart dictation.service"

else
    echo "Unsupported operating system"
    exit 1
fi 
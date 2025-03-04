#!/bin/bash

echo "Reverting dictation service setup..."

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Reverting macOS setup..."
    
    # Unload the service
    echo "Unloading launchd service..."
    launchctl unload ~/Library/LaunchAgents/com.user.dictation.plist 2>/dev/null
    
    # Remove plist file
    echo "Removing plist file..."
    rm -f ~/Library/LaunchAgents/com.user.dictation.plist
    
    echo "macOS reversion complete! All dictation service files have been removed."

elif [[ -f /etc/debian_version ]] || [[ -f /etc/linuxmint/info ]]; then
    echo "Reverting Linux Mint/Debian setup..."
    
    # Stop and disable user service
    echo "Stopping and disabling user service..."
    systemctl --user stop dictation.service 2>/dev/null
    systemctl --user disable dictation.service 2>/dev/null
    
    # Remove user service file
    echo "Removing user service file..."
    rm -f ~/.config/systemd/user/dictation.service
    systemctl --user daemon-reload
    
    # Stop and disable system service if it exists
    echo "Stopping and disabling system service (if it exists)..."
    sudo systemctl stop dictation.service 2>/dev/null
    sudo systemctl disable dictation.service 2>/dev/null
    
    # Remove system service file if it exists
    echo "Removing system service file (if it exists)..."
    if [ -f /etc/systemd/system/dictation.service ]; then
        sudo rm -f /etc/systemd/system/dictation.service
        sudo systemctl daemon-reload
    fi
    
    # Remove autostart entry
    echo "Removing autostart entry..."
    rm -f ~/.config/autostart/dictation-autostart.desktop
    
    echo "Linux reversion complete! All dictation service files have been removed."

else
    echo "Unsupported operating system"
    exit 1
fi

echo "If you want to completely remove the application, you can delete this directory." 
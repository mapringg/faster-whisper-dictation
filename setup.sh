#!/bin/bash

set -e  # Exit on error

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Get absolute path of the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Make scripts executable
log "Making scripts executable"
chmod +x run.sh

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    log "Error: Python 3 is required but not installed"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    log "Creating virtual environment"
    python3 -m venv .venv
fi

# Activate virtual environment and install requirements
log "Activating virtual environment and installing requirements"
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Detect OS and set up service
if [[ "$OSTYPE" == "darwin"* ]]; then
    log "Setting up for macOS..."
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p ~/Library/LaunchAgents
    
    # Generate plist file with correct paths
    cat > com.user.dictation.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.dictation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/run.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/dictation.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/dictation.stderr.log</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
</dict>
</plist>
EOF
    
    # Copy plist file
    cp com.user.dictation.plist ~/Library/LaunchAgents/
    
    # Load the service
    log "Loading launchd service"
    launchctl unload ~/Library/LaunchAgents/com.user.dictation.plist 2>/dev/null || true
    launchctl load ~/Library/LaunchAgents/com.user.dictation.plist
    
    log "macOS setup complete!"
    log "To check status: launchctl list | grep com.user.dictation"
    log "Logs are available at: /tmp/dictation.stdout.log and /tmp/dictation.stderr.log"

elif [[ -f /etc/debian_version ]] || [[ -f /etc/linuxmint/info ]]; then
    log "Setting up for Linux Mint/Debian..."
    
    # Create user systemd directory
    mkdir -p ~/.config/systemd/user
    
    # Copy service file
    cp dictation.service ~/.config/systemd/user/
    
    # Set up autostart
    mkdir -p ~/.config/autostart
    cp dictation-autostart.desktop ~/.config/autostart/
    
    # Reload systemd and enable service
    log "Configuring systemd service"
    systemctl --user daemon-reload
    systemctl --user stop dictation.service 2>/dev/null || true
    systemctl --user enable dictation.service
    
    # Start the service
    log "Starting service"
    systemctl --user start dictation.service
    
    # Verify service started successfully
    sleep 2
    if ! systemctl --user is-active --quiet dictation.service; then
        log "Error: Service failed to start"
        systemctl --user status dictation.service
        exit 1
    fi
    
    log "Linux setup complete!"
    log "To check status: systemctl --user status dictation.service"
    log "To view logs: journalctl --user -u dictation.service"
    log "Service will automatically restart after login"

else
    log "Error: Unsupported operating system"
    exit 1
fi

log "Setup completed successfully!" 
#!/bin/bash

set -e  # Exit on error

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to set up uinput for Linux
setup_uinput() {
    log "Setting up uinput for Linux..."
    
    # Create uinput module loading configuration
    if [ ! -f "/etc/modules-load.d/uinput.conf" ]; then
        log "Creating uinput module configuration..."
        echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf
    fi
    
    # Create udev rule for uinput
    if [ ! -f "/etc/udev/rules.d/99-uinput.rules" ]; then
        log "Creating uinput udev rules..."
        echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' | sudo tee /etc/udev/rules.d/99-uinput.rules
    fi
    
    # Check if /dev/uinput exists and is writable by the current user
    USER_NEEDS_INPUT_GROUP=true
    if [ -c "/dev/uinput" ] && [ -w "/dev/uinput" ]; then
        log "/dev/uinput is already writable by user $USER. Skipping input group addition."
        USER_NEEDS_INPUT_GROUP=false
    elif [ ! -c "/dev/uinput" ]; then
         log "Warning: /dev/uinput device not found yet. Will attempt group addition."
    fi

    # Add user to input group only if needed and not already in it
    if [ "$USER_NEEDS_INPUT_GROUP" = true ] && ! groups $USER | grep -q "\binput\b"; then
        log "Adding user $USER to input group for /dev/uinput access..."
        sudo usermod -aG input $USER
        log "$(tput setaf 1)$(tput bold)IMPORTANT: You MUST log out and log back in for these group changes to take effect fully.$(tput sgr0)"
        # Set a flag to remind user at the end of setup
        REMIND_LOGOUT=true
    fi
    
    # Load uinput module immediately
    if ! lsmod | grep -q "^uinput"; then
        log "Loading uinput module..."
        sudo modprobe uinput
    fi
    
    # Reload udev rules
    log "Reloading udev rules..."
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    # Check if /dev/uinput exists and has correct permissions
    if [ -c "/dev/uinput" ]; then
        log "Checking /dev/uinput permissions..."
        UINPUT_PERMS=$(stat -c "%a" /dev/uinput)
        if [ "$UINPUT_PERMS" != "660" ]; then
            log "Setting correct permissions for /dev/uinput..."
            sudo chmod 660 /dev/uinput
        fi
    else
        log "Warning: /dev/uinput device not found. You may need to reboot your system."
    fi
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
    <false/>
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
    launchctl load -w ~/Library/LaunchAgents/com.user.dictation.plist
    
    log "macOS setup complete!"
    log "To check status: launchctl list | grep com.user.dictation"
    log "Logs are available at: /tmp/dictation.stdout.log and /tmp/dictation.stderr.log"

elif [[ -f /etc/debian_version ]] || [[ -f /etc/linuxmint/info ]]; then
    log "Setting up for Linux Mint/Debian..."
    
    # Set up uinput for Linux
    setup_uinput
    
    # Create user systemd directory
    mkdir -p ~/.config/systemd/user
    
    # Create service file with correct paths
    log "Creating systemd service file with correct paths..."
    sed -e "s|@@WORKING_DIR@@|$SCRIPT_DIR|g" \
        -e "s|@@EXEC_START@@|$SCRIPT_DIR/run.sh|g" \
        dictation.service > ~/.config/systemd/user/dictation.service
    
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
    
    # Remind about logging out if user was added to input group
    if [ "$REMIND_LOGOUT" = true ]; then
        log "$(tput setaf 1)$(tput bold)REMINDER: Please log out and log back in now to apply input group permissions for dictation typing to work correctly.$(tput sgr0)"
    fi

else
    log "Error: Unsupported operating system"
    exit 1
fi

log "Setup completed successfully!" 

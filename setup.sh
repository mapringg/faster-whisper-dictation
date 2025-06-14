#!/bin/bash

set -e  # Exit on error

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

setup_uinput_linux() {
    log "Setting up uinput for Linux..."
    if [ ! -f "/etc/modules-load.d/uinput.conf" ]; then
        log "Creating uinput module configuration..."
        echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf > /dev/null
    fi
    if [ ! -f "/etc/udev/rules.d/99-uinput.rules" ]; then
        log "Creating uinput udev rules..."
        echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' | sudo tee /etc/udev/rules.d/99-uinput.rules > /dev/null
    fi
    if ! groups "$USER" | grep -q "\binput\b"; then
        log "Adding user $USER to 'input' group for /dev/uinput access..."
        sudo usermod -aG input "$USER"
        log "$(tput setaf 1)$(tput bold)IMPORTANT: You MUST log out and log back in for group changes to take effect.$(tput sgr0)"
        export REMIND_LOGOUT=true
    fi
    if ! lsmod | grep -q "^uinput"; then
        log "Loading uinput module for current session..."
        sudo modprobe uinput
    fi
    log "Reloading udev rules..."
    sudo udevadm control --reload-rules
    sudo udevadm trigger
}

# Get absolute path of the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log "Making scripts executable..."
chmod +x run.sh

if ! command -v python3 &>/dev/null; then
    log "Error: Python 3 is required but not installed."
    exit 1
fi

if [ ! -d ".venv" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv .venv
fi

log "Activating virtual environment and installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip
# Install from pyproject.toml
pip install .

# OS-specific setup
if [[ "$OSTYPE" == "darwin"* ]]; then
    log "Setting up for macOS..."
    PLIST_PATH=~/Library/LaunchAgents/com.user.dictation.plist
    log "Creating launchd service file at $PLIST_PATH"
    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.dictation</string>
    <key>ProgramArguments</key>
    <array>
        <string>${SCRIPT_DIR}/run.sh</string>
    </array>
    <key>RunAtLoad</key>
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
    log "Loading launchd service..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load -w "$PLIST_PATH"
    log "macOS setup complete!"
    log "To check status: launchctl list | grep com.user.dictation"

elif [[ -f /etc/debian_version ]] || [[ -f /etc/linuxmint/info ]]; then
    log "Setting up for Linux (Debian/Ubuntu/Mint)..."
    if ! command -v xsel &> /dev/null; then
        log "$(tput setaf 1)Warning: 'xsel' not found. It's required for pasting text on X11.$(tput sgr0)"
        log "$(tput setaf 3)Install it with: sudo apt update && sudo apt install xsel$(tput sgr0)"
    fi
    setup_uinput_linux

    SERVICE_PATH=~/.config/systemd/user/dictation.service
    mkdir -p "$(dirname "$SERVICE_PATH")"
    log "Creating systemd service file at $SERVICE_PATH"
    sed -e "s|@@WORKING_DIR@@|$SCRIPT_DIR|g" \
        -e "s|@@EXEC_START@@|$SCRIPT_DIR/run.sh|g" \
        dictation.service > "$SERVICE_PATH"
    
    log "Configuring and starting systemd service..."
    systemctl --user daemon-reload
    systemctl --user enable --now dictation.service
    
    # Verify service started
    sleep 2
    if ! systemctl --user is-active --quiet dictation.service; then
        log "$(tput setaf 1)Error: Service failed to start. Check logs with: journalctl --user -u dictation.service -n 50$(tput sgr0)"
        exit 1
    fi
    log "Linux setup complete!"
    log "To check status: systemctl --user status dictation.service"
    if [ "$REMIND_LOGOUT" = true ]; then
        log "$(tput setaf 1)$(tput bold)REMINDER: Please log out and log back in to apply input group permissions.$(tput sgr0)"
    fi
else
    log "Error: Unsupported operating system."
    exit 1
fi

log "Setup completed successfully!"
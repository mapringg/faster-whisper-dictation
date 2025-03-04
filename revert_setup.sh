#!/bin/bash

echo "Reverting dictation service setup..."

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

echo "Reversion complete! All dictation service files have been removed."
echo "If you want to completely remove the application, you can delete this directory." 
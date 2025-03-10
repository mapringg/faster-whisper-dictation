# Faster Whisper Dictation

A lightweight dictation service that uses Groq's API for fast and accurate speech-to-text transcription. Double-tap a key to start recording, single-tap to stop, and your speech will be automatically transcribed and typed out.

## Requirements

- Python 3.8 or higher
- Linux (Debian/Ubuntu/Mint) or macOS
- A Groq API key (get one from [Groq's website](https://console.groq.com))

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/faster-whisper-dictation.git
   cd faster-whisper-dictation
   ```

2. Create a `.env` file in your home directory with your Groq API key:

   ```bash
   echo "GROQ_API_KEY=your_api_key_here" > ~/.env
   ```

3. Run the setup script:
   ```bash
   ./setup.sh
   ```

The setup script will:

- Create a Python virtual environment
- Install required dependencies
- Set up the service to start automatically at login
- Start the service

## Usage

By default, the Left Alt key is used as the trigger:

- **Double-tap** Left Alt to start recording
- **Single-tap** Left Alt to stop recording

Your speech will be automatically transcribed and typed at the current cursor position.

To change the trigger key, stop the service and restart it with the `-d` option:

```bash
# For Linux:
systemctl --user stop dictation.service
./run.sh -d "<ctrl_l>"  # Use left Control instead

# For macOS:
launchctl unload ~/Library/LaunchAgents/com.user.dictation.plist
./run.sh -d "<ctrl_l>"  # Use left Control instead
```

## Options

```
-d, --trigger-key    Key to use for triggering recording (default: <alt_l>)
-t, --max-time      Maximum recording time in seconds (default: 30)
-l, --language      Specify language for better accuracy (e.g., 'en' for English)
-m, --model-name    Groq model to use (default: whisper-large-v3)
```

## Service Management

### Linux

```bash
# Check service status
systemctl --user status dictation.service

# View logs
journalctl --user -u dictation.service

# Restart service
systemctl --user restart dictation.service
```

### macOS

```bash
# Check service status
launchctl list | grep com.user.dictation

# View logs
cat /tmp/dictation.stdout.log
cat /tmp/dictation.stderr.log

# Restart service
launchctl unload ~/Library/LaunchAgents/com.user.dictation.plist
launchctl load ~/Library/LaunchAgents/com.user.dictation.plist
```

## Troubleshooting

1. If the service isn't starting:

   - Check the logs (see above)
   - Ensure your Groq API key is set in `~/.env`
   - Verify Python and required packages are installed

2. If recording isn't working:

   - Check your microphone permissions
   - Verify your default audio input device is set correctly

3. If the service needs to be restarted:

   ```bash
   # Linux
   systemctl --user restart dictation.service

   # macOS
   launchctl unload ~/Library/LaunchAgents/com.user.dictation.plist
   launchctl load ~/Library/LaunchAgents/com.user.dictation.plist
   ```

## Uninstallation

To remove the service:

```bash
./revert_setup.sh
```

## License

MIT License - See LICENSE file for details

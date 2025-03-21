# Faster Whisper Dictation

A lightweight dictation service that uses OpenAI's API (default) or Groq's API for fast and accurate speech-to-text transcription. Double-tap a key to start recording, single-tap to stop, and your speech will be automatically transcribed and typed out.

## Requirements

- Python 3.8 or higher
- Linux (Debian/Ubuntu/Mint) or macOS
- PortAudio (required for audio input)
  - macOS: `brew install portaudio`
  - Debian/Ubuntu/Mint: `sudo apt-get install portaudio19-dev`
- Python packages: faster-whisper, sounddevice, soundfile, pynput, transitions, requests, numpy

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/faster-whisper-dictation.git
   cd faster-whisper-dictation
   ```

2. Set up your API keys:
   Create a `.env` file in your home directory with your API keys:

   ```bash
   # Required for OpenAI (default transcriber)
   OPENAI_API_KEY=your_openai_api_key_here
   # Required only if using Groq transcriber
   GROQ_API_KEY=your_groq_api_key_here
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

On macOS:

- **Double-tap** Right Command to start recording
- **Single-tap** Right Command to stop recording
- **Double-tap** Right Option to cancel recording

On Linux:

- **Double-tap** Right Control to start recording
- **Single-tap** Right Control to stop recording
- **Double-tap** Right Alt to cancel recording

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
-d, --trigger-key    Key to use for triggering recording (default: Key.cmd_r)
-t, --max-time      Maximum recording time in seconds (default: 30)
-l, --language      Specify language for better accuracy (e.g., 'en' for English)
-m, --model-name    Model to use (default: gpt-4o-transcribe for OpenAI, whisper-large-v3 for Groq)
--transcriber       Transcription service to use: 'openai' (default) or 'groq'
--enable-sounds     Enable sound effects for recording actions
```

## Service Management

### Linux (systemd)

```bash
# Check service status
systemctl --user status dictation.service

# View logs
journalctl --user -u dictation.service

# Restart service
systemctl --user restart dictation.service
```

### Linux (Desktop Environments)

For desktop environments like GNOME, KDE, or XFCE, the application will automatically start on login using the `dictation-autostart.desktop` file.

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

## Code Structure

The project is organized as follows:

- `src/`: Contains the main application code
  - `cli.py`: Handles command-line argument parsing
  - `core/`: Contains the core application logic
  - `services/`: Contains modules for input handling, recording, and transcription

## Troubleshooting

1. If the service isn't starting:

   - Check the logs (see above)
   - Ensure your API keys are set in `~/.env`
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

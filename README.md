# Faster Whisper Dictation with Groq API

This is a modified version of the original Faster Whisper Dictation tool that uses the Groq API for speech transcription instead of local Whisper models.

## Setup

1. Install the required dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Set up your Groq API key in one of the following ways:

   **Option 1:** Set as an environment variable:

   ```
   export GROQ_API_KEY="your_groq_api_key_here"
   ```

   On Windows, use:

   ```
   set GROQ_API_KEY=your_groq_api_key_here
   ```

   **Option 2:** Create a `.env` file in your home directory:

   ```
   # On macOS/Linux
   echo "GROQ_API_KEY=your_groq_api_key_here" > ~/.env

   # On Windows
   echo GROQ_API_KEY=your_groq_api_key_here > %USERPROFILE%\.env
   ```

3. (Optional) Set up automatic startup:

   Run the setup script to configure the service to start automatically on system boot:

   ```bash
   ./setup.sh
   ```

   This script automatically detects your operating system and configures the appropriate startup method:

   **On macOS:**

   - Creates a LaunchAgent in `~/Library/LaunchAgents/`
   - Loads the service to start immediately and on future logins

   **On Linux (Debian/Linux Mint):**

   - Creates a user systemd service in `~/.config/systemd/user/`
   - Adds an autostart entry to ensure proper startup
   - Enables and starts the service

## Usage

Run the dictation tool:

```
python dictation.py
```

Or use the provided shell script (on macOS/Linux):

```
./run.sh
```

### Command Line Options

- `-m, --model-name`: Specify the Groq model to use (default: "whisper-large-v3-turbo")
- `-k, --key-combo`: Specify the key combination to toggle recording
- `-d, --double-key`: Specify a key for double-tap activation
- `-t, --max-time`: Maximum recording time in seconds (default: 30)
- `-l, --language`: Specify the language for better transcription accuracy

### Default Key Combinations

- Windows: Win+Z
- macOS/Linux: Double-tap Left Alt

## How It Works

1. Press the hotkey to start recording
2. Speak into your microphone
3. Press the hotkey again to stop recording
4. The audio will be transcribed using the Groq API
5. The transcribed text will be typed out at your cursor position

## Service Management

### Checking Service Status

**On macOS:**

```
launchctl list | grep com.user.dictation
```

View logs at: `/tmp/dictation.stdout.log` and `/tmp/dictation.stderr.log`

**On Linux:**

```
systemctl --user status dictation.service
```

View logs with: `journalctl --user -u dictation.service`

### Managing the Service

**On macOS:**

```
# Stop the service
launchctl unload ~/Library/LaunchAgents/com.user.dictation.plist

# Start the service
launchctl load ~/Library/LaunchAgents/com.user.dictation.plist
```

**On Linux:**

```
# Start the service
systemctl --user start dictation.service

# Stop the service
systemctl --user stop dictation.service

# Restart the service
systemctl --user restart dictation.service
```

### Reverting Setup

If you need to remove the service completely, run:

```
./revert_setup.sh
```

This script will:

**On macOS:**

- Unload the LaunchAgent service
- Remove the plist file from ~/Library/LaunchAgents/

**On Linux:**

- Stop and disable the user systemd service
- Remove service files
- Remove autostart entries
- Clean up any system-level service files if they exist

## Troubleshooting

- **API Key Issues:** If you get an error about the GROQ_API_KEY not being set, make sure you've set the environment variable correctly or added it to your `~/.env` file
- **Transcription Failures:** Check your internet connection and verify your Groq API key is valid
- **Microphone Problems:** Ensure your microphone permissions are properly set up for your operating system
- **Service Not Starting:**
  - Check the logs for error messages
  - Ensure your Groq API key is properly set in `~/.env`
  - Verify that the paths in the service configuration match your installation
  - Try running `run.sh` manually to verify it works outside the service

## Differences from Original Version

This version uses the Groq API for transcription instead of running Whisper models locally. This means:

1. You need an internet connection
2. You need a Groq API key
3. Transcription may be faster or slower depending on your internet connection and Groq API response times
4. All other functionality remains the same as the original version

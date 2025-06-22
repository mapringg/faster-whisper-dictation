# Faster Whisper Dictation

A lightweight, key-activated dictation service that uses local or cloud-based transcription for fast and accurate speech-to-text. Double-press a key to start recording, single-press to stop, and your speech is automatically typed out.

This service supports OpenAI, Groq, and local `faster-whisper` models.

## Requirements

- Python 3.8+
- **macOS** or **Linux** (Debian/Ubuntu/Mint)
- **Audio Dependencies**:
  - macOS: `brew install portaudio`
  - Linux: `sudo apt-get install portaudio19-dev`
- **Linux-specific clipboard tool**:
  - `xsel` is required for clipboard functionality on X11. The setup script will warn if it's missing.
  - `sudo apt install xsel`

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/doctorguile/faster-whisper-dictation.git
    cd faster-whisper-dictation
    ```

2.  **Set up API Keys (Optional):**
    If you plan to use OpenAI or Groq, create a `.env` file in the project directory or your home directory (`~/.env`):
    ```ini
    # Required for OpenAI transcriber
    OPENAI_API_KEY="your_openai_api_key"

    # Required for Groq transcriber
    GROQ_API_KEY="your_groq_api_key"
    ```

3.  **Run the setup script:**
    ```bash
    ./setup.sh
    ```
    This script will:
    - Create a Python virtual environment (`.venv`).
    - Install all required dependencies from `pyproject.toml`.
    - Set up the service to start automatically at login (`launchd` on macOS, `systemd` on Linux).
    - On Linux, it will configure `/dev/uinput` permissions. **You must log out and log back in** if prompted to apply group changes.

## Usage

The application runs as a background service with a status icon in the system tray.

### Default Hotkeys

| Action               | macOS Hotkey          | Linux Hotkey    |
| -------------------- | --------------------- | --------------- |
| **Start Recording**  | Double-press `Right ⌘` | Double-press `Ctrl` (either side) |
| **Stop Recording**   | Single-press `Right ⌘` | Single-press `Ctrl` (either side) |
| **Cancel Recording** | Double-press `Right ⌥` | Double-press `Alt` (either side)  |

Your speech is automatically transcribed, copied to the clipboard, and pasted at your cursor's current position.

### Status Icon Menu

Right-click the status icon for options:
- **Transcriber**: Switch between OpenAI, Groq, and Local models.
- **Language**: Select the language for transcription.
- **Enable/Disable Sounds**: Toggle audio feedback for actions.
- **Refresh Audio Devices**: Rescan for new audio hardware.
- **Exit**: Shut down the service.

## Command-Line Options

You can customize the behavior by passing arguments to `run.sh`. To make these changes permanent, you'll need to edit the service file (`dictation.service` or `com.user.dictation.plist`) and reinstall the service.

Example:
```bash
# Run with a different trigger key and the local transcriber
./run.sh --trigger-key "<cmd>+<shift>+d" --transcriber local
```

**Key Options:**
- `--transcriber`: `openai`, `groq`, or `local` (default: `openai`).
- `-m, --model-name`: Specify a model (e.g., `tiny.en` for local).
- `-d, --trigger-key`: Set a new trigger key using `pynput` format.
- `-l, --language`: Set transcription language (e.g., `fr`).
- `--enable-sounds`: Enable audio feedback.
- `--no-vad`: Disable Voice Activity Detection.

## Service Management

### Linux (systemd)
```bash
# Check status
systemctl --user status dictation.service

# View logs
journalctl --user -u dictation.service -f

# Restart service
systemctl --user restart dictation.service
```

### macOS (launchd)
```bash
# Check status
launchctl list | grep com.user.dictation

# View logs
tail -f /tmp/dictation.stdout.log

# Restart service
launchctl kickstart -k gui/$(id -u)/com.user.dictation
```

## Uninstallation
To remove the service and auto-start configurations, run:
```bash
./revert_setup.sh
```

## License
This project is licensed under the MIT License.
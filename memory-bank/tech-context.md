# Tech Context

- **Primary Language(s):** Python
- **Frameworks/Libraries:** sounddevice, soundfile, pynput (macOS keyboard control), transitions, requests, numpy, pystray, Pillow, python-uinput (Linux keyboard control). (Note: `faster-whisper` library is no longer a direct dependency as local transcription was removed).
- **Databases:** N/A
- **Key Dependencies:**
  - Python 3.8+
  - PortAudio (`portaudio19-dev` on Debian/Ubuntu, `portaudio` via brew on macOS) - For audio recording.
  - Cloud Transcription APIs: Groq API / OpenAI API (depending on selected transcriber). Requires respective API keys.
  - **Linux Specific:**
    - `xsel`: External command-line utility required for clipboard copy functionality. Must be installed via system package manager (e.g., `sudo apt install xsel`).
    - `python-uinput`: Python library for interacting with the kernel's uinput module (installed via pip).
    - `/dev/uinput` kernel module access: Requires user to be in the `input` group for keyboard simulation. `setup.sh` handles configuration.
  - **macOS Specific:**
    - `pynput`: Python library used for keyboard simulation (installed via pip).
    - Accessibility permissions may be required for keyboard control.
- **Development Setup:**
  - Requires Python environment.
  - API keys (GROQ_API_KEY or OPENAI_API_KEY) are needed for transcription.
  - **Environment Variable Loading:** Configuration (like API keys) is loaded with the following priority:
    1. Shell Environment Variables (Highest)
    2. Project `.env` file (`./.env`)
    3. Home `.env` file (`$HOME/.env`) (Lowest)
       Loading is handled in `src/core/utils.py::load_env_from_file`, called by `src/services/transcriber.py` and potentially `src/core/app.py`. The `run.sh` script also sources these files directly for environment setup before launching the Python app.
- **Build/Deployment Process:**
  - Primarily script-based installation using `setup.sh`.
  - `setup.sh` creates a virtual environment, installs dependencies (`requirements.txt` and potentially `pyproject.toml`), configures systemd (Linux) or launchd (macOS) services for auto-start, and handles Linux permissions (`/dev/uinput`, `input` group).
  - `revert_setup.sh` handles uninstallation (removes service files, etc.).
  - Uses `pyproject.toml` which could support standard packaging, but scripts are the main method.
- **Technical Constraints:**
  - **OS:** Linux (Debian/Ubuntu/Mint tested) and macOS. Windows is not supported.
  - **Permissions:** Requires specific permissions for audio input (microphone) and keyboard simulation (`/dev/uinput` access and `input` group membership on Linux; Accessibility permissions on macOS).
  - **Dependencies:** Relies on external APIs (OpenAI/Groq) requiring valid keys and internet connectivity for transcription. Requires `xsel` command on Linux for core functionality.
  - **Performance:** User experience goal is fast, near real-time transcription. API latency is a factor. Clipboard operations (`pbcopy`/`xsel`) are generally fast.
- **Tooling:**
  - **pre-commit:** Used for code quality checks before commits (configured in `.pre-commit-config.yaml`). Specific tools likely include linters (e.g., flake8, ruff) and formatters (e.g., black, isort).
  - **Virtual Environments:** Managed by `setup.sh` (likely using `venv`).
  - **Dependency Management:** `requirements.txt` (primary) and `pyproject.toml` (potentially for build/dev dependencies). Dev dependencies (`psutil`, `matplotlib`) installable via `pip install -e .[dev]`.

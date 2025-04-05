# Technical Context

## 1. Technologies & Core Libraries

- **Primary Language:** Python 3
- **State Management:** `transitions` library (`src/core/state_machine.py`)
- **Audio Handling:** `sounddevice` library (`src/services/recorder.py`)
- **System Tray:** `pystray` library (`src/services/status_indicator.py`)
- **Cloud Transcription APIs:** OpenAI API, Groq API (`src/services/transcriber.py`)
- **Keyboard Simulation:**
  - **Linux:** `python-uinput` library (`src/services/uinput_controller.py`) interacting with kernel's `/dev/uinput`.
  - **macOS:** `pynput` library (`src/services/keyboard_controller_factory.py` likely uses it).
- **Clipboard Interaction:**
  - **Linux:** `xsel` command-line utility (invoked via `subprocess`).
  - **macOS:** `pbcopy` command-line utility (invoked via `subprocess`).

## 2. Development Environment & Setup

- **Package Management:** `pip` with `requirements.txt`. (Potentially `mise` based on `mise.toml`, though not explicitly detailed in previous context).
- **Virtual Environment:** Recommended (managed by `setup.sh`).
- **Installation:**
  - Uses `setup.sh` script for:
    - Installing Python dependencies (`pip install -r requirements.txt`).
    - Creating a virtual environment (implied).
    - Checking for required system dependencies (`xsel` on Linux - warns only).
    - Adding user to the `input` group on Linux (requires logout/login).
    - Setting up system services (systemd for Linux, launchd for macOS) for auto-start.
  - Uses `revert_setup.sh` for uninstallation/reverting setup steps.
- **Configuration (API Keys):**
  - Loaded via environment variables.
  - Priority Order: Shell Environment Variables > Project `.env` file (`./.env`) > Home `.env` file (`~/.env`).
  - Handled by `src/core/utils.py::load_env_from_file` and respected in `run.sh`.

## 3. Technical Constraints & Dependencies

- **Operating Systems:** Linux (Debian/Ubuntu/Mint focus) and macOS. Windows is explicitly **not** supported.
- **Internet Connection:** Required for cloud transcription API calls (OpenAI/Groq).
- **API Keys:** Valid OpenAI or Groq API keys are necessary and must be configured via environment variables or `.env` files.
- **System Dependencies:**
  - **Linux:** `xsel` command-line utility must be installed.
- **Permissions:**
  - **Microphone Access:** Required on both OSes.
  - **Keyboard Simulation:**
    - **Linux:** User must be part of the `input` group and have appropriate permissions for `/dev/uinput`. `setup.sh` attempts to manage group membership.
    - **macOS:** Requires Accessibility permissions granted to the terminal or application running the script.

## 4. Tool Usage Patterns

- **Code Quality:** `pre-commit` framework (`.pre-commit-config.yaml`) is used to enforce standards before commits.
  - **Formatter:** `black`
  - **Linter:** `flake8` (implied, common hook)
  - **Import Sorting:** `isort` (implied, common hook)
- **Execution:** The application is typically run via `run.sh` or as a system service configured by `setup.sh`.

## 5. Excluded Technologies

- **Local Transcription:** Support for local `faster-whisper` models was explicitly removed to focus on cloud APIs.

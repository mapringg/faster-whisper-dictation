# System Patterns

- **Architecture Overview:**
  The application operates as an event-driven background service coordinated by the `App` class (`src/core/app.py`). It utilizes a state machine (`src/core/state_machine.py`) to manage its lifecycle (Ready, Recording, Transcribing, Replaying/Typing). User interaction is primarily through keyboard shortcuts detected by `DoubleKeyListener` (`src/services/input_handler.py`) and a system tray icon (`src/services/status_indicator.py`) for status and basic settings.

  ```mermaid
  flowchart TD
      subgraph User Interaction
          direction LR
          KB[Keyboard Shortcuts] --> DKL[DoubleKeyListener]
          Tray[System Tray Icon] --> SI[StatusIcon]
      end

      subgraph Core Logic
          direction TB
          App[App Coordinator] -- Manages --> SM[State Machine]
          App -- Uses --> REC[Recorder]
          App -- Uses --> TRX[Transcriber Strategy]
          App -- Uses --> KBR[KeyboardReplayer]
          App -- Updates --> SI
          App -- Receives Config --> SI
      end

      subgraph Services
          direction TB
          REC[Recorder] --> SD[sounddevice]
          TRX[Transcriber Strategy] --> |OpenAI| OpenAI_API[OpenAI API]
          TRX[Transcriber Strategy] --> |Groq| Groq_API[Groq API]
          KBR[KeyboardReplayer] -- Uses --> KCF[Keyboard Controller Factory]
          KCF --> |Linux| UIC[UInputController]
          KCF --> |macOS| PNP[pynput Controller]
          SI --> PSTRAY[pystray]
      end

      DKL -- Triggers State Change --> App
      SM -- Dictates --> App -- Behavior --> App
      App -- Start/Stop --> REC
      REC -- Audio Data --> App -- Pass To --> TRX
      TRX -- Text Segments --> App -- Pass To --> KBR
      KBR -- Copy & Paste --> KCF
      App -- Updates State --> SI

      style App fill:#f9f,stroke:#333,stroke-width:2px
      style SM fill:#ccf,stroke:#333,stroke-width:1px
      style DKL fill:#lightgreen,stroke:#333,stroke-width:1px
      style SI fill:#lightgreen,stroke:#333,stroke-width:1px
      style REC fill:#lightblue,stroke:#333,stroke-width:1px
      style TRX fill:#lightblue,stroke:#333,stroke-width:1px
      style KBR fill:#lightblue,stroke:#333,stroke-width:1px
      style KCF fill:#lightblue,stroke:#333,stroke-width:1px
  ```

- **Key Technical Decisions & Architectural Patterns:**

  - **State Machine:** Using the `transitions` library (`src/core/state_machine.py`) to manage application states (Ready, Recording, Transcribing, Replaying) ensures predictable behavior and simplifies handling different stages. (State Pattern)
  - **API Abstraction (Cloud Only):** Using a `BaseTranscriber` class (`src/services/transcriber.py`) with specific cloud implementations (OpenAI, Groq) allows swapping cloud providers. Local transcription is explicitly excluded. (Strategy Pattern)
  - **OS-Specific Keyboard Control:** Employing a factory (`src/services/keyboard_controller_factory.py`) to provide the appropriate keyboard simulation mechanism (`python-uinput` for Linux, `pynput` for macOS) isolates platform dependencies. (Factory Pattern - Decision: Specific libraries chosen for OS compatibility).
  - **Clipboard Utility (Linux):** Explicitly switched from `xclip` to `xsel` via `subprocess` calls to address persistent copy delays encountered with `xclip`. (Decision: Driven by debugging platform-specific issues).
  - **Environment Variable Configuration:** Centralizing configuration loading (API keys) via environment variables with a clear priority (Shell > Project > Home) provides flexibility (`src/core/utils.py::load_env_from_file`, `run.sh`). (Decision: Support project-level overrides).
  - **System Tray Icon:** Using `pystray` for a status indicator provides visual feedback and a simple interface for runtime adjustments (language, transcriber) without a full GUI. (Implicit Observer Pattern)
  - **Script-Based Installation:** Utilizing `setup.sh` and `revert_setup.sh` provides a consistent mechanism for dependency installation, virtual environment creation, service configuration (systemd/launchd), and permission handling across supported OS. (Decision: Adopted for simpler user setup).
  - **Automated Code Quality:** Employing `pre-commit` hooks (configured in `.pre-commit-config.yaml`) enforces code style and quality standards (e.g., formatting, linting) before commits, contributing to maintainability. (Decision: Implemented for code consistency).

- **Other Design Patterns:**

  - **Callback Pattern:** Used extensively for communication between components (e.g., `Recorder` -> `App`, `Transcriber` -> `App`, `StatusIcon` -> `App`).
  - **Context Manager:** Used in `Recorder` (`_stream_context`, `_recording_state`) for resource management.

- **Component Relationships:**

  - `main.py` (entry point) parses arguments using `src/cli.py` and instantiates/runs `src/core/app.py::App`.
  - `App` orchestrates the main workflow, holding instances of key services (`DoubleKeyListener`, `Recorder`, `Transcriber`, `KeyboardReplayer`, `StatusIcon`).
  - `DoubleKeyListener` listens for keyboard events and triggers state transitions in `App`.
  - `Recorder` captures audio when instructed by `App`.
  - `Transcriber` processes audio data (received via `App` callback) and sends text results back (via `App` callback).
  - `KeyboardReplayer` receives text from `App`, copies it to the system clipboard (`pbcopy` on macOS, `xsel --clipboard --input` on Linux), and then uses the OS-specific controller (via factory) to simulate a paste command (Cmd+V or Ctrl+V).
  - `StatusIcon` runs (potentially in a separate thread) to display status based on `App` state changes and sends user configuration requests back to `App` via callbacks.
  - `src/core/utils.py` provides common utilities used by various components (env loading, sound playback).

- **Critical Implementation Paths:**
  - **Recording Trigger Flow:** `DoubleKeyListener.on_press` -> `App._safe_start_recording` -> `App` state change to `RECORDING` -> `Recorder.start`.
  - **Transcription Flow:** `Recorder` completes -> Callback to `App` -> `App._safe_start_transcription` -> `App` state change to `TRANSCRIBING` -> `Transcriber.transcribe` -> API call -> Callback to `App`.
  - **Output Flow (Copy & Paste):** `Transcriber` callback to `App` -> `App._safe_start_replay` -> `App` state change to `REPLAYING` -> `KeyboardReplayer.replay` -> (Copies text via `pbcopy` on macOS / `xsel --clipboard --input` on Linux) -> (Simulates paste via OS-specific `KeyboardController` - `pynput`/`python-uinput`).
  - **Configuration Loading:** `App` initialization and `run.sh` both utilize `load_env_from_file` logic to ensure consistent API key access based on defined priority.
  - **System Tray Interaction:** User clicks menu item in `StatusIcon` -> Callback (`_select_language`, `_toggle_sounds`, etc.) -> Calls registered callback in `App` (`_change_language`, `_toggle_sounds`).

_[YYYY-MM-DD HH:MM:SS] - Added script-based installation and pre-commit usage to Key Technical Decisions._

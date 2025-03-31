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
      KBR -- Type Chars --> KCF
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

- **Key Technical Decisions:**

  - **State Machine:** Using the `transitions` library (`src/core/state_machine.py`) to manage application states ensures predictable behavior and simplifies handling different stages (ready, recording, etc.).
  - **API Abstraction (Cloud Only):** Using a `BaseTranscriber` class (`src/services/transcriber.py`) with specific cloud implementations (OpenAI, Groq) allows swapping cloud providers via a Strategy pattern. Local transcription is explicitly excluded.
  - **OS-Specific Keyboard Control:** Employing a factory (`src/services/keyboard_controller_factory.py`) to provide the appropriate keyboard simulation mechanism (`uinput` for Linux, `pynput` likely for macOS) isolates platform dependencies.
  - **Environment Variable Configuration:** Centralizing configuration loading (API keys) via environment variables with a clear priority (Shell > Project > Home) provides flexibility (`src/core/utils.py::load_env_from_file`, `run.sh`).
  - **System Tray Icon:** Using `pystray` for a status indicator provides visual feedback and a simple interface for runtime adjustments (language, transcriber) without a full GUI.

- **Design Patterns:**

  - **State Pattern:** Core application flow managed by `App` and `state_machine.py`.
  - **Strategy Pattern:** `BaseTranscriber` with `OpenAITranscriber` and `GroqTranscriber` implementations for cloud API interaction.
  - **Factory Pattern:** `keyboard_controller_factory.py` for OS-specific keyboard controllers.
  - **Callback Pattern:** Used extensively for communication between components (e.g., `Recorder` -> `App`, `Transcriber` -> `App`, `StatusIcon` -> `App`).
  - **Observer Pattern (Implicit):** `StatusIcon` observes the state managed by `App`.
  - **Context Manager:** Used in `Recorder` (`_stream_context`, `_recording_state`) for resource management.

- **Component Relationships:**

  - `main.py` (entry point) likely parses arguments using `src/cli.py` and instantiates/runs `src/core/app.py::App`.
  - `App` orchestrates the main workflow, holding instances of key services (`DoubleKeyListener`, `Recorder`, `Transcriber`, `KeyboardReplayer`, `StatusIcon`).
  - `DoubleKeyListener` listens for keyboard events and triggers state transitions in `App`.
  - `Recorder` captures audio when instructed by `App`.
  - `Transcriber` processes audio data (received via `App` callback) and sends text results back (via `App` callback).
  - `KeyboardReplayer` receives text from `App` and uses the OS-specific controller (via factory) to type it.
  - `StatusIcon` runs (potentially in a separate thread) to display status based on `App` state changes and sends user configuration requests back to `App` via callbacks.
  - `src/core/utils.py` provides common utilities used by various components (env loading, sound playback).

- **Critical Implementation Paths:**
  - **Recording Trigger Flow:** `DoubleKeyListener.on_press` -> `App._safe_start_recording` -> `App` state change to `RECORDING` -> `Recorder.start`.
  - **Transcription Flow:** `Recorder` completes -> Callback to `App` -> `App._safe_start_transcription` -> `App` state change to `TRANSCRIBING` -> `Transcriber.transcribe` -> API call -> Callback to `App`.
  - **Typing Flow:** `Transcriber` callback to `App` -> `App._safe_start_replay` -> `App` state change to `REPLAYING` -> `KeyboardReplayer.replay` -> `KeyboardController.type`.
  - **Configuration Loading:** `App` initialization and `run.sh` both utilize `load_env_from_file` logic to ensure consistent API key access based on defined priority.
  - **System Tray Interaction:** User clicks menu item in `StatusIcon` -> Callback (`_select_language`, `_toggle_sounds`, etc.) -> Calls registered callback in `App` (`_change_language`, `_toggle_sounds`).

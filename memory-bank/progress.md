# Progress

- **Current Status:** Initial population of Memory Bank documentation based on codebase analysis.
- **What Works:**
  - Environment variables can now be loaded from `$HOME/.env` and `./.env` by both the Python application (`src/services/transcriber.py`) and the startup script (`run.sh`).
  - Loading priority is correctly established and consistent: Shell > Project (`./.env`) > Home (`$HOME/.env`).
  - Transcription service initialization (`BaseTranscriber`) respects this priority.
  - The `run.sh` script correctly sources environment variables before checking for required API keys and launching the application.
  - Text output on Linux now uses `xsel` (switched from `xclip`) to copy to clipboard and `uinput` to simulate Ctrl+V paste, mirroring the macOS `pbcopy`/Cmd+V behavior.
- **What's Left to Build:** (To be defined)
- **Known Issues/Bugs:**
  - Linux functionality depends on `xsel` being installed. `setup.sh` warns but does not install it.
  - Linux keyboard simulation requires user to be in `input` group and potentially logout/login after setup.
  - **Reported (Debugging in Progress):** Previous attempts using `xclip` resulted in long delays before copy completion, even when using `Popen.communicate()`. Paste simulation reliability also needed improvement (addressed with minor delays in `uinput` controller). Currently testing `xsel` as an alternative to `xclip`.
- **Decision Log:**
  - [Date - Prior to Memory Bank creation]: Removed local `faster-whisper` transcription support. - Rationale: Focus exclusively on cloud APIs (OpenAI/Groq) for improved transcription accuracy and speed, simplifying the codebase and dependencies. This involved removing local model loading and processing logic.
  - [Date]: Implemented project-level `.env` support. - Rationale: Allow project-specific configuration overrides while maintaining global defaults and respecting shell environment variables. Modified `src/services/transcriber.py` and `run.sh`.
  - [Date - Current]: Aligned Linux text output with macOS. - Rationale: Replace character-by-character typing on Linux with a copy (`xclip`) and paste (Ctrl+V via `uinput`) mechanism for consistency with macOS (`pbcopy`/Cmd+V) and potential speed improvements. Modified `src/services/input_handler.py`, `src/services/uinput_controller.py`, `setup.sh`, and documentation.
  - [Date - Current Debugging - Attempt 1]: Attempted to fix Linux copy-paste issues (with `xclip`). - Rationale: Address reported `xclip` delay and paste unreliability. Switched `xclip` call from `subprocess.run` to `subprocess.Popen` with `communicate()`. Added small delays to `uinput` key press/release events. Modified `src/services/input_handler.py` and `src/services/uinput_controller.py`. Result: Paste worked, but `xclip` delay persisted.
  - [Date - Current Debugging - Attempt 2]: Switched Linux clipboard utility from `xclip` to `xsel`. - Rationale: Investigate if the persistent copy delay was specific to `xclip` interaction. Modified `setup.sh`, `README.md`, `memory-bank/tech-context.md`, `memory-bank/system-patterns.md`, and `src/services/input_handler.py`.

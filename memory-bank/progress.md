# Progress

- **Current Status:** Initial population of Memory Bank documentation based on codebase analysis.
- **What Works:**
  - Environment variables can now be loaded from `$HOME/.env` and `./.env` by both the Python application (`src/services/transcriber.py`) and the startup script (`run.sh`).
  - Loading priority is correctly established and consistent: Shell > Project (`./.env`) > Home (`$HOME/.env`).
  - Transcription service initialization (`BaseTranscriber`) respects this priority.
  - The `run.sh` script correctly sources environment variables before checking for required API keys and launching the application.
- **What's Left to Build:** (To be defined)
- **Known Issues/Bugs:** (None identified during initial documentation)
- **Decision Log:**
  - [Date - Prior to Memory Bank creation]: Removed local `faster-whisper` transcription support. - Rationale: Focus exclusively on cloud APIs (OpenAI/Groq) for improved transcription accuracy and speed, simplifying the codebase and dependencies. This involved removing local model loading and processing logic.
  - [Date]: Implemented project-level `.env` support. - Rationale: Allow project-specific configuration overrides while maintaining global defaults and respecting shell environment variables. Modified `src/services/transcriber.py` and `run.sh`.

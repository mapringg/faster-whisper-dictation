# Project Brief

- **Project Name:** Faster Whisper Dictation
- **Core Goal:** Provide a lightweight, fast, and accurate dictation service using OpenAI or Groq APIs for transcription, triggered by keyboard shortcuts, that types the transcribed text automatically.
- **Key Requirements:**
  - Transcribe speech to text _exclusively_ using cloud APIs: OpenAI (default) or Groq. (Note: Local transcription using faster-whisper was removed).
  - Trigger recording via configurable keyboard shortcuts (double-tap start, single-tap stop, double-tap cancel).
  - Automatically type transcribed text at the current cursor position.
  - Support Linux (Debian/Ubuntu/Mint focus) and macOS.
  - Allow configuration via command-line options (trigger key, max time, language, model, transcriber choice, sound effects).
  - Load API keys and potentially other settings via environment variables with a defined priority (Shell > Project `.env` > Home `.env`).
  - Provide a setup script (`setup.sh`) for easy installation (dependencies, virtual environment, service configuration).
  - Provide an uninstallation script (`revert_setup.sh`).
  - Run as a background service, automatically starting on login.
- **Scope:** A background service focused on keyboard-triggered dictation and cloud-based transcription (OpenAI/Groq), typing results into any active application. It does _not_ include local model transcription, complex voice commands, GUI configuration, or application-specific integrations beyond simulating keyboard input.
- **Stakeholders:** Primarily the developer(s) and end-users who want efficient, high-quality cloud-based dictation.

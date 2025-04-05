# Project Brief: Faster Whisper Dictation

## 1. Core Problem & Goal

**Problem:** Users need a fast, accurate, and seamless way to dictate text into any application on Linux and macOS without workflow interruption. Existing methods might be slow (character-by-character typing) or lack the accuracy of modern cloud transcription.

**Core Goal:** To provide a lightweight background dictation service that leverages high-performance cloud transcription APIs (OpenAI/Groq) for superior accuracy and speed, outputting the text via a quick copy-paste mechanism into the user's active application.

## 2. Target Users

Individuals who frequently type and value transcription speed and accuracy, such as developers, writers, students, and professionals using Linux or macOS.

## 3. Core Requirements & Scope

### Functional Requirements:

- **Cloud Transcription:** Exclusively use OpenAI or Groq APIs for transcription.
- **Keyboard Triggers:** Use configurable keyboard shortcuts for start/stop/cancel actions.
- **Clipboard & Paste Output:** Copy transcription result to clipboard and simulate paste (Cmd+V/Ctrl+V).
- **OS Support:** Linux (Debian/Ubuntu/Mint focus) and macOS.
- **Configuration:** Allow CLI options for trigger key, timing, language, model, transcriber choice, sound effects.
- **API Key Management:** Load keys via environment variables (Shell > Project `.env` > Home `.env`).
- **Background Operation:** Run as a system service (systemd/launchd) starting automatically on login.
- **Installation:** Provide `setup.sh` for setup and `revert_setup.sh` for removal.
- **Feedback:** Optional sound effects for state changes.

### Non-Functional Requirements:

- **Performance:** Fast, near real-time transcription and responsiveness.
- **Usability:** Seamless integration, simple setup, intuitive shortcuts.
- **Reliability:** Consistent background operation, robust error handling.

### Scope:

- **In Scope:** Background service, keyboard triggers, cloud transcription (OpenAI/Groq), copy-paste output, Linux/macOS support, CLI configuration, auto-start, basic sound feedback.
- **Out of Scope:** Local model transcription, complex voice commands, GUI configuration, application-specific integrations, Windows support.

## 4. Success Criteria

- The service reliably transcribes speech using selected cloud APIs with high accuracy.
- The copy-paste mechanism works consistently across supported OSes and applications.
- Users can easily install, configure, and use the service via CLI and keyboard shortcuts.
- The service runs stably in the background with minimal resource usage.

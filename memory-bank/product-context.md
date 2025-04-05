# Product Context

- **Project Name:** Faster Whisper Dictation

- **Problem:** Users need a quick and seamless way to dictate high-quality text into any application without interrupting their workflow, ideally using a fast copy-paste mechanism rather than slower character-by-character typing.

- **Solution / Core Goal:** Provide a lightweight, fast, and accurate background dictation service for Linux and macOS. It listens for keyboard shortcuts, records audio, sends it **exclusively** to high-performance cloud transcription services (OpenAI or Groq) for optimal accuracy, and outputs the result via a **copy-paste mechanism** (copying to clipboard and simulating Cmd+V/Ctrl+V) into the active application. (Decision: Local transcription explicitly removed).

- **Target Users:** Developers, writers, students, or anyone who frequently types and prioritizes transcription accuracy and speed, benefiting from a hands-free, clipboard-based way to input text using cloud-powered voice recognition.

- **Key Features & Requirements:**

  - **Cloud Transcription:** Transcribe speech to text _exclusively_ using cloud APIs: OpenAI (default) or Groq. (Local transcription is out of scope).
  - **Keyboard Triggers:** Configurable keyboard shortcuts (double-tap start, single-tap stop/paste, double-tap cancel).
  - **Clipboard Output:** Copies transcribed text to the system clipboard.
  - **Automatic Paste:** Simulates paste (Cmd+V/Ctrl+V) into the currently active application.
  - **OS Support:** Linux (Debian/Ubuntu/Mint focus) and macOS. (Windows is not supported).
  - **Configuration:** Allow customization via command-line options (trigger key, max time, language, model, transcriber choice, sound effects).
  - **Environment Variables:** Load API keys (OpenAI/Groq) via environment variables with priority (Shell > Project `.env` > Home `.env`).
  - **Background Service:** Run unobtrusively, automatically starting on login (via systemd/launchd).
  - **Installation:** Provide `setup.sh` for installation (dependencies, venv, service config) and `revert_setup.sh` for uninstallation.
  - **Optional Feedback:** Sound effects for recording start/stop/cancel.

- **User Experience Goals:**

  - **Fast & Responsive:** Near real-time transcription; immediate recording triggers.
  - **Seamless Integration:** Works in the background, pastes into any application without focus changes.
  - **Simple & Intuitive:** Easy install/use; minimal configuration; memorable shortcuts.
  - **Reliable:** Consistent background operation; graceful error handling.

- **Scope:**

  - **In Scope:** Background service, keyboard triggers, cloud transcription (OpenAI/Groq), copy-paste output, Linux/macOS support, CLI configuration, auto-start.
  - **Out of Scope:** Local model transcription, complex voice commands (beyond start/stop/cancel), GUI configuration, application-specific integrations, Windows support.

- **Technical Constraints & Dependencies:**

  - **Cloud APIs:** Requires active internet connection and valid API keys for OpenAI or Groq.
  - **OS:** Linux (Debian/Ubuntu/Mint tested) or macOS.
  - **Linux Dependencies:** Requires `xsel` command-line utility for clipboard access.
  - **Permissions:** Requires microphone access and keyboard simulation permissions (`input` group membership and `/dev/uinput` access on Linux; Accessibility permissions on macOS).

- **Stakeholders:** Primarily the developer(s) and end-users seeking efficient, high-quality cloud-based dictation.

_[YYYY-MM-DD HH:MM:SS] - Merged content from project-brief.md and added technical constraints._

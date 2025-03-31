# Product Context

- **Problem:** Users need a quick and seamless way to dictate high-quality text into any application without interrupting their workflow, ideally using a fast copy-paste mechanism rather than slower character-by-character typing.
- **Solution:** A background service that listens for specific keyboard shortcuts. When activated, it records audio, sends it _exclusively_ to high-performance cloud transcription services (OpenAI or Groq) for optimal accuracy. It then copies the transcribed text to the system clipboard and simulates a paste command (Cmd+V on macOS, Ctrl+V on Linux) to insert the text into the currently active application. (Note: Functionality for local `faster-whisper` transcription was removed to focus on cloud API quality).
- **Target Users:** Developers, writers, students, or anyone who frequently types and prioritizes transcription accuracy and speed, benefiting from a hands-free, clipboard-based way to input text using cloud-powered voice recognition on Linux or macOS.
- **User Experience Goals:**
  - **Fast & Responsive:** Transcription should feel near real-time. Recording triggers should be immediate.
  - **Seamless Integration:** Should work unobtrusively in the background and type text into any application without requiring focus changes.
  - **Simple & Intuitive:** Easy to install and use with minimal configuration. Keyboard shortcuts should be easy to remember and perform.
  - **Reliable:** The service should run consistently in the background and handle errors gracefully.
- **Key Features (from user perspective):**
  - Double-tap a key (Right Command on macOS, Right Control on Linux by default) to start dictating.
  - Single-tap the same key to stop dictating, copy the text to the clipboard, and paste it into the active application.
  - Double-tap another key (Right Option on macOS, Right Alt on Linux by default) to cancel the current recording.
  - Choice between high-quality cloud backends: OpenAI (default) or Groq.
  - Optional sound effects to confirm recording start/stop/cancel.
  - Ability to customize the trigger key, recording duration, language, and model via command-line flags.
  - Automatic startup on login.

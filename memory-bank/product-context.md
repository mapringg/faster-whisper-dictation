# Product Context

- **Problem:** Users need a quick and seamless way to dictate high-quality text into any application without interrupting their workflow. Local transcription models can sometimes lack accuracy or speed compared to leading cloud services.
- **Solution:** A background service that listens for specific keyboard shortcuts. When activated, it records audio, sends it _exclusively_ to high-performance cloud transcription services (OpenAI or Groq) for optimal accuracy, and then simulates keyboard input to type the transcribed text directly into the currently active application. (Note: Functionality for local `faster-whisper` transcription was removed to focus on cloud API quality).
- **Target Users:** Developers, writers, students, or anyone who frequently types and prioritizes transcription accuracy and speed, benefiting from a hands-free way to input text using cloud-powered voice recognition on Linux or macOS.
- **User Experience Goals:**
  - **Fast & Responsive:** Transcription should feel near real-time. Recording triggers should be immediate.
  - **Seamless Integration:** Should work unobtrusively in the background and type text into any application without requiring focus changes.
  - **Simple & Intuitive:** Easy to install and use with minimal configuration. Keyboard shortcuts should be easy to remember and perform.
  - **Reliable:** The service should run consistently in the background and handle errors gracefully.
- **Key Features (from user perspective):**
  - Double-tap a key (Right Command/Control by default) to start dictating.
  - Single-tap the same key to stop dictating and get the text typed out.
  - Double-tap another key (Right Option/Alt by default) to cancel the current recording.
  - Choice between high-quality cloud backends: OpenAI (default) or Groq.
  - Optional sound effects to confirm recording start/stop/cancel.
  - Ability to customize the trigger key, recording duration, language, and model via command-line flags.
  - Automatic startup on login.

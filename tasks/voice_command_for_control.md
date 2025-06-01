# Voice Command for Control

## Description

Implement simple voice commands to control the application, such as "start recording", "stop recording", or "change language to [language]". This will provide a hands-free alternative to hotkeys for controlling the dictation program.

## Implementation Details

- **Speech Recognition for Commands:** Integrate a lightweight, fast speech recognition module specifically for recognizing a predefined set of control commands. This could be a separate, smaller model than the main dictation transcriber to ensure quick response times.
- **Command Mapping:** Map recognized voice commands to existing application functions (e.g., `App.start_recording()`, `App.stop_recording()`, `App._change_language()`).
- **User Interface Feedback:** Provide audio or visual feedback when a voice command is recognized and executed.
- **Configuration:** Allow users to enable/disable voice commands and potentially customize the command phrases.

## Affected Files

- `src/core/app.py`: To integrate command handling logic.
- `src/services/input_handler.py`: Potentially to extend input handling beyond keyboard.
- New module for voice command recognition.

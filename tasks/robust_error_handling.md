# Robust Error Handling

## Description

Implement more robust error handling mechanisms throughout the application, particularly for external API calls, audio device interactions, and keyboard input. This will improve application stability, provide better user feedback, and enable graceful recovery from transient issues.

## Implementation Details

- **API Call Retries:** Implement exponential backoff and retry logic for API calls to transcription services to handle transient network issues or rate limits.
- **Audio Device Errors:** Enhance error handling for `sounddevice` operations, providing clear messages if an audio device is unavailable or disconnects.
- **Keyboard Input Errors:** Improve error handling for `pynput` or `uinput` related issues, ensuring the application doesn't crash due to unexpected input events.
- **Centralized Error Logging:** Ensure all errors are logged consistently with sufficient detail (e.g., stack traces) to aid debugging.
- **User Notifications:** Provide user-friendly notifications (e.g., via the status icon or pop-up messages) for critical errors that require user intervention.
- **Graceful Degradation:** Where possible, implement graceful degradation strategies (e.g., temporarily switching to a local model if a cloud API fails).

## Affected Files

- `src/core/app.py`: To centralize error handling and user notifications.
- `src/services/transcriber.py`: To implement API retry logic.
- `src/services/recorder.py`: To enhance audio device error handling.
- `src/services/input_handler.py`: To improve keyboard input error handling.
- `src/services/status_indicator.py`: To display error states or messages.

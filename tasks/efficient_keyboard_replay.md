# Efficient Keyboard Replay

## Description

Optimize the `KeyboardReplayer` to type transcribed text more efficiently, especially for long transcriptions. This will prevent delays or overwhelming the system/target application during text output.

## Implementation Details

- **Typing Speed Control:** Implement mechanisms to control the typing speed, potentially allowing users to configure it.
- **Batching/Chunking:** Instead of typing character by character, consider typing in small batches or chunks to reduce overhead.
- **Clipboard Pasting (Conditional):** For very long transcriptions, explore the option of copying the entire text to the clipboard and then pasting it, if the target application supports it and it doesn't interfere with the user's workflow. This would be a significant speed improvement but needs careful consideration of user experience.
- **Error Handling during Replay:** Improve error handling during replay to gracefully manage situations where typing might fail (e.g., target application not responding).

## Affected Files

- `src/services/input_handler.py`: To modify the `KeyboardReplayer` class.
- `src/core/app.py`: Potentially to pass configuration for replay speed or method.

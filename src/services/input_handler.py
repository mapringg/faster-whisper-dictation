import logging
import platform
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any

from pynput import keyboard

from ..core import constants as const

logger = logging.getLogger(__name__)

KeyboardCallback = Callable[[], None]


class ClipboardPaster:
    """Handles pasting transcribed text via the system clipboard."""

    def __init__(
        self, callback: KeyboardCallback, keyboard_controller: Any | None = None
    ):
        self.callback = callback
        self.kb = keyboard_controller or keyboard.Controller()

    def _get_full_text(self, segments: list[Any]) -> str:
        """Concatenates text from segments, removing any leading whitespace."""
        if not segments or not isinstance(segments, list):
            return ""
        return "".join(getattr(s, "text", "") for s in segments).lstrip()

    def _copy_to_clipboard(self, text: str):
        """Copies text to the clipboard using platform-specific commands."""
        system = platform.system()
        if system == "Darwin":
            command = ["pbcopy"]
        elif system == "Linux":
            command = ["xsel", "--clipboard", "--input"]
        else:
            raise OSError(f"Unsupported platform for clipboard operations: {system}")

        try:
            subprocess.run(
                command,
                input=text,
                text=True,
                check=True,
                capture_output=True,
            )
            logger.info(f"Copied {len(text)} chars to clipboard via {command[0]}.")
        except FileNotFoundError:
            logger.error(f"'{command[0]}' not found. Please ensure it is installed.")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to copy with {command[0]}: {e.stderr}")
            raise

    def _simulate_paste(self):
        """Simulates the platform-specific paste shortcut (Cmd+V or Ctrl+V)."""
        modifier = (
            keyboard.Key.cmd if platform.system() == "Darwin" else keyboard.Key.ctrl
        )
        try:
            logger.info("Simulating paste command...")
            with self.kb.pressed(modifier):
                self.kb.press("v")
                self.kb.release("v")
            logger.info("Paste command sent.")
        except Exception as e:
            logger.error(f"Error simulating paste: {e}")

    def replay(self, event: Any) -> None:
        """Copies the transcribed text to the clipboard and pastes it."""
        logger.info("Starting text paste process...")
        full_text = self._get_full_text(event.kwargs.get("segments", []))

        try:
            if not full_text:
                logger.warning("No text to paste.")
            else:
                self._copy_to_clipboard(full_text)
                time.sleep(0.1)  # Small delay for clipboard to update
                self._simulate_paste()
        except Exception as e:
            logger.error(f"Paste process failed: {e}")
        finally:
            # This callback is crucial to transition the state machine back to READY.
            self.callback()


class DoubleKeyListener:
    """Handles double-press and single-press events for a specific key."""

    def __init__(
        self,
        activate_callback: KeyboardCallback,
        deactivate_callback: KeyboardCallback,
        key: Any,
        double_click_threshold: float = const.DEFAULT_DOUBLE_CLICK_THRESHOLD_SECS,
    ):
        self.activate_callback = activate_callback
        self.deactivate_callback = deactivate_callback
        self.key = key
        self.double_click_threshold = double_click_threshold
        self.last_press_time = 0.0
        self.listener: keyboard.Listener | None = None
        self.shutdown_event = threading.Event()

    def on_press(self, key: Any):
        if key != self.key:
            return

        current_time = time.time()
        if (current_time - self.last_press_time) < self.double_click_threshold:
            self.activate_callback()
            self.last_press_time = 0  # Reset to prevent triple-click acting as single
        else:
            self.deactivate_callback()

        self.last_press_time = current_time

    def run(self):
        """Start listening for key events in a blocking manner."""
        try:
            with keyboard.Listener(on_press=self.on_press) as listener:
                self.listener = listener
                # Block until shutdown is signaled via the stop() method.
                self.shutdown_event.wait()
                listener.stop()
        except Exception as e:
            logger.error(f"Error in double key listener: {e}")
        finally:
            logger.info("Double key listener stopped.")

    def stop(self):
        """Signals the listener thread to stop."""
        self.shutdown_event.set()

import logging
import platform
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from pynput import keyboard

from ..core import constants as const
from .keyboard_controller_factory import create_keyboard_controller

logger = logging.getLogger(__name__)

# Type definitions
T = TypeVar("T")
KeyboardCallback = Callable[[], None]
Event = Any  # Type for state machine event


class ClipboardPaster:
    """Handles pasting transcribed text via the system clipboard."""

    def __init__(
        self,
        callback: KeyboardCallback,
        keyboard_controller: Any | None = None,
    ):
        """
        Initialize the paster with a callback function.

        Args:
            callback: Function to call after pasting is complete.
            keyboard_controller: Optional keyboard controller for dependency injection.
        """
        self.callback = callback
        self.kb = keyboard_controller or create_keyboard_controller()
        self.lock = threading.Lock()

    def _validate_segments(self, segments: list[Any]) -> bool:
        """Validate the transcription segments."""
        if not isinstance(segments, list):
            logger.error(f"Invalid segments type: {type(segments)}")
            return False

        for segment in segments:
            if not hasattr(segment, "text") or not isinstance(segment.text, str):
                logger.error("Segment missing text attribute or text is not a string")
                return False
        return True

    def _get_full_text(self, segments: list[Any]) -> str:
        """Concatenates text from segments, removing any leading whitespace."""
        if not segments:
            return ""
        raw_text = "".join(segment.text for segment in segments)
        return raw_text.lstrip()

    def _copy_to_clipboard(self, text: str):
        """Copies text to the clipboard using platform-specific commands."""
        system = platform.system()
        if system == "Darwin":
            command = ["pbcopy"]
            cmd_name = "pbcopy"
        elif system == "Linux":
            command = ["xsel", "--clipboard", "--input"]
            cmd_name = "xsel"
        else:
            raise OSError(f"Unsupported platform for clipboard operations: {system}")

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate(input=text)

            if process.returncode != 0:
                logger.error(
                    f"Failed to copy text using {cmd_name}. Stderr: {stderr.strip()}"
                )
                raise subprocess.CalledProcessError(
                    process.returncode, command, stdout, stderr
                )

            logger.info(
                f"Successfully copied {len(text)} characters to clipboard via {cmd_name}."
            )
        except FileNotFoundError:
            logger.error(
                f"'{cmd_name}' command not found. Please ensure it is installed and in your PATH."
            )
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while using {cmd_name}: {e}")
            raise

    def _simulate_paste(self):
        """Simulates the platform-specific paste shortcut (Cmd+V or Ctrl+V)."""
        system = platform.system()
        if system == "Darwin":
            modifier_key = keyboard.Key.cmd
        elif system == "Linux":
            modifier_key = keyboard.Key.ctrl
        else:
            logger.error(f"Unsupported platform for paste simulation: {system}")
            return

        try:
            logger.info("Attempting to paste from clipboard...")
            with self.kb.pressed(modifier_key):
                self.kb.press("v")
                self.kb.release("v")
            logger.info("Paste command executed.")
        except Exception as e:
            logger.error(f"Error simulating paste: {e}")

    def replay(self, event: Event) -> None:
        """
        Copies the transcribed text to the clipboard and pastes it.

        Args:
            event: State machine event containing transcription segments.
        """
        logger.info("Starting text paste process...")
        segments = event.kwargs.get("segments", [])

        if not self._validate_segments(segments):
            logger.error("Invalid transcription segments provided.")
            self.callback()
            return

        full_text = self._get_full_text(segments)

        if not full_text:
            logger.warning("No text generated to paste.")
            self.callback()
            return

        try:
            self._copy_to_clipboard(full_text)
            time.sleep(0.2)  # A small delay for the clipboard to update.
            self._simulate_paste()
        except Exception as e:
            logger.error(f"Failed to complete paste process: {e}")
        finally:
            self.callback()


class KeyListener:
    """Handles single key press events with error handling and cleanup."""

    def __init__(self, callback: KeyboardCallback, key: str):
        """
        Initialize the key listener with callback and key binding.

        Args:
            callback: Function to call when key is pressed
            key: Key combination to listen for (e.g. 'Key.cmd_r')
        """
        self.callback = callback
        self.key = key
        self.listener: keyboard.GlobalHotKeys | None = None
        self.lock = threading.Lock()  # Thread-safe state management

    def _validate_key(self) -> bool:
        """
        Validate the key combination.

        Returns:
            bool: True if key is valid, False otherwise
        """
        try:
            keyboard.HotKey.parse(self.key)
            return True
        except ValueError as e:
            logger.error(f"Invalid key combination '{self.key}': {str(e)}")
            return False

    def run(self) -> None:
        """Start listening for key presses with error handling and shutdown support."""
        if not self._validate_key():
            logger.error("Cannot start key listener with invalid key")
            return

        try:
            with self.lock:
                self.listener = keyboard.GlobalHotKeys({self.key: self._safe_callback})
                self.listener.start()

                # Instead of blocking indefinitely, check periodically if we should shut down
                while self.listener.running:
                    # Check if shutdown_event exists and is set
                    if hasattr(self, "shutdown_event") and self.shutdown_event.is_set():
                        logger.info(
                            "Shutdown event detected in key listener, stopping..."
                        )
                        break

                    # Sleep briefly to avoid high CPU usage
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in key listener: {str(e)}")
        finally:
            self._cleanup()

    def _safe_callback(self) -> None:
        """Wrapper for callback with error handling."""
        try:
            self.callback()
        except Exception as e:
            logger.error(f"Error in key callback: {str(e)}")

    def _cleanup(self) -> None:
        """Clean up listener resources."""
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception as e:
                logger.error(f"Error stopping key listener: {str(e)}")
            finally:
                self.listener = None


class DoubleKeyListener:
    """Handles double-click key events with rate limiting and error handling."""

    # Class constants from core.constants
    DEFAULT_DOUBLE_CLICK_THRESHOLD = (
        const.DEFAULT_DOUBLE_CLICK_THRESHOLD_SECS
    )  # Seconds between clicks
    DEFAULT_MIN_PRESS_DURATION = (
        const.DEFAULT_MIN_PRESS_DURATION_SECS
    )  # Minimum press duration in seconds

    def __init__(
        self,
        activate_callback: KeyboardCallback,
        deactivate_callback: KeyboardCallback,
        key: keyboard.Key = keyboard.Key.cmd_r,
        double_click_threshold: float = DEFAULT_DOUBLE_CLICK_THRESHOLD,
        min_press_duration: float = DEFAULT_MIN_PRESS_DURATION,
    ):
        """
        Initialize the double key listener with callbacks and key binding.

        Args:
            activate_callback: Function to call on double-click
            deactivate_callback: Function to call on single-click
            key: Key to listen for (default: right command key)
            double_click_threshold: Time window for double-click detection in seconds
            min_press_duration: Minimum press duration in seconds for debouncing
        """
        self.activate_callback = activate_callback
        self.deactivate_callback = deactivate_callback
        self.key = key
        self.last_press_time = 0.0
        self.double_click_threshold = double_click_threshold
        self.min_press_duration = min_press_duration
        self.listener: keyboard.Listener | None = None
        self.lock = threading.Lock()  # Thread-safe state management

    def _safe_activate(self) -> None:
        """Wrapper for activate callback with error handling."""
        try:
            self.activate_callback()
        except Exception as e:
            logger.error(f"Error in activate callback: {str(e)}")

    def _safe_deactivate(self) -> None:
        """Wrapper for deactivate callback with error handling."""
        try:
            self.deactivate_callback()
        except Exception as e:
            logger.error(f"Error in deactivate callback: {str(e)}")

    def on_press(self, key: Any) -> bool | None:
        """
        Handle key press events with rate limiting.

        Args:
            key: The key that was pressed

        Returns:
            Optional[bool]: Return value depends on pynput requirements
        """
        if key != self.key:
            return None

        current_time = time.time()
        time_since_last = current_time - self.last_press_time

        # Rate limiting
        if time_since_last < self.min_press_duration:
            return None

        self.last_press_time = current_time

        # Determine if double click
        is_dbl_click = time_since_last < self.double_click_threshold

        try:
            if is_dbl_click:
                self._safe_activate()
            else:
                self._safe_deactivate()
        except Exception as e:
            logger.error(f"Error handling key press: {str(e)}")

        return None

    def on_release(self, key: Any) -> None:
        """Handle key release events."""
        pass

    def run(self) -> None:
        """Start listening for key events with error handling and shutdown support."""
        try:
            with self.lock:
                self.listener = keyboard.Listener(
                    on_press=self.on_press, on_release=self.on_release
                )
                self.listener.start()

                # Instead of blocking indefinitely, check periodically if we should shut down
                while self.listener.is_alive():
                    # Check if shutdown_event exists and is set
                    if hasattr(self, "shutdown_event") and self.shutdown_event.is_set():
                        logger.info(
                            "Shutdown event detected in double key listener, stopping..."
                        )
                        break

                    # Sleep briefly to avoid high CPU usage
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in double key listener: {str(e)}")
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """Clean up listener resources."""
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception as e:
                logger.error(f"Error stopping double key listener: {str(e)}")
            finally:
                self.listener = None

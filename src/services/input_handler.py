import logging
import platform  # Added for OS detection
import subprocess  # Added for pbcopy
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


class KeyboardReplayer:
    """Handles typing out transcribed text with rate limiting and error handling."""

    # Class constants from core.constants
    DEFAULT_TYPING_DELAY = (
        const.DEFAULT_TYPING_DELAY_SECS
    )  # Delay between keystrokes in seconds
    DEFAULT_MAX_RETRIES = const.DEFAULT_MAX_TYPING_RETRIES
    DEFAULT_RETRY_DELAY = (
        const.DEFAULT_RETRY_DELAY_SECS
    )  # Base delay for retries in seconds

    def __init__(
        self,
        callback: KeyboardCallback,
        keyboard_controller: Any | None = None,
        typing_delay: float = DEFAULT_TYPING_DELAY,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ):
        """
        Initialize the replayer with a callback function.

        Args:
            callback: Function to call after typing is complete
            keyboard_controller: Optional keyboard controller for dependency injection
            typing_delay: Delay between keystrokes in seconds
            max_retries: Maximum number of retry attempts for typing errors
            retry_delay: Base delay between retry attempts in seconds
        """
        self.callback = callback
        self.kb = (
            keyboard_controller or create_keyboard_controller()
        )  # Use factory by default
        self.typing_delay = typing_delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.lock = threading.Lock()  # Thread-safe state management

    def _validate_segments(self, segments: list[Any]) -> bool:
        """
        Validate the transcription segments.

        Args:
            segments: List of transcription segments

        Returns:
            bool: True if segments are valid, False otherwise
        """
        if not isinstance(segments, list):
            logger.error(f"Invalid segments type: {type(segments)}")
            return False

        for segment in segments:
            if not hasattr(segment, "text") or not isinstance(segment.text, str):
                logger.error("Segment missing text attribute or text is not a string")
                return False

        return True

    def _type_with_retry(self, char: str) -> bool:
        """
        Type a single character with retry mechanism.

        Args:
            char: Character to type

        Returns:
            bool: True if successful, False after max retries
        """
        for attempt in range(self.max_retries):
            try:
                self.kb.type(char)
                return True
            except Exception as e:
                logger.warning(
                    f"Error typing character '{char}' (attempt {attempt + 1}): {str(e)}"
                )
                if attempt < self.max_retries - 1:
                    # Use instance variable for retry delay
                    backoff_delay = self.retry_delay * (attempt + 1)
                    time.sleep(backoff_delay)

        logger.error(
            f"Failed to type character '{char}' after {self.max_retries} attempts"
        )
        return False

    def replay(self, event: Event) -> None:
        """
        Handle the text replay process with error handling and rate limiting.

        Args:
            event: State machine event containing transcription segments
        """
        logger.info("Starting text replay...")
        segments = event.kwargs.get("segments", [])
        text_buffer: list[str] = []

        # Validate input segments
        if not self._validate_segments(segments):
            logger.error("Invalid transcription segments")
            self.callback()
            return

        try:
            if platform.system() == "Darwin":  # macOS specific logic
                logger.info("macOS detected, using pbcopy for clipboard output.")
                full_text = ""
                is_first_char_overall = True
                for segment in segments:
                    for char in segment.text:
                        # Skip leading space only for the very first character overall
                        if is_first_char_overall and char == " ":
                            is_first_char_overall = False
                            continue
                        is_first_char_overall = False  # Mark after first non-space char
                        full_text += char

                if full_text:
                    try:
                        # Use subprocess to pipe text to pbcopy
                        subprocess.run(
                            ["pbcopy"],
                            input=full_text,
                            text=True,
                            check=True,
                            capture_output=True,  # Suppress pbcopy output
                        )
                        logger.info(
                            f"Successfully copied {len(full_text)} characters to clipboard."
                        )
                        # Add a small delay before pasting
                        time.sleep(0.1)

                        # Simulate Command + V paste shortcut
                        try:
                            logger.info("Attempting to paste from clipboard...")
                            with self.kb.pressed(keyboard.Key.cmd):
                                self.kb.press("v")
                                self.kb.release("v")
                            logger.info("Paste command executed.")
                        except Exception as paste_err:
                            logger.error(f"Error simulating paste: {paste_err}")

                    except subprocess.CalledProcessError as e:
                        logger.error(
                            f"Failed to copy text to clipboard using pbcopy: {e}"
                        )
                        logger.error(f"pbcopy stderr: {e.stderr}")
                    except FileNotFoundError:
                        logger.error(
                            "pbcopy command not found. Is it installed and in PATH?"
                        )
                    except Exception as e:
                        logger.error(
                            f"An unexpected error occurred while using pbcopy: {e}"
                        )
                else:
                    logger.warning("No text generated to copy to clipboard.")

            else:  # Linux specific logic (using xclip + paste)
                logger.info("Linux detected, using xclip and paste simulation.")
                full_text = ""
                is_first_char_overall = True
                for segment in segments:
                    for char in segment.text:
                        # Skip leading space only for the very first character overall
                        if is_first_char_overall and char == " ":
                            is_first_char_overall = False
                            continue
                        is_first_char_overall = False  # Mark after first non-space char
                        full_text += char

                if full_text:
                    try:
                        # Use subprocess.Popen for better control over xsel
                        logger.info(
                            "Attempting to copy text to clipboard using xsel via Popen..."
                        )
                        process = subprocess.Popen(
                            ["xsel", "--clipboard", "--input"],  # Use xsel command
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                        stdout, stderr = process.communicate(input=full_text)

                        if process.returncode == 0:
                            logger.info(
                                f"Successfully copied {len(full_text)} characters to clipboard via xsel."
                            )
                            # Increase delay slightly before pasting
                            time.sleep(0.2)
                        else:
                            # Raise an error to be caught by the outer exception handler
                            raise subprocess.CalledProcessError(
                                process.returncode,
                                process.args,
                                stdout,
                                stderr,  # Keep error details
                            )

                        # Simulate Control + V paste shortcut (No changes needed here)
                        try:
                            logger.info(
                                "Attempting to paste from clipboard (Ctrl+V)..."
                            )
                            # Assuming self.kb maps pynput keys or uses uinput equivalents
                            # Need to verify UInputController handles this correctly
                            with self.kb.pressed(
                                keyboard.Key.ctrl
                            ):  # Or specific uinput key if needed
                                self.kb.press("v")
                                self.kb.release("v")
                            logger.info("Paste command (Ctrl+V) executed.")
                        except AttributeError:
                            logger.error(
                                "Keyboard controller does not support 'pressed' context manager or required keys (Ctrl/V). Paste simulation failed."
                            )
                        except Exception as paste_err:
                            logger.error(
                                f"Error simulating paste (Ctrl+V): {paste_err}"
                            )

                    except subprocess.CalledProcessError as e:
                        logger.error(
                            f"Failed to copy text to clipboard using xsel: {e}"
                        )
                        logger.error(f"xsel stderr: {e.stderr}")
                        logger.error(f"xsel stdout: {e.stdout}")
                    except FileNotFoundError:
                        logger.error(
                            "xsel command not found. Please install xsel for clipboard functionality on Linux."
                        )
                    except Exception as e:
                        logger.error(
                            f"An unexpected error occurred while using xsel: {e}"
                        )
                else:
                    logger.warning("No text generated to copy to clipboard.")

        except Exception as e:
            logger.error(f"Unexpected error during text replay: {str(e)}")
        finally:
            # This callback needs to be called regardless of the method (typing/copying)
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

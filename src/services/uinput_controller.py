import contextlib
import logging
import time

import uinput
from pynput import keyboard  # Import pynput keyboard for key definitions

logger = logging.getLogger(__name__)

# Define character to key mappings
CHAR_TO_KEY = {
    "a": uinput.KEY_A,
    "b": uinput.KEY_B,
    "c": uinput.KEY_C,
    "d": uinput.KEY_D,
    "e": uinput.KEY_E,
    "f": uinput.KEY_F,
    "g": uinput.KEY_G,
    "h": uinput.KEY_H,
    "i": uinput.KEY_I,
    "j": uinput.KEY_J,
    "k": uinput.KEY_K,
    "l": uinput.KEY_L,
    "m": uinput.KEY_M,
    "n": uinput.KEY_N,
    "o": uinput.KEY_O,
    "p": uinput.KEY_P,
    "q": uinput.KEY_Q,
    "r": uinput.KEY_R,
    "s": uinput.KEY_S,
    "t": uinput.KEY_T,
    "u": uinput.KEY_U,
    "v": uinput.KEY_V,
    "w": uinput.KEY_W,
    "x": uinput.KEY_X,
    "y": uinput.KEY_Y,
    "z": uinput.KEY_Z,
    "A": uinput.KEY_A,
    "B": uinput.KEY_B,
    "C": uinput.KEY_C,
    "D": uinput.KEY_D,
    "E": uinput.KEY_E,
    "F": uinput.KEY_F,
    "G": uinput.KEY_G,
    "H": uinput.KEY_H,
    "I": uinput.KEY_I,
    "J": uinput.KEY_J,
    "K": uinput.KEY_K,
    "L": uinput.KEY_L,
    "M": uinput.KEY_M,
    "N": uinput.KEY_N,
    "O": uinput.KEY_O,
    "P": uinput.KEY_P,
    "Q": uinput.KEY_Q,
    "R": uinput.KEY_R,
    "S": uinput.KEY_S,
    "T": uinput.KEY_T,
    "U": uinput.KEY_U,
    "V": uinput.KEY_V,
    "W": uinput.KEY_W,
    "X": uinput.KEY_X,
    "Y": uinput.KEY_Y,
    "Z": uinput.KEY_Z,
    "1": uinput.KEY_1,
    "2": uinput.KEY_2,
    "3": uinput.KEY_3,
    "4": uinput.KEY_4,
    "5": uinput.KEY_5,
    "6": uinput.KEY_6,
    "7": uinput.KEY_7,
    "8": uinput.KEY_8,
    "9": uinput.KEY_9,
    "0": uinput.KEY_0,
    " ": uinput.KEY_SPACE,
    ".": uinput.KEY_DOT,
    ",": uinput.KEY_COMMA,
    "!": uinput.KEY_1,
    "@": uinput.KEY_2,
    "#": uinput.KEY_3,
    "$": uinput.KEY_4,
    "%": uinput.KEY_5,
    "^": uinput.KEY_6,
    "&": uinput.KEY_7,
    "*": uinput.KEY_8,
    "(": uinput.KEY_9,
    ")": uinput.KEY_0,
    "-": uinput.KEY_MINUS,
    "_": uinput.KEY_MINUS,
    "=": uinput.KEY_EQUAL,
    "+": uinput.KEY_EQUAL,
    "[": uinput.KEY_LEFTBRACE,
    "{": uinput.KEY_LEFTBRACE,
    "]": uinput.KEY_RIGHTBRACE,
    "}": uinput.KEY_RIGHTBRACE,
    "\\": uinput.KEY_BACKSLASH,
    "|": uinput.KEY_BACKSLASH,  # Needs Shift
    ";": uinput.KEY_SEMICOLON,
    ":": uinput.KEY_SEMICOLON,  # Needs Shift
    "'": uinput.KEY_APOSTROPHE,
    '"': uinput.KEY_APOSTROPHE,  # Needs Shift
    "/": uinput.KEY_SLASH,
    "?": uinput.KEY_SLASH,  # Needs Shift
    "`": uinput.KEY_GRAVE,
    "~": uinput.KEY_GRAVE,  # Needs Shift
    "\n": uinput.KEY_ENTER,
    "\t": uinput.KEY_TAB,
}

# Define which characters need shift (more comprehensive)
SHIFT_CHARS = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+{}|:"<>?~')

# Mapping from pynput special keys to uinput keys
PYNPUT_TO_UINPUT = {
    keyboard.Key.ctrl: uinput.KEY_LEFTCTRL,
    keyboard.Key.ctrl_l: uinput.KEY_LEFTCTRL,
    keyboard.Key.ctrl_r: uinput.KEY_RIGHTCTRL,
    keyboard.Key.shift: uinput.KEY_LEFTSHIFT,
    keyboard.Key.shift_l: uinput.KEY_LEFTSHIFT,
    keyboard.Key.shift_r: uinput.KEY_RIGHTSHIFT,
    keyboard.Key.alt: uinput.KEY_LEFTALT,
    keyboard.Key.alt_l: uinput.KEY_LEFTALT,
    keyboard.Key.alt_r: uinput.KEY_RIGHTALT,
    keyboard.Key.cmd: uinput.KEY_LEFTMETA,  # Map Cmd to Meta (Super/Windows key)
    keyboard.Key.cmd_l: uinput.KEY_LEFTMETA,
    keyboard.Key.cmd_r: uinput.KEY_RIGHTMETA,
    keyboard.Key.enter: uinput.KEY_ENTER,
    keyboard.Key.space: uinput.KEY_SPACE,
    keyboard.Key.tab: uinput.KEY_TAB,
    keyboard.Key.backspace: uinput.KEY_BACKSPACE,
    # Add other mappings as needed
}


class UInputKeyboardController:
    """UInput-based keyboard controller for sending keystrokes."""

    def __init__(self):
        """Initialize the UInput device with all supported keys."""
        try:
            # Create a list of all unique keys we'll use from characters and special keys
            char_keys = set(CHAR_TO_KEY.values())
            special_keys = set(PYNPUT_TO_UINPUT.values())
            # Ensure necessary modifier keys are included
            modifier_keys = {
                uinput.KEY_LEFTSHIFT,
                uinput.KEY_RIGHTSHIFT,
                uinput.KEY_LEFTCTRL,
                uinput.KEY_RIGHTCTRL,
                uinput.KEY_LEFTALT,
                uinput.KEY_RIGHTALT,
                uinput.KEY_LEFTMETA,
                uinput.KEY_RIGHTMETA,
            }
            all_keys = list(char_keys | special_keys | modifier_keys)

            # Create the virtual input device
            self.device = uinput.Device(all_keys)
            # Allow some time for the device to be set up
            time.sleep(0.1)
            logger.info(
                f"UInput keyboard controller initialized successfully with {len(all_keys)} keys."
            )
        except PermissionError:
            logger.error(
                "Permission denied creating uinput device. "
                "Ensure user is in the 'input' group and has write access to /dev/uinput."
            )
            raise
        except Exception as e:
            logger.error(f"Failed to initialize UInput keyboard controller: {str(e)}")
            raise

    def _get_uinput_key(
        self, key: str | keyboard.Key | keyboard.KeyCode
    ) -> tuple[int | None, bool]:
        """
        Get the uinput key code and shift state for a character or pynput key.

        Args:
            key: The character (str) or pynput key object.

        Returns:
            tuple[int | None, bool]: The uinput key code (or None if not found) and shift state.
        """
        uinput_key = None
        needs_shift = False

        if isinstance(key, str) and len(key) == 1:
            uinput_key = CHAR_TO_KEY.get(key)
            needs_shift = key in SHIFT_CHARS
        elif isinstance(key, keyboard.Key):
            uinput_key = PYNPUT_TO_UINPUT.get(key)
        elif isinstance(key, keyboard.KeyCode):
            # Handle alphanumeric keys from KeyCode
            if key.char and key.char in CHAR_TO_KEY:
                uinput_key = CHAR_TO_KEY.get(key.char)
                needs_shift = key.char in SHIFT_CHARS
            # Could potentially map vk here if needed, but CHAR_TO_KEY is preferred

        if uinput_key is None:
            logger.warning(f"No uinput mapping found for key: {key}")

        return uinput_key, needs_shift

    def press(self, key: str | keyboard.Key | keyboard.KeyCode) -> None:
        """
        Press a key.

        Args:
            key: The character (str) or pynput key object to press.
        """
        uinput_key, needs_shift = self._get_uinput_key(key)
        if uinput_key is None:
            return

        try:
            if needs_shift:
                self.device.emit(uinput.KEY_LEFTSHIFT, 1)  # Press shift
                time.sleep(
                    0.005
                )  # Slightly longer delay before key press when shift is involved

            self.device.emit(uinput_key, 1)  # Press key
            time.sleep(0.005)  # Delay after key press
            # logger.debug(f"Pressed key: {key} (uinput: {uinput_key}, shift: {needs_shift})")

        except Exception as e:
            logger.error(f"Error pressing key '{key}': {str(e)}")
            # Attempt to release shift if it was pressed
            if needs_shift:
                try:
                    self.device.emit(uinput.KEY_LEFTSHIFT, 0)
                except Exception:
                    pass  # Ignore release error if press failed badly
            raise

    def release(self, key: str | keyboard.Key | keyboard.KeyCode) -> None:
        """
        Release a key.

        Args:
            key: The character (str) or pynput key object to release.
        """
        uinput_key, needs_shift = self._get_uinput_key(key)
        if uinput_key is None:
            return

        try:
            self.device.emit(uinput_key, 0)  # Release key
            time.sleep(0.005)  # Delay after key release
            # logger.debug(f"Released key: {key} (uinput: {uinput_key}, shift: {needs_shift})")

            if needs_shift:
                time.sleep(0.005)  # Delay before releasing shift
                self.device.emit(uinput.KEY_LEFTSHIFT, 0)  # Release shift
                time.sleep(0.005)  # Delay after releasing shift

        except Exception as e:
            logger.error(f"Error releasing key '{key}': {str(e)}")
            # Don't re-raise here usually, as release might follow a failed press

    @contextlib.contextmanager
    def pressed(self, *keys: str | keyboard.Key | keyboard.KeyCode) -> None:
        """
        Context manager to press and hold keys.

        Args:
            *keys: The keys to press and hold.
        """
        try:
            for key in keys:
                self.press(key)
            yield
        finally:
            # Release keys in reverse order
            for key in reversed(keys):
                try:
                    self.release(key)
                except Exception as e:
                    # Log error but continue releasing other keys
                    logger.error(
                        f"Error releasing key '{key}' in context manager: {str(e)}"
                    )

    def type(self, char: str) -> None:
        """
        Type a single character (press and release).

        Args:
            char: The character to type
        """
        # Use press/release for consistency, handles shift automatically
        try:
            self.press(char)
            # Release happens almost immediately for typing
            time.sleep(0.001)
            self.release(char)
            # Small delay between distinct characters
            time.sleep(0.0025)
        except Exception:
            # Error already logged in press/release
            pass  # Don't re-log or raise here for typing individual chars

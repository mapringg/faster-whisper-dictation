import logging
import time

import uinput

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
    "|": uinput.KEY_BACKSLASH,
    ";": uinput.KEY_SEMICOLON,
    ":": uinput.KEY_SEMICOLON,
    "'": uinput.KEY_APOSTROPHE,
    '"': uinput.KEY_APOSTROPHE,
    "/": uinput.KEY_SLASH,
    "?": uinput.KEY_SLASH,
    "`": uinput.KEY_GRAVE,
    "~": uinput.KEY_GRAVE,
    "\n": uinput.KEY_ENTER,
    "\t": uinput.KEY_TAB,
}

# Define which characters need shift
SHIFT_CHARS = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+{}|:"<>?~')


class UInputKeyboardController:
    """UInput-based keyboard controller for sending keystrokes."""

    def __init__(self):
        """Initialize the UInput device with all supported keys."""
        try:
            # Create a list of all unique keys we'll use
            keys = list(set(CHAR_TO_KEY.values()))
            # Add SHIFT key for uppercase letters and symbols
            keys.append(uinput.KEY_LEFTSHIFT)

            # Create the virtual input device
            self.device = uinput.Device(keys)
            # Allow some time for the device to be set up
            time.sleep(0.1)
            logger.info("UInput keyboard controller initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize UInput keyboard controller: {str(e)}")
            raise

    def type(self, char: str) -> None:
        """
        Type a single character.

        Args:
            char: The character to type

        Raises:
            ValueError: If character mapping is not found
        """
        if char not in CHAR_TO_KEY:
            logger.warning(f"No uinput mapping for character: {char}")
            return

        try:
            key = CHAR_TO_KEY[char]
            needs_shift = char in SHIFT_CHARS

            if needs_shift:
                # Press shift
                self.device.emit(uinput.KEY_LEFTSHIFT, 1)
                time.sleep(0.001)

            # Press and release the key
            self.device.emit(key, 1)  # Press
            time.sleep(0.001)
            self.device.emit(key, 0)  # Release

            if needs_shift:
                # Release shift
                time.sleep(0.001)
                self.device.emit(uinput.KEY_LEFTSHIFT, 0)

            # Small delay between keystrokes for stability
            time.sleep(0.0025)

        except Exception as e:
            logger.error(f"Error typing character '{char}': {str(e)}")
            raise

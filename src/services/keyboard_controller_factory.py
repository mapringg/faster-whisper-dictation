import logging
import platform
from typing import Any

from pynput import keyboard

from .uinput_controller import UInputKeyboardController

logger = logging.getLogger(__name__)


def create_keyboard_controller() -> Any:
    """
    Create and return the appropriate keyboard controller based on the operating system.

    Returns:
        Any: A keyboard controller instance (either pynput.keyboard.Controller or UInputKeyboardController)
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        logger.info("Using pynput keyboard controller for macOS")
        return keyboard.Controller()
    elif system == "Linux":
        logger.info("Using UInput keyboard controller for Linux")
        return UInputKeyboardController()
    else:
        logger.warning(
            f"Unsupported operating system: {system}, falling back to pynput"
        )
        return keyboard.Controller()

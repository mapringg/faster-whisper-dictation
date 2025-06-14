import logging
from typing import Any

from pynput import keyboard

logger = logging.getLogger(__name__)


def create_keyboard_controller() -> Any:
    """
    Create and return a pynput keyboard controller.

    Returns:
        Any: A pynput.keyboard.Controller instance.
    """
    logger.info("Using pynput keyboard controller")
    return keyboard.Controller()

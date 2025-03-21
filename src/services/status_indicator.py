import logging
import platform
import threading
from collections.abc import Callable
from enum import Enum

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

logger = logging.getLogger(__name__)

# Global variable to hold icon instance for main thread access on macOS
_global_icon = None


class StatusIconState(Enum):
    """States for the status icon."""

    READY = "ready"  # Green
    RECORDING = "recording"  # Red
    TRANSCRIBING = "transcribing"  # Yellow
    REPLAYING = "replaying"  # Blue
    ERROR = "error"  # Gray


class StatusIcon:
    """System tray icon that reflects the application state."""

    def __init__(self, on_exit: Callable | None = None):
        """
        Initialize the status icon.

        Args:
            on_exit: Optional callback to run when exit is selected from the menu
        """
        self.state = StatusIconState.READY
        self._icon = None
        self._icon_thread = None
        self._on_exit = on_exit
        self._sound_toggle_callback = None
        self._sounds_enabled = False
        self._language_callback = None
        self._current_language = "en"  # Default to English
        self._state_colors = {
            StatusIconState.READY: (0, 150, 0),  # Green
            StatusIconState.RECORDING: (200, 0, 0),  # Red
            StatusIconState.TRANSCRIBING: (200, 150, 0),  # Yellow/Orange
            StatusIconState.REPLAYING: (0, 0, 200),  # Blue
            StatusIconState.ERROR: (100, 100, 100),  # Gray
        }

        # State descriptions for tooltips and menus
        self._state_descriptions = {
            StatusIconState.READY: "Ready - Double tap to start recording",
            StatusIconState.RECORDING: "Recording... - Tap once to stop",
            StatusIconState.TRANSCRIBING: "Transcribing... please wait",
            StatusIconState.REPLAYING: "Replaying text...",
            StatusIconState.ERROR: "Error occurred",
        }

        # Available languages with labels
        self._languages = {
            "en": "English",
            "th": "Thai",
            # Add other languages here as needed
        }

    def _create_image(self, width, height, color):
        """Create a simple colored circle image for the icon."""
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)

        # Draw a colored circle
        dc.ellipse([(4, 4), (width - 4, height - 4)], fill=color)

        return image

    def _get_icon_image(self):
        """Get the appropriate icon based on current state."""
        color = self._state_colors.get(self.state, (100, 100, 100))
        return self._create_image(22, 22, color)

    def _get_menu_title(self):
        """Get the current state description for the menu."""
        return f"Status: {self._state_descriptions.get(self.state, 'Unknown')}"

    def _select_english(self):
        """Select English language."""
        self._select_language("en")
        return False  # Don't close the menu

    def _select_thai(self):
        """Select Thai language."""
        self._select_language("th")
        return False  # Don't close the menu

    def _setup_menu(self):
        """Create the right-click menu for the icon."""
        sound_text = "Enable Sounds" if not self._sounds_enabled else "Disable Sounds"

        menu_items = [
            MenuItem(lambda _: self._get_menu_title(), None, enabled=False),
            Menu.SEPARATOR,
        ]

        # Add sound toggle option if callback is set
        if self._sound_toggle_callback:
            menu_items.append(MenuItem(sound_text, self._toggle_sounds))
            menu_items.append(Menu.SEPARATOR)

        # Add language selection if callback is set
        if self._language_callback:
            # Add language header
            menu_items.append(
                MenuItem(
                    f"Language: {self._languages.get(self._current_language, 'Unknown')}",
                    None,
                    enabled=False,
                )
            )

            # Add language options with checkmark as suffix
            suffix_en = " ✓" if self._current_language == "en" else ""
            suffix_th = " ✓" if self._current_language == "th" else ""

            menu_items.append(MenuItem(f"English{suffix_en}", self._select_english))
            menu_items.append(MenuItem(f"Thai{suffix_th}", self._select_thai))

            menu_items.append(Menu.SEPARATOR)

        menu_items.append(MenuItem("Exit", self._exit))

        return Menu(*menu_items)

    def _toggle_sounds(self):
        """Toggle sound effects and update the menu."""
        if self._sound_toggle_callback:
            self._sounds_enabled = not self._sounds_enabled
            self._sound_toggle_callback(self._sounds_enabled)
            # Update menu
            if self._icon:
                self._icon.menu = self._setup_menu()
        return False  # Don't close the menu

    def _select_language(self, language_code):
        """Handle language selection from the menu."""
        if self._language_callback and language_code != self._current_language:
            self._current_language = language_code
            self._language_callback(language_code)
            # Update menu
            if self._icon:
                self._icon.menu = self._setup_menu()
        return False  # Don't close the menu

    def _exit(self):
        """Handle exit from the menu."""
        if self._on_exit:
            self._on_exit()
        return True  # This tells pystray to exit

    def start(self):
        """Start the status icon in a separate thread."""
        if self._icon_thread and self._icon_thread.is_alive():
            logger.warning("Status icon thread is already running")
            return

        # Create icon in the current thread (which should be the main thread)
        system = platform.system()
        icon_title = "Dictation Assistant"

        # macOS and Linux handle tooltips differently
        if system == "Darwin":  # macOS
            icon_title = "Dictation"  # Shorter title for macOS menu bar

        # Create the icon on the main thread
        self._icon = Icon(
            name="Dictation Assistant",
            icon=self._get_icon_image(),
            title=icon_title,
            menu=self._setup_menu(),
        )

        global _global_icon
        _global_icon = self._icon

        # For macOS, we'll run the icon in the main thread later
        # For other platforms, we can use a separate thread
        if system == "Darwin":
            # Just prepare the icon, will be run from main thread
            logger.info("Status icon created (will run on main thread)")
        else:
            # On non-macOS platforms, run in a separate thread
            def run_icon():
                try:
                    self._icon.run()
                except Exception as e:
                    logger.error(f"Error in status icon thread: {e}")

            self._icon_thread = threading.Thread(target=run_icon, daemon=True)
            self._icon_thread.start()
            logger.info("Status icon started in thread")

    def update_state(self, new_state: StatusIconState):
        """
        Update the icon to reflect a new state.

        Args:
            new_state: The new state to display
        """
        self.state = new_state
        if self._icon:
            try:
                # Update icon appearance
                self._icon.icon = self._get_icon_image()

                # Update tooltip/title
                description = self._state_descriptions.get(new_state, "Unknown state")
                self._icon.title = f"Dictation: {description}"

                # Update menu (will refresh on next open)
                self._icon.menu = self._setup_menu()

                logger.info(f"Updated status icon to: {new_state.name}")
            except Exception as e:
                logger.error(f"Failed to update status icon: {e}")

    def stop(self):
        """Stop the status icon."""
        if self._icon:
            try:
                self._icon.stop()
                logger.info("Status icon stopped")
            except Exception as e:
                logger.error(f"Error stopping status icon: {e}")

        # Wait for thread to end
        if self._icon_thread and self._icon_thread.is_alive():
            self._icon_thread.join(timeout=1.0)

    def set_sound_toggle_callback(
        self, callback: Callable[[bool], None], initial_state: bool = False
    ):
        """
        Set callback for toggling sound effects.

        Args:
            callback: Function to call when sounds are toggled (receives bool indicating if sounds are enabled)
            initial_state: Initial state of the sound toggle
        """
        self._sound_toggle_callback = callback
        self._sounds_enabled = initial_state
        # Update menu if icon already exists
        if self._icon:
            self._icon.menu = self._setup_menu()

    def set_language_callback(
        self, callback: Callable[[str], None], initial_language: str = "en"
    ):
        """
        Set callback for changing language.

        Args:
            callback: Function to call when language is changed (receives language code)
            initial_language: Initial language code
        """
        self._language_callback = callback
        if initial_language in self._languages:
            self._current_language = initial_language
        # Update menu if icon already exists
        if self._icon:
            self._icon.menu = self._setup_menu()


def get_global_icon():
    """Get the global icon instance for main thread access."""
    global _global_icon
    return _global_icon


def run_icon_on_macos():
    """
    Run the icon loop on macOS main thread.
    This should be called from the main thread after the app is set up.
    """
    global _global_icon
    if _global_icon and platform.system() == "Darwin":
        try:
            logger.info("Running status icon on main thread (macOS)")
            _global_icon.run()
        except Exception as e:
            logger.error(f"Error running icon on main thread: {e}")

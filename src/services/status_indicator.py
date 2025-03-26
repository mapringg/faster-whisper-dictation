import logging
import platform
import threading
import time
from collections.abc import Callable
from enum import Enum

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

logger = logging.getLogger(__name__)

# Global variable to hold icon instance for main thread access
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

    # Class constants
    ICON_WIDTH = 22
    ICON_HEIGHT = 22
    ICON_PADDING = 4

    def __init__(self, on_exit: Callable | None = None):
        """
        Initialize the status icon.

        Args:
            on_exit: Optional callback to run when exit is selected from the menu
        """
        self.on_exit = on_exit
        self._current_state = StatusIconState.READY
        self._icon = None
        self._icon_lock = threading.Lock()
        self._is_initialized = False
        self._sound_toggle_callback = None
        self._sounds_enabled = False
        self._language_callback = None
        self._current_language = "en"  # Default to English
        self._transcriber_callback = None
        self._current_transcriber = "openai"  # Default to OpenAI
        self._transcribers = {
            "openai": "OpenAI",
            "groq": "Groq",
        }
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

    def _create_base_image(self) -> Image.Image:
        """Create a base transparent image for icons."""
        return Image.new("RGBA", (self.ICON_WIDTH, self.ICON_HEIGHT), (0, 0, 0, 0))

    def _get_icon_image(self):
        """Get the current static image for the current state."""
        color = self._state_colors.get(self._current_state, (100, 100, 100))

        # For error state, use a special image with X mark
        if self._current_state == StatusIconState.ERROR:
            return self._create_error_image()

        # Otherwise create a simple colored circle
        return self._create_static_image(color)

    def _create_static_image(self, color) -> Image.Image:
        """Create a simple colored circle image for the icon."""
        image = self._create_base_image()
        dc = ImageDraw.Draw(image)
        dc.ellipse(
            [
                (self.ICON_PADDING, self.ICON_PADDING),
                (
                    self.ICON_WIDTH - self.ICON_PADDING,
                    self.ICON_HEIGHT - self.ICON_PADDING,
                ),
            ],
            fill=color,
        )
        # Clean up draw object
        del dc
        return image

    def _create_error_image(self):
        """Create an error image with an X mark."""
        image = self._create_base_image()
        dc = ImageDraw.Draw(image)

        # Draw circle background
        rect = [
            (self.ICON_PADDING, self.ICON_PADDING),
            (
                self.ICON_WIDTH - self.ICON_PADDING,
                self.ICON_HEIGHT - self.ICON_PADDING,
            ),
        ]
        dc.ellipse(rect, fill=(100, 100, 100))

        # Draw X mark
        line_color = (255, 255, 255)
        line_width = 2
        margin = self.ICON_PADDING + 3  # Additional margin for X inside circle

        dc.line(
            [(margin, margin), (self.ICON_WIDTH - margin, self.ICON_HEIGHT - margin)],
            fill=line_color,
            width=line_width,
        )
        dc.line(
            [(self.ICON_WIDTH - margin, margin), (margin, self.ICON_HEIGHT - margin)],
            fill=line_color,
            width=line_width,
        )

        # Delete the draw object to free memory
        del dc

        return image

    def _get_menu_title(self):
        """Get the current state description for the menu."""
        return f"Status: {self._state_descriptions.get(self._current_state, 'Unknown')}"

    def _select_english(self):
        """Select English language."""
        self._select_language("en")
        return False  # Don't close the menu

    def _select_thai(self):
        """Select Thai language."""
        self._select_language("th")
        return False  # Don't close the menu

    def _select_openai(self):
        """Select OpenAI transcriber."""
        self._select_transcriber("openai")
        return False  # Don't close the menu

    def _select_groq(self):
        """Select Groq transcriber."""
        self._select_transcriber("groq")
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

    def _select_transcriber(self, transcriber_id):
        """Handle transcriber selection from the menu."""
        if self._transcriber_callback and transcriber_id != self._current_transcriber:
            self._current_transcriber = transcriber_id
            self._transcriber_callback(transcriber_id)
            # Update menu
            if self._icon:
                self._icon.menu = self._setup_menu()
        return False  # Don't close the menu

    def _add_transcriber_menu_items(self, menu_items: list):
        """Add transcriber selection items to the menu."""
        if not self._transcriber_callback:
            return

        # Add transcriber header
        menu_items.append(
            MenuItem(
                "Transcriber",
                None,
                enabled=False,
            )
        )

        # Add transcriber options with non-shifting prefix checkmark
        menu_items.append(
            MenuItem(
                f"{('✓' if self._current_transcriber == 'openai' else '   ')} OpenAI",
                self._select_openai,
            )
        )
        menu_items.append(
            MenuItem(
                f"{('✓' if self._current_transcriber == 'groq' else '   ')} Groq",
                self._select_groq,
            )
        )

        menu_items.append(Menu.SEPARATOR)

    def _add_language_menu_items(self, menu_items: list):
        """Add language selection items to the menu."""
        if not self._language_callback:
            return

        # Add language header
        menu_items.append(
            MenuItem(
                "Language",
                None,
                enabled=False,
            )
        )

        # Add language options with non-shifting prefix checkmark
        menu_items.append(
            MenuItem(
                f"{('✓' if self._current_language == 'en' else '   ')} English",
                self._select_english,
            )
        )
        menu_items.append(
            MenuItem(
                f"{('✓' if self._current_language == 'th' else '   ')} Thai",
                self._select_thai,
            )
        )

        menu_items.append(Menu.SEPARATOR)

    def _add_sound_menu_item(self, menu_items: list):
        """Add sound toggle item to the menu."""
        if not self._sound_toggle_callback:
            return

        sound_text = "Enable Sounds" if not self._sounds_enabled else "Disable Sounds"
        menu_items.append(MenuItem(sound_text, self._toggle_sounds))

    def _setup_menu(self):
        """Create the right-click menu for the icon."""
        menu_items = []

        self._add_transcriber_menu_items(menu_items)
        self._add_language_menu_items(menu_items)
        self._add_sound_menu_item(menu_items)

        # Always add exit option
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

    def _exit(self):
        """Handle exit from the menu."""
        logger.info("Exit selected from status icon menu")

        # Stop icon if possible (for non-macOS platforms)
        try:
            if self._icon and platform.system() != "Darwin":
                logger.info("Stopping icon directly")
                # This won't work on macOS, but helps on other platforms
                self._icon.stop()
        except Exception as e:
            logger.warning(f"Failed to stop icon directly: {e}")

        # Call the exit callback last
        if self.on_exit:
            logger.info("Calling application exit handler")
            self.on_exit()

        # This tells pystray to exit (though it may not take effect on all platforms)
        return True

    def start(self):
        """Start the status icon by creating the instance."""
        if self._icon:
            logger.warning("Status icon instance already created")
            return

        # Create icon instance in the current thread (should be main thread)
        system = platform.system()
        icon_title = "Dictation Assistant"
        if system == "Darwin":
            icon_title = "Dictation"  # Shorter title for macOS menu bar

        try:
            self._icon = Icon(
                name="Dictation Assistant",
                icon=self._get_icon_image(),
                title=icon_title,  # Use title for tooltip/initial display
                menu=self._setup_menu(),
            )

            global _global_icon
            _global_icon = self._icon
            self._is_initialized = True
            logger.info("Status icon instance created successfully.")

            # Start a thread to log backend info after initialization
            def log_backend_info():
                time.sleep(1)  # Wait for icon to initialize
                try:
                    if hasattr(self._icon, "backend"):
                        logger.info(
                            f"Status icon using backend: {self._icon.backend.__class__.__name__}"
                        )
                    else:
                        logger.warning("Status icon backend attribute not available")
                except Exception as e:
                    logger.error(f"Error getting backend info: {e}")

            backend_thread = threading.Thread(target=log_backend_info, daemon=True)
            backend_thread.start()

        except Exception as e:
            logger.error(f"Failed to create status icon instance: {e}")
            self._icon = None
            _global_icon = None
            self._is_initialized = False

    def _update_icon_state_internal(self, new_state: StatusIconState):
        """Internal method to update icon appearance and tooltip."""
        if self._icon is None:
            logger.warning("Cannot update icon state: icon instance is None")
            return

        try:
            # Create new icon image first
            new_icon = self._get_icon_image()

            # Update icon image
            self._icon.icon = new_icon

            # Update tooltip/title
            description = self._state_descriptions.get(new_state, "Unknown state")
            # pystray uses 'title' for the tooltip text
            self._icon.title = f"Dictation: {description}"

            # Update menu (refreshes when next opened)
            self._icon.menu = self._setup_menu()

            # Force an update on Linux/GNOME by triggering a menu refresh
            if platform.system() == "Linux":
                try:
                    # Small delay to allow the icon update to propagate
                    time.sleep(0.1)
                    # Force menu update to refresh icon
                    self._icon.update_menu()
                except Exception as e:
                    logger.warning(f"Failed to force Linux icon refresh: {e}")

            logger.info(f"Updated status icon state to: {new_state.name}")
        except Exception as e:
            # Catch potential errors if the icon backend is misbehaving
            logger.error(f"Failed to update status icon appearance: {e}")

    def update_state(self, new_state: StatusIconState):
        """Update the status icon state and appearance."""
        with self._icon_lock:
            if not self._is_initialized or self._icon is None:
                logger.warning("Status icon not initialized, cannot update state.")
                return

            if self._current_state == new_state:
                return  # No state change needed

            logger.info(
                f"Updating status icon state from {self._current_state} to {new_state} on {platform.system()}"
            )
            self._current_state = new_state

            # Call the internal update method, regardless of platform
            self._update_icon_state_internal(new_state)

    def stop(self):
        """Clean up resources when stopping the status icon."""
        logger.info("Stopping status icon")
        global _global_icon
        with self._icon_lock:
            if self._icon:
                try:
                    # Attempt to stop the icon. This might block or fail depending
                    # on the state and platform, especially if called from a thread
                    # other than the one running the icon.
                    logger.info("Attempting to stop icon instance...")
                    self._icon.stop()
                    logger.info("Icon stopped successfully.")
                except Exception as e:
                    # Log error but continue cleanup
                    logger.error(f"Error stopping icon: {e}")
                finally:
                    # Ensure icon reference is cleared
                    self._icon = None
                    _global_icon = None
                    self._is_initialized = False
            else:
                # Ensure global ref is cleared even if self._icon was already None
                _global_icon = None
                self._is_initialized = False

        # Force garbage collection
        import gc

        gc.collect()
        logger.info("Status icon cleanup completed.")

    def _validate_callback(self, callback: Callable, name: str) -> bool:
        """
        Validate that a callback is callable.

        Args:
            callback: The callback to validate
            name: Name of the callback for error logging

        Returns:
            bool: True if callback is valid, False otherwise
        """
        if not callable(callback):
            logger.error(f"{name} callback must be callable")
            return False
        return True

    def set_sound_toggle_callback(
        self, callback: Callable[[bool], None], initial_state: bool = False
    ):
        """
        Set callback for toggling sound effects.

        Args:
            callback: Function to call when sounds are toggled (receives bool indicating if sounds are enabled)
            initial_state: Initial state of the sound toggle
        """
        if not self._validate_callback(callback, "Sound toggle"):
            return

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
        if not self._validate_callback(callback, "Language"):
            return

        self._language_callback = callback
        if initial_language in self._languages:
            self._current_language = initial_language
        else:
            logger.warning(
                f"Unknown language: {initial_language}, defaulting to English"
            )
            self._current_language = "en"

        # Update menu if icon already exists
        if self._icon:
            self._icon.menu = self._setup_menu()

    def set_transcriber_callback(
        self, callback: Callable[[str], None], initial_transcriber: str = "openai"
    ):
        """
        Set callback for changing transcriber.

        Args:
            callback: Function to call when transcriber is changed (receives transcriber id)
            initial_transcriber: Initial transcriber id
        """
        if not self._validate_callback(callback, "Transcriber"):
            return

        self._transcriber_callback = callback
        if initial_transcriber in self._transcribers:
            self._current_transcriber = initial_transcriber
        else:
            logger.warning(
                f"Unknown transcriber: {initial_transcriber}, defaulting to OpenAI"
            )
            self._current_transcriber = "openai"

        # Update menu if icon already exists
        if self._icon:
            self._icon.menu = self._setup_menu()


def get_global_icon():
    """Get the global icon instance for main thread access."""
    global _global_icon
    return _global_icon


def run_icon_on_main_thread():
    """
    Run the icon loop on the main thread.
    This should be called from the main thread after the app is set up.
    It will block until the icon is stopped or exits.
    """
    global _global_icon
    if _global_icon:
        try:
            logger.info("Running status icon loop on main thread...")
            # This call blocks until the icon is stopped or the exit menu item returns True
            _global_icon.run()
            logger.info("Status icon main thread loop exited.")
        except Exception as e:
            logger.error(f"Error running icon on main thread: {e}")
        finally:
            # Clean up global reference after the loop finishes or errors out
            _global_icon = None
            logger.info("Status icon global reference cleared after run.")
    else:
        logger.warning("Cannot run icon: global icon instance is None.")

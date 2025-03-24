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
        """Start the status icon in a separate thread."""
        if self._icon:
            logger.warning("Status icon is already running")
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

            icon_thread = threading.Thread(target=run_icon, daemon=True)
            icon_thread.start()
            logger.info("Status icon started in thread")

    def _update_macos_icon(self, new_state: StatusIconState):
        """Update the icon appearance on macOS."""
        if self._icon is None:
            return

        try:
            # Update icon appearance without recreating the icon
            self._icon.icon = self._get_icon_image()
            self._icon.title = (
                f"Dictation: {self._state_descriptions.get(new_state, 'Unknown state')}"
            )
            self._icon.menu = self._setup_menu()
            logger.info(f"Updated macOS status icon to: {new_state.name}")
        except Exception as e:
            logger.error(f"Failed to update macOS status icon: {e}")

    def _update_other_platform_icon(self, new_state: StatusIconState):
        """Update the icon appearance on non-macOS platforms."""
        if self._icon is not None:
            self._update_icon_appearance()
        elif not self._is_initialized:
            self._initialize_icon()

    def update_state(self, new_state: StatusIconState):
        """Update the status icon state and appearance."""
        with self._icon_lock:
            if self._current_state == new_state:
                return  # No state change needed

            logger.info(
                f"Updating status icon state from {self._current_state} to {new_state}"
            )
            self._current_state = new_state

            # Use platform-specific update method
            if platform.system() == "Darwin":
                self._update_macos_icon(new_state)
            else:
                self._update_other_platform_icon(new_state)

    def _initialize_icon(self):
        """Initialize the status icon only if not already initialized."""
        with self._icon_lock:
            if self._is_initialized:
                return

            try:
                # Create the icon and set up the menu
                self._setup_icon()
                self._is_initialized = True
                logger.info("Status icon initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize status icon: {str(e)}")
                self._is_initialized = False

    def _setup_icon(self):
        """Set up the status icon and menu."""
        if self._icon is not None:
            return

        try:
            # Create icon instance
            self._icon = Icon(
                name="Dictation Assistant",
                icon=self._get_icon_image(),
                title=self._get_menu_title(),
                menu=self._setup_menu(),
            )

            logger.info("Status icon created (will run on main thread)")
        except Exception as e:
            logger.error(f"Error setting up status icon: {str(e)}")
            self._icon = None

    def _update_icon_appearance(self):
        """Update the icon appearance based on the current state."""
        if self._icon:
            try:
                # Update icon appearance
                self._icon.icon = self._get_icon_image()

                # Update tooltip/title
                description = self._state_descriptions.get(
                    self._current_state, "Unknown state"
                )
                self._icon.title = f"Dictation: {description}"

                # Update menu (will refresh on next open)
                self._icon.menu = self._setup_menu()

                logger.info(f"Updated status icon to: {self._current_state.name}")
            except Exception as e:
                logger.error(f"Failed to update status icon: {e}")

    def stop(self):
        """Clean up resources when stopping the status icon."""
        logger.info("Stopping status icon")

        with self._icon_lock:
            # Clean up the icon - platform specific handling
            global _global_icon
            if self._icon:
                try:
                    logger.info("Stopping icon instance")
                    # On macOS, we may not be able to stop the icon if it's running in the main thread
                    if platform.system() != "Darwin":
                        self._icon.stop()
                        logger.info("Icon stopped successfully")
                    else:
                        # On macOS, we can sometimes remove the reference without calling stop
                        # since the icon will be exited by the main thread
                        logger.info("Skipping icon.stop() on macOS")
                except Exception as e:
                    logger.error(f"Error stopping icon: {e}")
                finally:
                    # Ensure icon is set to None to break reference cycles
                    self._icon = None

            # Reset variables
            _global_icon = None  # Clear global reference too
            self._is_initialized = False

            # Force garbage collection to clean up any lingering references
            import gc

            gc.collect()

            logger.info("Status icon cleanup completed successfully")

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


def run_icon_on_macos():
    """
    Run the icon loop on macOS main thread.
    This should be called from the main thread after the app is set up.
    """
    global _global_icon
    if _global_icon and platform.system() == "Darwin":
        try:
            logger.info("Running status icon on main thread (macOS)")
            # Run the icon, which will block until icon.stop() is called
            # or until the menu's exit function returns True
            _global_icon.run()
            logger.info("Status icon main thread loop exited")
        except KeyboardInterrupt:
            logger.info("Status icon interrupted by keyboard")
        except Exception as e:
            logger.error(f"Error running icon on main thread: {e}")
        finally:
            # Clean up global reference to prevent memory leaks
            _global_icon = None
            logger.info("Status icon global reference cleared")

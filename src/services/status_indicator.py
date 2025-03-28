import logging
import platform
import queue
import threading
import time
from collections.abc import Callable
from enum import Enum

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

from ..core import constants as const

logger = logging.getLogger(__name__)


class StatusIconState(Enum):
    """States for the status icon."""

    READY = "ready"  # Green
    RECORDING = "recording"  # Red
    TRANSCRIBING = "transcribing"  # Yellow
    REPLAYING = "replaying"  # Blue
    ERROR = "error"  # Gray


class StatusIcon:
    """System tray icon that reflects the application state."""

    # Class constants - now imported from core.constants
    ICON_WIDTH = const.ICON_WIDTH_PX
    ICON_HEIGHT = const.ICON_HEIGHT_PX
    ICON_PADDING = const.ICON_PADDING_PX

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
        self.update_queue = queue.Queue()
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
            StatusIconState.READY: const.STATE_DESC_READY,
            StatusIconState.RECORDING: const.STATE_DESC_RECORDING,
            StatusIconState.TRANSCRIBING: const.STATE_DESC_TRANSCRIBING,
            StatusIconState.REPLAYING: const.STATE_DESC_REPLAYING,
            StatusIconState.ERROR: const.STATE_DESC_ERROR,
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
            # Queue menu update
            self.update_queue.put({"action": "update_menu"})
        return False  # Don't close the menu

    def _select_transcriber(self, transcriber_id):
        """Handle transcriber selection from the menu."""
        if self._transcriber_callback and transcriber_id != self._current_transcriber:
            self._current_transcriber = transcriber_id
            self._transcriber_callback(transcriber_id)
            # Queue menu update
            self.update_queue.put({"action": "update_menu"})
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

        # Add refresh audio devices option
        menu_items.append(
            MenuItem("Refresh Audio Devices", self._refresh_audio_devices)
        )

    def _setup_menu(self):
        """Create the right-click menu for the icon."""
        menu_items = []

        self._add_transcriber_menu_items(menu_items)
        self._add_language_menu_items(menu_items)
        self._add_sound_menu_item(menu_items)

        # Always add exit option
        menu_items.append(MenuItem("Exit", self._exit))

        return Menu(*menu_items)

    def _refresh_audio_devices(self):
        """Refresh audio devices and update the menu."""
        # Queue a message to refresh audio devices
        self.update_queue.put({"action": "refresh_devices"})
        return False  # Don't close the menu

    def _toggle_sounds(self):
        """Toggle sound effects and update the menu."""
        if self._sound_toggle_callback:
            self._sounds_enabled = not self._sounds_enabled
            self._sound_toggle_callback(self._sounds_enabled)
            # Queue menu update
            self.update_queue.put({"action": "update_menu"})
        return False  # Don't close the menu

    def _exit(self):
        """Handle exit from the menu."""
        logger.info("Exit selected from status icon menu")

        # Queue a shutdown message first
        self.update_queue.put({"action": "shutdown"})

        # Call the exit callback
        if self.on_exit:
            logger.info("Calling application exit handler")
            self.on_exit()

        # Return False to let the main loop handle shutdown
        return False

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

            self._is_initialized = True
            logger.info("Status icon instance created successfully.")

            # Set up periodic queue processing on the appropriate main thread mechanism
            if system == "Linux":
                try:
                    # Use GLib.timeout_add if available (for GTK-based backend)
                    import gi

                    gi.require_version("GLib", "2.0")
                    from gi.repository import GLib

                    # Process queue every 100ms
                    GLib.timeout_add(100, self._process_queue)
                    logger.info("Using GLib.timeout_add for queue processing")
                except (ImportError, ValueError):
                    logger.warning(
                        "GLib not available, using fallback for queue processing"
                    )
            elif system == "Darwin":
                try:
                    # Use AppKit timer for macOS
                    import AppKit
                    import Foundation

                    # Create a timer to process the queue
                    self._timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                        0.1,  # 100ms interval
                        self._icon,  # Target object
                        "processQueue:",  # Selector name
                        None,  # User info
                        True,  # Repeats
                    )
                    # Add method to icon instance dynamically (Python allows this)
                    self._icon.processQueue_ = lambda sender: self._process_queue()
                    logger.info("Using AppKit timer for queue processing")
                except ImportError:
                    logger.warning(
                        "AppKit not available, using fallback for queue processing"
                    )
            else:
                # For Windows or other platforms
                # We'll rely on run_icon_on_main_thread implementation
                logger.info("Using generic queue processing for this platform")

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

    def _update_icon_state_internal(
        self, new_state: StatusIconState, error_msg: str | None = None
    ):
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
            if new_state == StatusIconState.ERROR and error_msg:
                description = f"Error: {error_msg}"
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

            # Queue the update instead of calling directly
            self.update_queue.put(
                {
                    "action": "set_state",
                    "state": new_state,
                    "error_msg": None,  # Error messages are handled in _process_queue
                }
            )

    def _process_queue(self):
        """
        Process a single item from the update queue on the main thread.
        This method should be called periodically from the main thread.
        """
        try:
            # Get one message from the queue, non-blocking
            try:
                message = self.update_queue.get(block=False)
            except queue.Empty:
                # No messages, just return and we'll check again later
                return True  # Continue processing

            # Process the message
            if message["action"] == "set_state":
                self._update_icon_state_internal(message["state"])
            elif message["action"] == "update_menu":
                if self._icon:
                    self._icon.menu = self._setup_menu()
            elif message["action"] == "refresh_devices":
                # Import here to avoid circular imports
                from ..core.utils import refresh_devices

                # Refresh devices and provide feedback via icon state
                current_state = self._current_state
                self._update_icon_state_internal(
                    StatusIconState.TRANSCRIBING
                )  # Use as "busy" indicator

                # Perform the refresh
                success = refresh_devices()

                # Brief delay to show the busy state
                import time

                time.sleep(0.5)

                # Show error state briefly if failed
                if not success:
                    self._update_icon_state_internal(StatusIconState.ERROR)
                    time.sleep(1)

                # Return to previous state
                self._update_icon_state_internal(current_state)
            elif message["action"] == "shutdown":
                # Handle shutdown request
                logger.info("Processing shutdown request from queue")
                if self._icon:
                    try:
                        self._icon.stop()
                    except Exception as e:
                        logger.error(f"Error stopping icon: {e}")
                return False  # Stop processing

            # Mark task as done
            self.update_queue.task_done()

        except Exception as e:
            logger.error(f"Error processing icon queue: {e}")

        return True  # Continue processing

    def stop(self):
        """Clean up resources when stopping the status icon."""
        logger.info("Stopping status icon")
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
                    self._is_initialized = False
            else:
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


def run_icon_on_main_thread(icon_instance):
    """
    Run the icon loop on the main thread.
    This should be called from the main thread after the app is set up.
    It will block until the icon is stopped or exits.

    Args:
        icon_instance: The pystray.Icon instance to run
    """
    if icon_instance:
        try:
            logger.info("Running status icon loop on main thread...")

            # Create and start a thread to process queue while icon is running
            should_continue = [True]  # Use a list for mutable reference

            def process_queue_wrapper():
                while should_continue[0]:
                    if icon_instance and hasattr(icon_instance, "_process_queue"):
                        if not icon_instance._process_queue():
                            should_continue[0] = False
                            break
                    time.sleep(0.1)  # 100ms interval

            queue_thread = threading.Thread(target=process_queue_wrapper, daemon=True)
            queue_thread.start()

            # This call blocks until the icon is stopped
            icon_instance.run()

            # Signal queue processing thread to stop
            should_continue[0] = False
            queue_thread.join(timeout=1.0)

            logger.info("Status icon main thread loop exited.")
        except Exception as e:
            logger.error(f"Error running icon on main thread: {e}")
    else:
        logger.warning("Cannot run icon: global icon instance is None.")

import logging
import platform
import threading
import time
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
    ANIMATION_SPEED = 0.2

    def __init__(self, on_exit: Callable | None = None):
        """
        Initialize the status icon.

        Args:
            on_exit: Optional callback to run when exit is selected from the menu
        """
        self.on_exit = on_exit
        self._current_state = StatusIconState.READY
        self._icon = None
        self._animation_thread = None
        self._animation_running = False
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

        # Frame cache for animations
        self._animation_frames = {}
        self._current_frame = 0
        self._animation_speed = 0.2  # seconds between frames

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

        # Initialize animation frames
        self._init_animation_frames()

    def _init_animation_frames(self):
        """Initialize animation frames for each state."""
        # Ready state (pulsing green circle)
        self._animation_frames[StatusIconState.READY] = self._create_pulse_animation(
            (0, 150, 0), 6
        )

        # Recording state (blinking red circle)
        self._animation_frames[StatusIconState.RECORDING] = (
            self._create_blink_animation((200, 0, 0), 4)
        )

        # Transcribing state (spinning yellow circle)
        self._animation_frames[StatusIconState.TRANSCRIBING] = (
            self._create_spin_animation((200, 150, 0), 8)
        )

        # Replaying state (pulsing blue)
        self._animation_frames[StatusIconState.REPLAYING] = (
            self._create_pulse_animation((0, 0, 200), 6)
        )

        # Error state (gray X mark)
        self._animation_frames[StatusIconState.ERROR] = [self._create_error_image()]

    def _create_base_image(self) -> Image.Image:
        """Create a base transparent image for icons."""
        return Image.new("RGBA", (self.ICON_WIDTH, self.ICON_HEIGHT), (0, 0, 0, 0))

    def _create_pulse_animation(self, color, num_frames=6):
        """Create a pulsing animation with varying opacity."""
        frames = []

        for i in range(num_frames):
            # Calculate opacity based on sine wave pattern
            factor = 0.5 + 0.5 * (i / (num_frames - 1))  # 0.5 to 1.0 and back
            current_color = (color[0], color[1], color[2], int(255 * factor))

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
                fill=current_color,
            )
            frames.append(image)

        # Add frames in reverse for smooth pulsing (except last frame to avoid duplication)
        frames.extend(frames[:-1][::-1])
        return frames

    def _create_blink_animation(self, color, num_frames=4):
        """Create a blinking animation that alternates between full color and transparent."""
        frames = []

        # Full color frame
        image1 = self._create_base_image()
        dc1 = ImageDraw.Draw(image1)
        dc1.ellipse(
            [
                (self.ICON_PADDING, self.ICON_PADDING),
                (
                    self.ICON_WIDTH - self.ICON_PADDING,
                    self.ICON_HEIGHT - self.ICON_PADDING,
                ),
            ],
            fill=color,
        )

        # Semi-transparent frame
        image2 = self._create_base_image()
        dc2 = ImageDraw.Draw(image2)
        transparent_color = (color[0], color[1], color[2], 100)
        dc2.ellipse(
            [
                (self.ICON_PADDING, self.ICON_PADDING),
                (
                    self.ICON_WIDTH - self.ICON_PADDING,
                    self.ICON_HEIGHT - self.ICON_PADDING,
                ),
            ],
            fill=transparent_color,
        )

        # Alternate between frames
        for i in range(num_frames):
            if i % 2 == 0:
                frames.append(image1)
            else:
                frames.append(image2)

        return frames

    def _create_spin_animation(self, color, num_frames=8):
        """Create a spinning animation with an arc that rotates."""
        frames = []

        for i in range(num_frames):
            image = self._create_base_image()
            dc = ImageDraw.Draw(image)

            # Draw base circle (semi-transparent)
            base_color = (color[0], color[1], color[2], 100)
            dc.ellipse(
                [
                    (self.ICON_PADDING, self.ICON_PADDING),
                    (
                        self.ICON_WIDTH - self.ICON_PADDING,
                        self.ICON_HEIGHT - self.ICON_PADDING,
                    ),
                ],
                fill=base_color,
            )

            # Draw spinning arc
            start_angle = (i * 45) % 360
            end_angle = (start_angle + 90) % 360

            # Ensure proper order of angles for arc drawing
            if start_angle > end_angle:
                start_angle, end_angle = end_angle, start_angle

            dc.pieslice(
                [
                    (self.ICON_PADDING, self.ICON_PADDING),
                    (
                        self.ICON_WIDTH - self.ICON_PADDING,
                        self.ICON_HEIGHT - self.ICON_PADDING,
                    ),
                ],
                start=start_angle,
                end=end_angle,
                fill=color,
            )
            frames.append(image)

        return frames

    def _create_error_image(self):
        """Create an error image with an X mark."""
        image = self._create_base_image()
        dc = ImageDraw.Draw(image)

        # Draw circle background
        dc.ellipse(
            [
                (self.ICON_PADDING, self.ICON_PADDING),
                (
                    self.ICON_WIDTH - self.ICON_PADDING,
                    self.ICON_HEIGHT - self.ICON_PADDING,
                ),
            ],
            fill=(100, 100, 100),
        )

        # Draw X mark
        line_color = (255, 255, 255)
        line_width = 2
        margin = self.ICON_PADDING + 3  # Additional margin for X inside circle
        dc.line(
            [
                (margin, margin),
                (self.ICON_WIDTH - margin, self.ICON_HEIGHT - margin),
            ],
            fill=line_color,
            width=line_width,
        )
        dc.line(
            [
                (self.ICON_WIDTH - margin, margin),
                (margin, self.ICON_HEIGHT - margin),
            ],
            fill=line_color,
            width=line_width,
        )

        return image

    def _get_icon_image(self):
        """Get the current frame of the animation for the current state."""
        frames = self._animation_frames.get(self._current_state, [])
        if not frames:
            # Fallback to static image if no animation frames
            color = self._state_colors.get(self._current_state, (100, 100, 100))
            return self._create_static_image(color)

        if len(frames) == 1:
            return frames[0]  # Static image (single frame)

        # Return current frame from animation
        frame_idx = self._current_frame % len(frames)
        return frames[frame_idx]

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
        self._stop_animation()
        if self.on_exit:
            self.on_exit()
        return True  # This tells pystray to exit

    def _run_animation(self):
        """Run the animation loop in a separate thread."""
        try:
            # Use a local reference to prevent memory leaks
            frames_cache = {}

            while self._animation_running:
                # Update the frame counter
                self._current_frame += 1

                # Limit animation frames to prevent memory leaks
                if self._current_frame > 1000:
                    self._current_frame = 0

                # Update the icon with the new frame
                if self._icon:
                    # Get the current state's frames
                    if (
                        self._current_state not in frames_cache
                        and self._current_state in self._animation_frames
                    ):
                        # Make a shallow copy to avoid memory leaks
                        frames_cache[self._current_state] = self._animation_frames[
                            self._current_state
                        ]

                    # Update icon
                    try:
                        self._icon.icon = self._get_icon_image()
                    except Exception as icon_error:
                        logger.error(f"Error updating icon image: {icon_error}")

                # Free memory by clearing any unused state frames from cache
                current_states = {self._current_state}
                for state in list(frames_cache.keys()):
                    if state not in current_states:
                        del frames_cache[state]

                # Sleep until next frame
                time.sleep(self._animation_speed)
        except Exception as e:
            logger.error(f"Error in animation thread: {e}")
        finally:
            # Clean up before exiting thread
            frames_cache.clear()

    def _start_animation(self):
        """Start the animation thread if not already running."""
        if self._animation_thread and self._animation_thread.is_alive():
            return

        self._animation_running = True
        self._animation_thread = threading.Thread(
            target=self._run_animation, daemon=True
        )
        self._animation_thread.start()
        logger.info("Animation thread started")

    def _stop_animation(self):
        """Stop the animation thread with proper cleanup."""
        self._animation_running = False
        if self._animation_thread and self._animation_thread.is_alive():
            try:
                self._animation_thread.join(timeout=1.0)
                logger.info("Animation thread stopped")
            except Exception:
                logger.warning(
                    "Animation thread did not stop gracefully within timeout"
                )

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

        # Start animation
        self._start_animation()

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

            self._animation_thread = threading.Thread(target=run_icon, daemon=True)
            self._animation_thread.start()
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

            # Start animation
            self._start_animation()

            logger.info("Status icon created (will run on main thread)")
        except Exception as e:
            logger.error(f"Error setting up status icon: {str(e)}")
            self._icon = None

    def _update_icon_appearance(self):
        """Update the icon appearance based on the current state."""
        if self._icon:
            try:
                # Reset frame counter for new animation
                self._current_frame = 0

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
        with self._icon_lock:
            # First stop the animation thread
            self._animation_running = False
            if self._animation_thread and self._animation_thread.is_alive():
                try:
                    self._animation_thread.join(timeout=1.0)
                    logger.info("Animation thread joined successfully")
                except Exception as e:
                    logger.error(f"Error joining animation thread: {e}")

            # Clear animation frame cache to free memory
            for state in list(self._animation_frames.keys()):
                self._animation_frames[state] = []

            # Clean up the icon
            if self._icon:
                try:
                    self._icon.stop()
                    logger.info("Icon stopped successfully")
                except Exception as e:
                    logger.error(f"Error stopping icon: {e}")

            # Reset variables
            self._icon = None
            self._is_initialized = False
            self._current_frame = 0

            # Force garbage collection to clean up any lingering references
            import gc

            gc.collect()
            logger.info("Garbage collection performed during status icon cleanup")

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
            _global_icon.run()
        except Exception as e:
            logger.error(f"Error running icon on main thread: {e}")

import logging
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
    READY = "ready"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    REPLAYING = "replaying"
    ERROR = "error"


class StatusIcon:
    """System tray icon that reflects and controls the application state."""

    def __init__(self, on_exit: Callable | None = None):
        self.on_exit = on_exit
        self.is_initialized = False
        self._icon: Icon | None = None
        self._current_state = StatusIconState.READY
        self._current_language = "en"
        self._current_transcriber = "openai"
        self._sounds_enabled = False
        self._language_callback: Callable[[str], None] | None = None
        self._transcriber_callback: Callable[[str], None] | None = None
        self._sound_toggle_callback: Callable[[bool], None] | None = None
        self.update_queue = queue.Queue()

        self._state_config = {
            StatusIconState.READY: {
                "color": (0, 150, 0),
                "desc": const.STATE_DESC_READY,
            },
            StatusIconState.RECORDING: {
                "color": (200, 0, 0),
                "desc": const.STATE_DESC_RECORDING,
            },
            StatusIconState.TRANSCRIBING: {
                "color": (200, 150, 0),
                "desc": const.STATE_DESC_TRANSCRIBING,
            },
            StatusIconState.REPLAYING: {
                "color": (0, 0, 200),
                "desc": const.STATE_DESC_REPLAYING,
            },
            StatusIconState.ERROR: {
                "color": (100, 100, 100),
                "desc": const.STATE_DESC_ERROR,
            },
        }
        self._languages = {"en": "English", "th": "Thai"}
        self._transcribers = {"openai": "OpenAI", "groq": "Groq", "local": "Local"}

    def _create_icon_image(self, color: tuple[int, int, int]) -> Image.Image:
        image = Image.new(
            "RGBA", (const.ICON_WIDTH_PX, const.ICON_HEIGHT_PX), (0, 0, 0, 0)
        )
        dc = ImageDraw.Draw(image)
        padding = const.ICON_PADDING_PX
        dc.ellipse(
            [
                (padding, padding),
                (const.ICON_WIDTH_PX - padding, const.ICON_HEIGHT_PX - padding),
            ],
            fill=color,
        )
        return image

    def _setup_menu(self) -> Menu:
        def create_radio_menu(
            title: str, options: dict, current_value: str, callback: Callable
        ):
            def on_select(value):
                return lambda: callback(value)

            items = [
                MenuItem(
                    label,
                    on_select(key),
                    checked=lambda item, k=key: current_value == k,
                    radio=True,
                )
                for key, label in options.items()
            ]
            return MenuItem(title, Menu(*items))

        transcriber_menu = create_radio_menu(
            "Transcriber",
            self._transcribers,
            self._current_transcriber,
            self._select_transcriber,
        )
        language_menu = create_radio_menu(
            "Language", self._languages, self._current_language, self._select_language
        )

        sound_item = MenuItem(
            "Disable Sounds" if self._sounds_enabled else "Enable Sounds",
            self._toggle_sounds,
        )
        refresh_item = MenuItem("Refresh Audio Devices", self._refresh_audio_devices)
        exit_item = MenuItem("Exit", self._exit)

        return Menu(
            transcriber_menu,
            language_menu,
            Menu.SEPARATOR,
            sound_item,
            refresh_item,
            Menu.SEPARATOR,
            exit_item,
        )

    def start(self):
        try:
            self._icon = Icon(
                "Dictation",
                icon=self._create_icon_image(
                    self._state_config[self._current_state]["color"]
                ),
                title=f"Dictation: {self._state_config[self._current_state]['desc']}",
                menu=self._setup_menu(),
            )
            self.is_initialized = True
            logger.info("Status icon instance created.")
        except Exception as e:
            logger.error(f"Failed to create status icon: {e}")
            self.is_initialized = False

    def stop_icon(self):
        """Thread-safe method to stop the icon."""
        self.update_queue.put({"action": "shutdown"})

    def update_state(self, new_state: StatusIconState):
        if self._current_state != new_state:
            self._current_state = new_state
            self.update_queue.put({"action": "update_state", "state": new_state})

    def _process_queue(self) -> bool:
        """Process items from the update queue. Returns False to stop processing."""
        try:
            message = self.update_queue.get_nowait()
            action = message.get("action")

            if action == "shutdown":
                if self._icon:
                    self._icon.stop()
                return False  # Stop processing
            if not self._icon:
                return True

            if action == "update_state":
                state = message["state"]
                config = self._state_config[state]
                self._icon.icon = self._create_icon_image(config["color"])
                self._icon.title = f"Dictation: {config['desc']}"
            elif action == "update_menu":
                self._icon.menu = self._setup_menu()
            elif action == "refresh_devices":
                self._perform_device_refresh()

        except queue.Empty:
            pass  # No items in queue
        except Exception as e:
            logger.error(f"Error processing icon queue: {e}")
        return True  # Continue processing

    def _perform_device_refresh(self):
        from ..core.utils import refresh_devices

        original_state = self._current_state
        self.update_state(StatusIconState.TRANSCRIBING)  # Use as "busy" indicator
        time.sleep(0.1)  # allow UI to update
        refresh_devices()
        time.sleep(const.DEVICE_REFRESH_DELAY_SECS)
        self.update_state(original_state)

    def _select_transcriber(self, transcriber_id: str):
        if self._transcriber_callback and self._current_transcriber != transcriber_id:
            self._current_transcriber = transcriber_id
            self._transcriber_callback(transcriber_id)
            self.update_queue.put({"action": "update_menu"})

    def _select_language(self, lang_code: str):
        if self._language_callback and self._current_language != lang_code:
            self._current_language = lang_code
            self._language_callback(lang_code)
            self.update_queue.put({"action": "update_menu"})

    def _toggle_sounds(self):
        if self._sound_toggle_callback:
            self._sounds_enabled = not self._sounds_enabled
            self._sound_toggle_callback(self._sounds_enabled)
            self.update_queue.put({"action": "update_menu"})

    def _refresh_audio_devices(self):
        self.update_queue.put({"action": "refresh_devices"})

    def _exit(self):
        if self.on_exit:
            self.on_exit()

    def set_language_callback(self, callback: Callable, initial_language: str):
        self._language_callback = callback
        self._current_language = initial_language

    def set_transcriber_callback(self, callback: Callable, initial_transcriber: str):
        self._transcriber_callback = callback
        self._current_transcriber = initial_transcriber

    def set_sound_toggle_callback(self, callback: Callable, initial_state: bool):
        self._sound_toggle_callback = callback
        self._sounds_enabled = initial_state


def run_icon_on_main_thread(status_icon: StatusIcon):
    """Runs the icon's main loop and its queue processor."""
    if not status_icon or not status_icon._icon:
        logger.warning("Cannot run icon: instance not available.")
        return

    should_continue = [True]

    def queue_processor():
        while should_continue[0]:
            if not status_icon._process_queue():
                should_continue[0] = False
                break
            time.sleep(0.1)

    queue_thread = threading.Thread(target=queue_processor, daemon=True)
    queue_thread.start()

    status_icon._icon.run()

    should_continue[0] = False
    queue_thread.join(timeout=1.0)
    logger.info("Status icon main thread loop exited.")

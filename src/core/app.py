import argparse
import asyncio
import logging
import platform
import signal
import threading
import time
from typing import Any

from pynput import keyboard

from ..core.utils import loadwav, playsound
from ..services.input_handler import ClipboardPaster, DoubleKeyListener
from ..services.recorder import Recorder
from ..services.status_indicator import (
    StatusIcon,
    StatusIconState,
    run_icon_on_main_thread,
)
from ..services.transcriber import (
    GroqTranscriber,
    LocalTranscriber,
    OpenAITranscriber,
)
from . import constants as const
from .config import AppConfig
from .state_machine import create_state_machine

logger = logging.getLogger(__name__)


class App:
    """Main application class that manages the dictation workflow."""

    def __init__(self, args: argparse.Namespace):
        self.config = AppConfig.from_args(args)
        self.shutdown_event = threading.Event()
        self.status_icon_lock = threading.Lock()
        self.timer: threading.Timer | None = None
        self.last_state_change = 0
        self.state_change_delay = const.STATE_CHANGE_DELAY_SECS

        self._configure_platform_keys()
        self.m = create_state_machine()
        self.status_icon = self._setup_status_icon()
        self.recorder = self._setup_recorder()
        self.transcriber = self._create_transcriber(
            self.config.transcriber, self.config.model_name
        )
        self.replayer = ClipboardPaster(self.m.finish_replaying)
        self.SOUND_EFFECTS = self._load_sound_effects()

        self._setup_state_machine_callbacks()
        self.async_loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._start_async_loop, daemon=True)

    def _configure_platform_keys(self):
        if platform.system() == "Darwin":
            self.cancel_key = keyboard.Key.alt_r
            self.cancel_key_name = "Right Option"
        else:  # Linux
            self.cancel_key = self._normalize_key(self.config.cancel_key)
            self.cancel_key_name = self.config.cancel_key

    def _setup_status_icon(self) -> StatusIcon:
        icon = StatusIcon(on_exit=self._exit_app)
        icon.set_sound_toggle_callback(self._toggle_sounds, self.config.enable_sounds)
        icon.set_language_callback(self._change_language, self.config.language)
        icon.set_transcriber_callback(self._change_transcriber, self.config.transcriber)
        return icon

    def _setup_recorder(self) -> Recorder:
        return Recorder(
            self.m.finish_recording,
            vad_enabled=self.config.vad,
            vad_sensitivity=self.config.vad_sensitivity,
        )

    def _setup_state_machine_callbacks(self):
        self.m.on_enter_READY(self._on_enter_ready)
        self.m.on_enter_RECORDING(self._on_enter_recording)
        self.m.on_enter_TRANSCRIBING(self._async_on_enter_transcribing_wrapper)
        self.m.on_enter_REPLAYING(self._on_enter_replaying)

    def _start_async_loop(self):
        logger.info("Starting asyncio event loop.")
        asyncio.set_event_loop(self.async_loop)
        try:
            self.async_loop.run_forever()
        finally:
            self.async_loop.close()
            logger.info("Asyncio event loop closed.")

    def run(self) -> None:
        """Main application entry point."""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            self.status_icon.start()
            if not self.status_icon.is_initialized:
                raise RuntimeError("Failed to initialize status icon.")

            self.async_thread.start()
            key_listener, cancel_listener = self._setup_key_listeners()
            self.m.to_READY()

            logger.info("Handing control to status icon main loop...")
            run_icon_on_main_thread(self.status_icon)

            logger.info("Status icon loop finished. Shutting down...")
            key_listener.stop()
            cancel_listener.stop()

        except Exception as e:
            logger.error(f"Critical application error: {e}", exc_info=True)
            self.shutdown_event.set()
        finally:
            self._cleanup_resources()
            logger.info("Application finished.")

    def _on_enter_ready(self, event: Any):
        logger.info(
            f"Ready. Double tap '{self.config.trigger_key}' to start. "
            f"Double tap '{self.config.cancel_key}' to cancel."
        )
        with self.status_icon_lock:
            self.status_icon.update_state(StatusIconState.READY)

    def _on_enter_recording(self, event: Any):
        logger.info("Recording started.")
        with self.status_icon_lock:
            self.status_icon.update_state(StatusIconState.RECORDING)
        self.recorder.start(event)

    def _async_on_enter_transcribing_wrapper(self, event: Any):
        """Schedules the async transcription task to run in the event loop."""
        if self.async_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._on_enter_transcribing(event), self.async_loop
            )

    async def _on_enter_transcribing(self, event: Any):
        audio_data = event.kwargs.get("audio_data")
        if not audio_data or audio_data.getbuffer().nbytes == 0:
            logger.error("No audio data to transcribe.")
            await self._handle_error()
            return

        with self.status_icon_lock:
            self.status_icon.update_state(StatusIconState.TRANSCRIBING)
        await self.transcriber.transcribe(event)

    def _on_enter_replaying(self, event: Any):
        if event.kwargs.get("error"):
            logger.error(f"Transcription failed: {event.kwargs['error']}")
            asyncio.run_coroutine_threadsafe(self._handle_error(), self.async_loop)
        else:
            with self.status_icon_lock:
                self.status_icon.update_state(StatusIconState.REPLAYING)
            self.replayer.replay(event)

    async def _handle_error(self):
        """Visually indicate an error and return to READY state."""
        self.beep("error_sound", wait=False)
        with self.status_icon_lock:
            self.status_icon.update_state(StatusIconState.ERROR)
        await asyncio.sleep(const.ERROR_STATE_DISPLAY_DURATION_SECS)
        self.m.to_READY()

    def _can_change_state(self) -> bool:
        """Rate limit state changes to prevent bouncing."""
        if time.time() - self.last_state_change < self.state_change_delay:
            logger.warning("State change too fast, ignoring request.")
            return False
        self.last_state_change = time.time()
        return True

    def start(self):
        if self.m.is_READY() and self._can_change_state():
            self.beep("start_recording")
            if self.config.max_time:
                self.timer = threading.Timer(self.config.max_time, self.stop)
                self.timer.start()
            self.m.start_recording(language=self.config.language)

    def stop(self):
        if self.m.is_RECORDING() and self._can_change_state():
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.recorder.stop()
            self.beep("finish_recording", wait=False)

    def cancel_recording(self):
        if self.m.is_RECORDING() and self._can_change_state():
            logger.info("Cancelling recording.")
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.recorder.stop()
            self.beep("cancel_recording", wait=False)
            self.m.to_READY()

    def _toggle_sounds(self, enabled: bool):
        self.config.set_enable_sounds(enabled)

    def _change_language(self, lang_code: str):
        self.config.set_language(lang_code)

    def _change_transcriber(self, transcriber_id: str):
        try:
            # Close existing async transcriber
            if hasattr(self.transcriber, "close") and self.async_loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self.transcriber.close(), self.async_loop
                )
                future.result(timeout=const.TRANSCRIBER_CLOSE_TIMEOUT_SECS)

            model_name = getattr(const, f"DEFAULT_{transcriber_id.upper()}_MODEL")
            self.transcriber = self._create_transcriber(transcriber_id, model_name)
            self.config.set_transcriber(transcriber_id)
            self.config.set_model_name(model_name)
            logger.info(
                f"Transcriber changed to {transcriber_id} with model {model_name}."
            )
        except Exception as e:
            logger.error(f"Error changing transcriber: {e}")
            asyncio.run_coroutine_threadsafe(self._handle_error(), self.async_loop)

    def _create_transcriber(self, transcriber_id: str, model_name: str):
        transcriber_map = {
            "openai": OpenAITranscriber,
            "groq": GroqTranscriber,
            "local": LocalTranscriber,
        }
        cls = transcriber_map.get(transcriber_id)
        if not cls:
            raise ValueError(f"Unknown transcriber: {transcriber_id}")
        return cls(self.m.finish_transcribing, model_name)

    def _load_sound_effects(self) -> dict[str, Any]:
        sounds = {
            "start_recording": loadwav(const.SOUND_PATH_START),
            "finish_recording": loadwav(const.SOUND_PATH_FINISH),
            "cancel_recording": loadwav(const.SOUND_PATH_CANCEL),
        }
        sounds["error_sound"] = sounds["cancel_recording"]
        return sounds

    def beep(self, sound_name: str, wait: bool = True):
        if not self.config.get_enable_sounds():
            return
        sound = self.SOUND_EFFECTS.get(sound_name)
        if sound is not None:
            playsound(sound, wait)
        else:
            logger.warning(f"Sound not found: {sound_name}")

    def _normalize_key(self, key_str: str) -> Any:
        if key_str.startswith("Key."):
            key_name = key_str.split(".")[1]
            key = getattr(keyboard.Key, key_name)
            return key
        key = keyboard.HotKey.parse(key_str)[0]
        return key

    def _setup_key_listeners(self) -> tuple[DoubleKeyListener, DoubleKeyListener]:
        trigger_key = self._normalize_key(self.config.trigger_key)
        key_listener = DoubleKeyListener(self.start, self.stop, trigger_key)
        cancel_listener = DoubleKeyListener(
            self.cancel_recording, lambda: None, self.cancel_key
        )

        key_listener.shutdown_event = self.shutdown_event
        cancel_listener.shutdown_event = self.shutdown_event

        threading.Thread(target=key_listener.run, daemon=True).start()
        threading.Thread(target=cancel_listener.run, daemon=True).start()
        return key_listener, cancel_listener

    def signal_handler(self, signum, frame):
        logger.warning(f"Received signal {signum}. Initiating shutdown...")
        self.shutdown_event.set()
        # This might be called from a non-main thread, so we queue the stop.
        if self.status_icon:
            self.status_icon.stop_icon()

    def _exit_app(self):
        logger.info("Exit requested via menu. Initiating shutdown...")
        self.shutdown_event.set()
        if self.status_icon:
            self.status_icon.stop_icon()

    def _cleanup_resources(self):
        logger.info("Cleaning up resources...")
        if self.timer:
            self.timer.cancel()
        if self.m.is_RECORDING():
            self.recorder.stop()

        if self.async_loop.is_running():
            if hasattr(self.transcriber, "close"):
                future = asyncio.run_coroutine_threadsafe(
                    self.transcriber.close(), self.async_loop
                )
                try:
                    future.result(timeout=const.TRANSCRIBER_CLEANUP_TIMEOUT_SECS)
                except Exception as e:
                    logger.warning(f"Transcriber did not close cleanly: {e}")
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)

        if self.async_thread.is_alive():
            self.async_thread.join(timeout=const.ASYNC_THREAD_JOIN_TIMEOUT_SECS)
        logger.info("Resource cleanup completed.")

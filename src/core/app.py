import asyncio  # Added
import logging
import platform
import signal
import threading
import time

import numpy as np
from pynput import keyboard

from ..core.utils import loadwav, playsound
from ..services.input_handler import DoubleKeyListener, KeyboardReplayer
from ..services.recorder import Recorder
from ..services.status_indicator import (
    StatusIcon,
    StatusIconState,
    run_icon_on_main_thread,
)
from ..services.transcriber import (  # Added LocalTranscriber
    GroqTranscriber,
    LocalTranscriber,
    OpenAITranscriber,
)
from . import constants as const
from .state_machine import create_state_machine

logger = logging.getLogger(__name__)


class App:
    """Main application class that manages the dictation workflow."""

    # Class constants
    TRANSCRIBER_MODELS = {
        "openai": const.DEFAULT_OPENAI_MODEL,
        "groq": const.DEFAULT_GROQ_MODEL,
        "local": const.DEFAULT_LOCAL_MODEL,  # Added local transcriber
    }

    def __init__(self, args):
        """
        Initialize the application with command line arguments.

        Args:
            args: Parsed command line arguments
        """
        self.args = args
        self.shutdown_event = threading.Event()
        self.language = args.language
        self.timer_active = threading.Event()
        self.last_state_change = 0
        self.state_change_delay = 0.5  # Minimum delay between state changes in seconds
        self.status_icon_lock = threading.Lock()  # Add lock for status icon operations
        self.config_lock = threading.Lock()  # Add lock for configuration settings

        # Determine platform-specific cancel key
        if platform.system() == "Darwin":
            self.cancel_key = keyboard.Key.alt_r  # Right Option
            self.cancel_key_name = "right option"
        else:  # Linux, Windows (assuming Left Ctrl)
            self.cancel_key = keyboard.Key.ctrl_l  # Left Control
            self.cancel_key_name = "left control"

        # Start timer monitoring thread
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        self.enable_sounds = args.enable_sounds  # Store the sound enable flag

        # Initialize state machine
        self.m = create_state_machine()

        # Initialize components
        # args.vad is created by argparse.BooleanOptionalAction in cli.py
        # args.vad_sensitivity is also from cli.py
        vad_enabled_arg = getattr(
            args, "vad", True
        )  # Default to True if --vad/--no-vad not specified
        vad_sensitivity_arg = getattr(args, "vad_sensitivity", 1)  # Default to 1
        logger.info(
            f"Initializing Recorder with VAD enabled: {vad_enabled_arg}, sensitivity: {vad_sensitivity_arg}"
        )
        self.recorder = Recorder(
            self.m.finish_recording,
            vad_enabled=vad_enabled_arg,
            vad_sensitivity=vad_sensitivity_arg,
        )

        # Initialize the appropriate transcriber based on the argument
        if args.transcriber == "openai":
            self.transcriber = OpenAITranscriber(
                self.m.finish_transcribing, args.model_name
            )
        elif args.transcriber == "local":  # Added local transcriber initialization
            self.transcriber = LocalTranscriber(
                self.m.finish_transcribing, args.model_name
            )
        else:  # groq
            self.transcriber = GroqTranscriber(
                self.m.finish_transcribing, args.model_name
            )

        self.replayer = KeyboardReplayer(self.m.finish_replaying)

        # Initialize status icon with lock protection
        with self.status_icon_lock:
            self.status_icon = StatusIcon(on_exit=self._exit_app)
            self.status_icon.set_sound_toggle_callback(
                self._toggle_sounds, self.enable_sounds
            )
            self.status_icon.set_language_callback(self._change_language, self.language)
            self.status_icon.set_transcriber_callback(
                self._change_transcriber, self.args.transcriber
            )

        # Configure state machine callbacks that combine functionality
        self.m.on_enter_READY(self._on_enter_ready)
        self.m.on_enter_RECORDING(self._on_enter_recording)
        # self.m.on_enter_TRANSCRIBING(self._on_enter_transcribing) # Will be handled differently
        self.m.on_enter_TRANSCRIBING(
            self._async_on_enter_transcribing_wrapper
        )  # New async wrapper
        self.m.on_enter_REPLAYING(self._on_enter_replaying)

        # Asyncio event loop setup
        self.async_loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._start_async_loop, daemon=True)
        self.async_thread.start()

        # Load sound effects with validation
        self.SOUND_EFFECTS = self._load_sound_effects()

        # Add error sound (using cancel sound as fallback)
        if "cancel_recording" in self.SOUND_EFFECTS:
            self.SOUND_EFFECTS["error_sound"] = self.SOUND_EFFECTS["cancel_recording"]

    def _on_enter_ready(self, *_):
        """Callback that runs when entering READY state."""
        with self.status_icon_lock:
            logger.info(
                f"Double tap {self.args.trigger_key} to start recording. "
                f"Tap once to stop recording. "
                f"Double tap {self.cancel_key_name} to cancel recording."
            )
            self.status_icon.update_state(StatusIconState.READY)

    def _on_enter_recording(self, event):
        """Handle entering RECORDING state."""
        with self.status_icon_lock:
            logger.info("Recording started")
            self.status_icon.update_state(StatusIconState.RECORDING)
            # Start the actual recording
            self._safe_start_recording(event)

    def _async_on_enter_transcribing_wrapper(self, event):
        """Wrapper to call the async _on_enter_transcribing from the state machine."""
        # This method is called by the state machine, which runs in the main thread or a pynput thread.
        # We need to schedule the async _on_enter_transcribing to run in our asyncio loop.
        logger.debug("Scheduling _on_enter_transcribing via wrapper")
        asyncio.run_coroutine_threadsafe(
            self._on_enter_transcribing(event), self.async_loop
        )

    async def _on_enter_transcribing(self, event):  # Changed to async def
        """Handle entering TRANSCRIBING state asynchronously."""
        audio_data = (
            event.kwargs.get("audio_data") if hasattr(event, "kwargs") else None
        )

        if audio_data is None or audio_data.getbuffer().nbytes == 0:
            logger.error(
                "No audio data available for transcription - recording may have failed or was empty"
            )
            # Ensure UI updates are thread-safe if called from async context
            self.async_loop.call_soon_threadsafe(
                self.status_icon.update_state, StatusIconState.ERROR
            )
            await asyncio.sleep(1)  # Use asyncio.sleep
            self.async_loop.call_soon_threadsafe(self.m.to_READY)
            return

        # Start the actual transcription asynchronously
        await self._safe_start_transcription(event)  # Added await

    def _on_enter_replaying(self, event):
        """Handle entering REPLAYING state."""
        # Check for transcription error
        error = event.kwargs.get("error") if hasattr(event, "kwargs") else None

        if error:
            logger.error(f"Transcription failed: {error}")
            with self.status_icon_lock:
                self.status_icon.update_state(StatusIconState.ERROR)
            # Wait a moment to show the error state
            time.sleep(1)
            # Return to READY state
            self.m.to_READY()
        else:
            # Start the actual replaying
            self._safe_start_replay(event)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.warning(f"Received signal {signum}. Initiating shutdown...")
        self.shutdown_event.set()

    def _exit_app(self):
        """Handle exit request from the status icon menu."""
        logger.info("Exit requested via menu. Initiating shutdown...")
        self.shutdown_event.set()
        # Return False to let the main loop handle shutdown
        return False

    def _toggle_sounds(self, enabled: bool):
        """Toggle sound effects on/off."""
        with self.config_lock:
            self.enable_sounds = enabled
        logger.info(f"Sound effects {'enabled' if enabled else 'disabled'}")

    def _change_language(self, language_code: str):
        """Change the transcription language."""
        with self.config_lock:
            self.language = language_code
        logger.info(f"Language changed to: {language_code}")

    def _change_transcriber(self, transcriber_id: str):
        """Change the transcription service."""
        try:
            # Get model name from class constants
            model_name = self.TRANSCRIBER_MODELS.get(transcriber_id)
            if not model_name:
                logger.error(f"Unknown transcriber: {transcriber_id}")
                self.status_icon.update_state(StatusIconState.ERROR)
                return

            with self.config_lock:
                # Close existing transcriber if it has a close method
                if hasattr(self.transcriber, "close"):
                    if asyncio.iscoroutinefunction(self.transcriber.close):
                        logger.info(
                            f"Closing existing async transcriber: {self.transcriber.__class__.__name__}"
                        )
                        asyncio.run_coroutine_threadsafe(
                            self.transcriber.close(), self.async_loop
                        )
                    else:
                        logger.info(
                            f"Closing existing sync transcriber: {self.transcriber.__class__.__name__}"
                        )
                        self.transcriber.close()

                # Create new transcriber instance with appropriate model name
                if transcriber_id == "openai":
                    self.transcriber = OpenAITranscriber(
                        self.m.finish_transcribing, model_name
                    )
                elif transcriber_id == "local":  # Added local transcriber instantiation
                    self.transcriber = LocalTranscriber(
                        self.m.finish_transcribing, model_name
                    )
                else:  # groq
                    self.transcriber = GroqTranscriber(
                        self.m.finish_transcribing, model_name
                    )

                # Update the stored model name
                self.args.model_name = model_name
                self.args.transcriber = transcriber_id

            logger.info(
                f"Transcriber changed to: {transcriber_id} with model: {model_name}"
            )
        except Exception as e:
            logger.error(f"Error changing transcriber: {str(e)}")
            self.status_icon.update_state(StatusIconState.ERROR)

    def _load_sound_effects(self) -> dict[str, np.ndarray | None]:
        """
        Load and validate sound effects.

        Returns:
            dict: Mapping of sound effect names to audio data
        """
        sounds = {
            "start_recording": loadwav(const.SOUND_PATH_START),
            "finish_recording": loadwav(const.SOUND_PATH_FINISH),
            "cancel_recording": loadwav(const.SOUND_PATH_CANCEL),
        }

        # Validate sound effects
        for name, data in sounds.items():
            if data is None:
                logger.error(f"Failed to load sound effect: {name}")

        return sounds

    def _start_async_loop(self):
        """Starts the asyncio event loop."""
        logger.info("Starting asyncio event loop in a new thread.")
        asyncio.set_event_loop(self.async_loop)
        try:
            self.async_loop.run_forever()
        finally:
            self.async_loop.close()
            logger.info("Asyncio event loop closed.")

    def _safe_start_recording(self, event) -> None:
        """Wrapper for recorder start with error handling."""
        try:
            self.recorder.start(event)
        except Exception as e:
            logger.error(f"Error starting recording: {str(e)}")
            self.status_icon.update_state(StatusIconState.ERROR)
            self.m.to_READY()  # This should be called thread-safe if m is not async-aware
            # self.async_loop.call_soon_threadsafe(self.m.to_READY)

    async def _safe_start_transcription(self, event) -> None:  # Changed to async def
        """Wrapper for transcription start with error handling (now asynchronous)."""
        try:
            # Update status icon first (ensure thread-safety if status_icon is not async-aware)
            # Using call_soon_threadsafe if status_icon methods are not designed for async calls directly
            # from a different thread's loop.
            # However, if status_icon is simple and its state updates are atomic or internally locked,
            # direct calls might be fine. For safety, let's assume they might need to be thread-safe.
            def update_status_sync():
                with self.status_icon_lock:
                    logger.info("Transcribing audio...")
                    self.status_icon.update_state(StatusIconState.TRANSCRIBING)

            # If running in the asyncio loop's thread, direct call is fine.
            # If called from another thread (e.g. via run_coroutine_threadsafe),
            # and status_icon interacts with GUI elements, it must be called on the main thread.
            # For now, let's assume status_icon updates are safe or handled internally.
            update_status_sync()

            # The event already contains audio_data and language.
            # The transcriber.transcribe method is now async.
            await self.transcriber.transcribe(event)  # Added await
        except Exception as e:
            logger.error(f"Error starting transcription: {str(e)}")

            def update_error_status_sync():
                with self.status_icon_lock:
                    self.status_icon.update_state(StatusIconState.ERROR)

            # update_error_status_sync()
            self.async_loop.call_soon_threadsafe(update_error_status_sync)

            # self.m.to_READY() # This should be called thread-safe
            self.async_loop.call_soon_threadsafe(self.m.to_READY)

    def _safe_start_replay(self, event) -> None:
        """Wrapper for replay start with error handling."""
        try:
            # Update status icon first
            with self.status_icon_lock:
                logger.info("Replaying transcribed text...")
                self.status_icon.update_state(StatusIconState.REPLAYING)

            # Then start replay (which will trigger state transition when done)
            self.replayer.replay(event)
        except Exception as e:
            logger.error(f"Error starting replay: {str(e)}")
            with self.status_icon_lock:
                self.status_icon.update_state(StatusIconState.ERROR)
            self.m.to_READY()

    def _timer_loop(self) -> None:
        """Continuous timer monitoring loop using threading.Timer for efficiency."""
        while True:
            # Wait until timer is activated
            self.timer_active.wait()

            # Create and start a timer
            self.timer = threading.Timer(self.args.max_time, self.timer_stop)
            self.timer.daemon = True
            self.timer.start()

            # Wait until timer is cleared (by stop or cancel)
            self.timer_active.wait()
            self.timer_active.clear()

            # Cancel the timer if it's still running
            if hasattr(self, "timer") and self.timer:
                self.timer.cancel()

    def _can_change_state(self) -> bool:
        """
        Check if state change is allowed based on rate limiting.

        Returns:
            bool: True if state change is allowed, False otherwise
        """
        current_time = time.time()
        time_since_last = current_time - self.last_state_change
        return time_since_last >= self.state_change_delay

    def beep(self, sound_name: str, wait: bool = True) -> None:
        """
        Play a sound effect with validation.

        Args:
            sound_name: Name of the sound effect to play
            wait: Whether to wait for sound to finish playing
        """
        # Skip if sounds are disabled
        with self.config_lock:
            play_sound = self.enable_sounds
        if not play_sound:
            return

        sound = self.SOUND_EFFECTS.get(sound_name)
        if sound is None:
            logger.error(f"Invalid sound effect: {sound_name}")
            return

        try:
            playsound(sound, wait=wait)
        except Exception as e:
            logger.error(f"Error playing sound effect {sound_name}: {str(e)}")

    def start(self) -> bool:
        """
        Start recording if in READY state.

        Returns:
            bool: True if recording started, False otherwise
        """
        if not self._can_change_state():
            logger.warning("State change too fast - ignoring start request")
            return False

        if self.m.is_READY():
            try:
                self.beep("start_recording")

                # Start recording timer if max time specified
                if self.args.max_time:
                    self.timer_active.set()

                with self.config_lock:
                    current_language = self.language
                self.m.start_recording(language=current_language)
                self.last_state_change = time.time()
                return True
            except Exception as e:
                logger.error(f"Error starting recording: {str(e)}")
                return False
        return False

    def stop(self) -> bool:
        """
        Stop recording if in RECORDING state.

        Returns:
            bool: True if recording stopped, False otherwise
        """
        if not self._can_change_state():
            logger.warning("State change too fast - ignoring stop request")
            return False

        if self.m.is_RECORDING():
            try:
                self.recorder.stop()

                # Cancel timer if running
                self.timer_active.clear()

                self.beep("finish_recording", wait=False)
                self.last_state_change = time.time()
                return True
            except Exception as e:
                logger.error(f"Error stopping recording: {str(e)}")
                return False
        return False

    def cancel_recording(self) -> bool:
        """
        Cancel recording if in RECORDING state and return to READY state.
        This aborts the recording without transcribing anything.

        Returns:
            bool: True if recording was cancelled, False otherwise
        """
        logger.debug("Cancel recording requested")

        if not self._can_change_state():
            logger.warning("State change too fast - ignoring cancel request")
            return False

        if self.m.is_RECORDING():
            try:
                logger.info("Cancelling recording...")
                self.recorder.stop()

                # Cancel timer if running
                self.timer_active.clear()

                self.beep("cancel_recording", wait=False)

                # Go directly to READY state instead of going through transcription
                self.m.to_READY()
                self.last_state_change = time.time()
                return True
            except Exception as e:
                logger.error(f"Error cancelling recording: {str(e)}")
                return False
        return False

    def timer_stop(self) -> None:
        """Handle timer expiration by stopping recording."""
        logger.info("Timer stop")
        try:
            self.stop()
        except Exception as e:
            logger.error(f"Error in timer stop: {str(e)}")

    def _normalize_key(self, key: str) -> str:
        """
        Normalize key string to handle platform-specific variations.

        Args:
            key: Key string to normalize

        Returns:
            str: Normalized key string
        """
        # Handle Key.attr format (e.g., "Key.cmd_r")
        if key.startswith("Key."):
            attr_name = key[4:]  # Remove "Key." prefix
            try:
                # Get the attribute directly from keyboard.Key
                return getattr(keyboard.Key, attr_name)
            except AttributeError as err:
                logger.error(f"Invalid key attribute: {attr_name}")
                raise ValueError(f"Invalid key attribute: {attr_name}") from err

        # Handle bracket format (e.g., "<cmd_r>")
        key = key.replace("<win>", "<cmd>").replace("<super>", "<cmd>")
        try:
            parsed_key = keyboard.HotKey.parse(key)[0]
            logger.info(f"Using trigger key: {parsed_key}")
            return parsed_key
        except ValueError as e:
            logger.error(f"Invalid trigger key: {key} - {str(e)}")
            raise

    def _setup_key_listener(self) -> tuple[DoubleKeyListener, DoubleKeyListener]:
        """
        Configure and return the key listeners with normalized trigger keys.

        Returns:
            tuple: (main_listener, cancel_listener)
        """
        try:
            # Normalize trigger key
            trigger_key = self._normalize_key(self.args.trigger_key)

            # Use stored platform-specific key
            cancel_key = self.cancel_key

            # Main trigger key listener
            key_listener = DoubleKeyListener(self.start, self.stop, trigger_key)

            # Cancel key listener (double tap to cancel)
            cancel_listener = DoubleKeyListener(
                self.cancel_recording, lambda: None, cancel_key
            )

            # Return both listeners
            return key_listener, cancel_listener
        except Exception as e:
            logger.error(f"Error setting up key listener: {str(e)}")
            raise

    def _cleanup_resources(self) -> None:
        """Clean up all resources to ensure proper shutdown."""
        try:
            logger.info("Cleaning up resources...")

            # Cancel any active timer
            if hasattr(self, "timer_active"):
                self.timer_active.clear()

            if hasattr(self, "timer") and self.timer:
                self.timer.cancel()
                self.timer = None

            # Stop recording if active
            if hasattr(self, "recorder"):
                try:
                    if self.m.is_RECORDING():
                        self.recorder.stop()
                    # Clear recorder frames to free memory
                    if hasattr(self.recorder, "frames"):
                        self.recorder.frames = []
                except Exception as e:
                    logger.error(f"Error stopping recorder: {str(e)}")

            # Stop status icon
            if hasattr(self, "status_icon"):
                try:
                    # Ensure status_icon.stop() is called from the correct thread if it interacts with GUI
                    if hasattr(self.status_icon, "_icon") and hasattr(
                        self.status_icon._icon, "stop"
                    ):
                        # If pystray, it might need to be stopped from the main thread or its own thread.
                        # For now, assume direct call is okay or handled by pystray.
                        self.status_icon.stop()
                    elif hasattr(self.status_icon, "stop"):  # Fallback
                        self.status_icon.stop()

                except Exception as e:
                    logger.error(f"Error stopping status icon: {str(e)}")

            # Stop asyncio loop
            if hasattr(self, "async_loop") and self.async_loop.is_running():
                logger.info("Stopping asyncio event loop...")
                self.async_loop.call_soon_threadsafe(self.async_loop.stop)
                # Wait for the async_thread to finish
                if hasattr(self, "async_thread") and self.async_thread.is_alive():
                    self.async_thread.join(timeout=5)  # Wait for 5 seconds
                    if self.async_thread.is_alive():
                        logger.warning("Asyncio thread did not stop in time.")

            # Clean up transcriber resources
            if hasattr(self, "transcriber"):
                # Nothing to do for now, but could be extended
                pass

            # Clean up keyboard replayer
            if hasattr(self, "replayer"):
                # Nothing specific to clean up
                pass

            # Force garbage collection
            import gc

            gc.collect()

            logger.info("Resource cleanup completed")
        except Exception as e:
            logger.error(f"Error during resource cleanup: {str(e)}")

    def run(self) -> None:
        """Main application entry point."""
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)  # Handle Ctrl+C
        signal.signal(signal.SIGTERM, self.signal_handler)  # Handle kill/systemd stop

        try:
            # Create the status icon instance (doesn't run the loop yet)
            logger.info("Creating status icon instance...")
            self.status_icon.start()
            if not self.status_icon._is_initialized:
                raise RuntimeError("Failed to initialize status icon.")

            # Set up key listeners
            logger.info("Setting up key listeners...")
            keylistener, cancel_listener = self._setup_key_listener()

            # Initialize state machine to READY
            logger.info("Setting initial state to READY...")
            self.m.to_READY()  # Ensure initial state and message

            # Pass shutdown event to listeners
            keylistener.shutdown_event = self.shutdown_event
            cancel_listener.shutdown_event = self.shutdown_event

            # Start key listeners in separate threads
            key_listener_thread = threading.Thread(target=keylistener.run, daemon=True)
            cancel_listener_thread = threading.Thread(
                target=cancel_listener.run, daemon=True
            )

            logger.info("Starting key listener threads...")
            key_listener_thread.start()
            cancel_listener_thread.start()

            logger.info("Handing control to status icon main loop...")
            run_icon_on_main_thread(self.status_icon._icon)

            logger.info("Status icon loop finished. Shutting down...")

        except Exception as e:
            logger.error(f"Critical application error: {str(e)}", exc_info=True)
            self.shutdown_event.set()

        finally:
            logger.info("Entering final cleanup phase.")
            self._cleanup_resources()
            logger.info("Application finished.")

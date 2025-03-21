import logging
import platform
import threading
import time

import numpy as np
from pynput import keyboard

from ..core.utils import loadwav, playsound
from ..services.input_handler import DoubleKeyListener, KeyboardReplayer
from ..services.recorder import Recorder
from ..services.status_indicator import StatusIcon, StatusIconState
from ..services.transcriber import GroqTranscriber, OpenAITranscriber
from .state_machine import create_state_machine

logger = logging.getLogger(__name__)


class App:
    """Main application class that manages the dictation workflow."""

    def __init__(self, args):
        """
        Initialize the application with command line arguments.

        Args:
            args: Parsed command line arguments
        """
        self.args = args
        self.language = args.language
        self.timer_active = threading.Event()
        self.last_state_change = 0
        self.state_change_delay = 0.5  # Minimum delay between state changes in seconds

        # Start timer monitoring thread
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        self.enable_sounds = args.enable_sounds  # Store the sound enable flag

        # Initialize state machine
        self.m = create_state_machine()

        # Initialize components
        self.recorder = Recorder(self.m.finish_recording)

        # Initialize the appropriate transcriber based on the argument
        if args.transcriber == "openai":
            self.transcriber = OpenAITranscriber(
                self.m.finish_transcribing, args.model_name
            )
        else:  # groq
            self.transcriber = GroqTranscriber(
                self.m.finish_transcribing, args.model_name
            )

        self.replayer = KeyboardReplayer(self.m.finish_replaying)

        # Initialize status icon
        self.status_icon = StatusIcon(on_exit=self._exit_app)

        # Connect status icon sound toggle to the app's sound setting
        self.status_icon.set_sound_toggle_callback(
            self._toggle_sounds, self.enable_sounds
        )

        # Configure state machine callbacks that combine functionality
        self.m.on_enter_READY(self._on_enter_ready)
        self.m.on_enter_RECORDING(self._on_enter_recording)
        self.m.on_enter_TRANSCRIBING(self._on_enter_transcribing)
        self.m.on_enter_REPLAYING(self._on_enter_replaying)

        # Load sound effects with validation
        self.SOUND_EFFECTS = self._load_sound_effects()

    def _on_enter_ready(self, *_):
        """Callback that runs when entering READY state."""
        # Get the platform-specific cancel key name for the message
        if platform.system() == "Darwin":
            cancel_key_name = "right option"
        else:
            cancel_key_name = "right alt"

        logger.info(
            f"Double tap {self.args.trigger_key} to start recording. "
            f"Tap once to stop recording. "
            f"Double tap {cancel_key_name} to cancel recording."
        )
        self.status_icon.update_state(StatusIconState.READY)

    def _on_enter_recording(self, event):
        """Handle entering RECORDING state."""
        logger.info("Recording started")
        self.status_icon.update_state(StatusIconState.RECORDING)
        # Start the actual recording
        self._safe_start_recording(event)

    def _on_enter_transcribing(self, event):
        """Handle entering TRANSCRIBING state."""
        logger.info("Transcribing audio...")
        self.status_icon.update_state(StatusIconState.TRANSCRIBING)
        # Start the actual transcription
        self._safe_start_transcription(event)

    def _on_enter_replaying(self, event):
        """Handle entering REPLAYING state."""
        logger.info("Replaying transcribed text...")
        self.status_icon.update_state(StatusIconState.REPLAYING)
        # Start the actual replaying
        self._safe_start_replay(event)

    def _exit_app(self):
        """Handle exit request from the status icon menu."""
        logger.info("Exit requested from status icon")
        # Perform any necessary cleanup
        try:
            if self.m.is_RECORDING():
                self.recorder.stop()
            self.status_icon.stop()
        except Exception as e:
            logger.error(f"Error during exit: {str(e)}")
        # Exit application
        import sys

        sys.exit(0)

    def _toggle_sounds(self, enabled: bool):
        """Toggle sound effects on/off."""
        self.enable_sounds = enabled
        logger.info(f"Sound effects {'enabled' if enabled else 'disabled'}")

    def _load_sound_effects(self) -> dict[str, np.ndarray | None]:
        """
        Load and validate sound effects.

        Returns:
            dict: Mapping of sound effect names to audio data
        """
        sounds = {
            "start_recording": loadwav("assets/107786__leviclaassen__beepbeep.wav"),
            "finish_recording": loadwav(
                "assets/559318__alejo902__sonido-3-regulator.wav"
            ),
            "cancel_recording": loadwav("assets/160909__racche__scratch-speed.wav"),
        }

        # Validate sound effects
        for name, data in sounds.items():
            if data is None:
                logger.error(f"Failed to load sound effect: {name}")

        return sounds

    def _safe_start_recording(self, event) -> None:
        """Wrapper for recorder start with error handling."""
        try:
            self.recorder.start(event)
        except Exception as e:
            logger.error(f"Error starting recording: {str(e)}")
            self.status_icon.update_state(StatusIconState.ERROR)
            self.m.to_READY()

    def _safe_start_transcription(self, event) -> None:
        """Wrapper for transcription start with error handling."""
        try:
            self.transcriber.transcribe(event)
        except Exception as e:
            logger.error(f"Error starting transcription: {str(e)}")
            self.status_icon.update_state(StatusIconState.ERROR)
            self.m.to_READY()

    def _safe_start_replay(self, event) -> None:
        """Wrapper for replay start with error handling."""
        try:
            self.replayer.replay(event)
        except Exception as e:
            logger.error(f"Error starting replay: {str(e)}")
            self.status_icon.update_state(StatusIconState.ERROR)
            self.m.to_READY()

    def _timer_loop(self) -> None:
        """Continuous timer monitoring loop."""
        while True:
            self.timer_active.wait()
            start_time = time.time()
            while time.time() - start_time < self.args.max_time:
                if not self.timer_active.is_set():
                    break
                time.sleep(0.1)  # Precise timeout checking
            if self.timer_active.is_set():
                self.timer_stop()
            self.timer_active.clear()

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
        if not self.enable_sounds:
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

                self.m.start_recording(language=self.language)
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

    def _setup_key_listener(self) -> tuple[DoubleKeyListener, DoubleKeyListener]:
        """
        Configure and return the key listeners with normalized trigger keys.

        Returns:
            tuple: (main_listener, cancel_listener)
        """

        def normalize_key(key: str) -> str:
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

        try:
            trigger_key = normalize_key(self.args.trigger_key)

            # Set cancel key based on platform
            if platform.system() == "Darwin":  # macOS
                cancel_key = keyboard.Key.alt_r  # Right option key on Mac
            else:
                cancel_key = keyboard.Key.alt_r  # Right alt key on Linux

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

    def run(self) -> None:
        """Main application loop that handles key listening and state management."""
        try:
            # Start the status icon
            self.status_icon.start()

            # Set up key listeners
            keylistener, cancel_listener = self._setup_key_listener()

            # Start cancel listener in a separate thread
            cancel_listener_thread = threading.Thread(target=cancel_listener.run)
            cancel_listener_thread.daemon = True
            cancel_listener_thread.start()

            # Initialize state machine
            self.m.to_READY()

            # Check if we're on macOS
            if platform.system() == "Darwin":
                # On macOS, run the key listener in a separate thread
                # and run the icon on the main thread
                from ..services.status_indicator import run_icon_on_macos

                key_listener_thread = threading.Thread(target=keylistener.run)
                key_listener_thread.daemon = True
                key_listener_thread.start()

                # Run icon on main thread (this will block until the icon is stopped)
                run_icon_on_macos()
            else:
                # On other platforms, run the key listener on the main thread
                keylistener.run()
        except Exception as e:
            logger.error(f"Application error: {str(e)}")
            # Try to stop the status icon
            if hasattr(self, "status_icon"):
                try:
                    self.status_icon.stop()
                except Exception as cleanup_error:
                    logger.error(f"Error stopping status icon: {cleanup_error}")
            raise

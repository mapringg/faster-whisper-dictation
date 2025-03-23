import logging
import platform
import threading
import time
from abc import ABC, abstractmethod

import numpy as np
from pynput import keyboard

from ..core.utils import loadwav, playsound
from ..services.input_handler import DoubleKeyListener, KeyboardReplayer
from ..services.recorder import Recorder
from ..services.status_indicator import StatusIcon, StatusIconState
from ..services.transcriber import GroqTranscriber, OpenAITranscriber
from .state_machine import create_state_machine

logger = logging.getLogger(__name__)


class PlatformHandler(ABC):
    """Abstract base class for platform-specific behavior."""

    @staticmethod
    def get_handler():
        """Factory method to get the appropriate platform handler."""
        system = platform.system()
        if system == "Darwin":
            return MacOSHandler()
        else:
            return DefaultHandler()

    @abstractmethod
    def get_cancel_key_name(self) -> str:
        """Get the platform-specific cancel key name for user messages."""
        pass

    @abstractmethod
    def get_cancel_key(self) -> keyboard.Key:
        """Get the platform-specific cancel key for the listener."""
        pass

    @abstractmethod
    def run_key_listener(self, app, keylistener) -> None:
        """Run the key listener in a platform-specific way."""
        pass


class MacOSHandler(PlatformHandler):
    """Handler for macOS-specific behavior."""

    def get_cancel_key_name(self) -> str:
        """Get the macOS-specific cancel key name."""
        return "right option"

    def get_cancel_key(self) -> keyboard.Key:
        """Get the macOS-specific cancel key."""
        return keyboard.Key.alt_r  # Right option key on Mac

    def run_key_listener(self, app, keylistener) -> None:
        """Run the key listener in a macOS-specific way."""
        from ..services.status_indicator import run_icon_on_macos

        # On macOS, run the key listener in a separate thread
        # and run the icon on the main thread
        key_listener_thread = threading.Thread(target=keylistener.run)
        key_listener_thread.daemon = True
        key_listener_thread.start()

        # Run icon on main thread (this will block until the icon is stopped)
        run_icon_on_macos()


class DefaultHandler(PlatformHandler):
    """Default handler for other platforms (Linux, Windows)."""

    def get_cancel_key_name(self) -> str:
        """Get the default cancel key name."""
        return "right alt"

    def get_cancel_key(self) -> keyboard.Key:
        """Get the default cancel key."""
        return keyboard.Key.alt_r  # Right alt key on Linux/Windows

    def run_key_listener(self, app, keylistener) -> None:
        """Run the key listener in the default way."""
        # On other platforms, run the key listener on the main thread
        keylistener.run()


class App:
    """Main application class that manages the dictation workflow."""

    # Class constants
    TRANSCRIBER_MODELS = {"openai": "gpt-4o-transcribe", "groq": "whisper-large-v3"}

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
        self.status_icon_lock = threading.Lock()  # Add lock for status icon operations

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
        self.m.on_enter_TRANSCRIBING(self._on_enter_transcribing)
        self.m.on_enter_REPLAYING(self._on_enter_replaying)

        # Load sound effects with validation
        self.SOUND_EFFECTS = self._load_sound_effects()

    def _on_enter_ready(self, *_):
        """Callback that runs when entering READY state."""
        with self.status_icon_lock:
            # Get the platform-specific cancel key name using the handler
            platform_handler = PlatformHandler.get_handler()
            cancel_key_name = platform_handler.get_cancel_key_name()

            logger.info(
                f"Double tap {self.args.trigger_key} to start recording. "
                f"Tap once to stop recording. "
                f"Double tap {cancel_key_name} to cancel recording."
            )
            self.status_icon.update_state(StatusIconState.READY)

    def _on_enter_recording(self, event):
        """Handle entering RECORDING state."""
        with self.status_icon_lock:
            logger.info("Recording started")
            self.status_icon.update_state(StatusIconState.RECORDING)
            # Start the actual recording
            self._safe_start_recording(event)

    def _on_enter_transcribing(self, event):
        """Handle entering TRANSCRIBING state."""
        # Start the actual transcription
        self._safe_start_transcription(event)

    def _on_enter_replaying(self, event):
        """Handle entering REPLAYING state."""
        # Start the actual replaying
        self._safe_start_replay(event)

    def _exit_app(self):
        """Handle exit request from the status icon menu."""
        logger.info("Exit requested from status icon")
        # Set exit flag for graceful shutdown
        self.exit_requested = True

        # Perform any necessary cleanup
        self._cleanup_resources()

        # Platform-specific service management
        import platform
        import subprocess
        import os
        import sys
        import shutil
        import time

        system = platform.system()
        
        # Create a marker file to indicate user-initiated exit (used by run.sh)
        # Creating this BEFORE stopping the service ensures run.sh won't restart
        try:
            logger.info("Creating exit marker file")
            with open("/tmp/dictation_user_exit", "w") as f:
                f.write("1")
        except Exception as e:
            logger.error(f"Failed to create exit marker file: {e}")
        
        # On macOS, unload the LaunchAgent
        if system == "Darwin":
            try:
                logger.info("Attempting to unload macOS LaunchAgent")
                # Use full path expansion for home directory
                home_dir = os.path.expanduser("~")
                plist_path = os.path.join(home_dir, "Library/LaunchAgents/com.user.dictation.plist")
                
                # Use subprocess with expanded path, not shell=True
                subprocess.run(
                    ["launchctl", "unload", plist_path],
                    check=False,
                    capture_output=True
                )
                
                # Verify the service is unloaded
                result = subprocess.run(
                    ["launchctl", "list", "com.user.dictation"],
                    check=False,
                    capture_output=True
                )
                
                if result.returncode != 0:
                    logger.info("LaunchAgent successfully unloaded")
                else:
                    logger.warning("LaunchAgent may still be loaded")
                    
            except Exception as e:
                logger.error(f"Failed to unload LaunchAgent: {e}")
        
        # On Linux with systemd, try to stop the user service
        elif os.path.exists("/etc/debian_version") or os.path.exists("/etc/linuxmint/info"):
            if shutil.which("systemctl"):
                try:
                    logger.info("Attempting to stop systemd user service")
                    subprocess.run(
                        ["systemctl", "--user", "stop", "dictation.service"],
                        check=False,
                        capture_output=True
                    )
                    
                    # Verify the service is stopped
                    result = subprocess.run(
                        ["systemctl", "--user", "is-active", "dictation.service"],
                        check=False,
                        capture_output=True
                    )
                    
                    if b"inactive" in result.stdout or b"failed" in result.stdout:
                        logger.info("Systemd service successfully stopped")
                    else:
                        logger.warning("Systemd service may still be running")
                        
                except Exception as e:
                    logger.error(f"Failed to stop systemd service: {e}")
        
        # Make sure any file operations have completed
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
            
        # Small delay to ensure subprocess operations and file writes complete
        time.sleep(0.5)
            
        logger.info("Exiting application completely")
        # Use os._exit to force immediate termination of the process
        # This is needed because regular sys.exit() might not work if we're in a daemon thread
        os._exit(0)

    def _toggle_sounds(self, enabled: bool):
        """Toggle sound effects on/off."""
        self.enable_sounds = enabled
        logger.info(f"Sound effects {'enabled' if enabled else 'disabled'}")

    def _change_language(self, language_code: str):
        """Change the transcription language."""
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

            # Create new transcriber instance with appropriate model name
            if transcriber_id == "openai":
                self.transcriber = OpenAITranscriber(
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
            # Update status icon first
            with self.status_icon_lock:
                logger.info("Transcribing audio...")
                self.status_icon.update_state(StatusIconState.TRANSCRIBING)

            # Then start transcription (which will trigger state transition when done)
            self.transcriber.transcribe(event)
        except Exception as e:
            logger.error(f"Error starting transcription: {str(e)}")
            with self.status_icon_lock:
                self.status_icon.update_state(StatusIconState.ERROR)
            self.m.to_READY()

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
            # Get platform-specific handler
            platform_handler = PlatformHandler.get_handler()

            # Normalize trigger key
            trigger_key = self._normalize_key(self.args.trigger_key)

            # Get platform-specific cancel key
            cancel_key = platform_handler.get_cancel_key()

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
                    self.status_icon.stop()
                except Exception as e:
                    logger.error(f"Error stopping status icon: {str(e)}")

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

            # Get platform-specific handler
            platform_handler = PlatformHandler.get_handler()

            # Run key listener in a platform-specific way
            platform_handler.run_key_listener(self, keylistener)
        except Exception as e:
            logger.error(f"Application error: {str(e)}")
            # Try to stop the status icon
            if hasattr(self, "status_icon"):
                try:
                    self.status_icon.stop()
                except Exception as cleanup_error:
                    logger.error(f"Error stopping status icon: {cleanup_error}")
            raise

import time
import threading
import logging
from pathlib import Path
import numpy as np
from pynput import keyboard
from .state_machine import States, create_state_machine
from ..services.recorder import Recorder
from ..services.transcriber import GroqTranscriber
from ..services.input_handler import KeyboardReplayer, DoubleKeyListener
from ..core.utils import playsound, loadwav

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
        self.timer = None
        self.last_state_change = 0
        self.state_change_delay = 0.5  # Minimum delay between state changes in seconds
        
        # Initialize state machine
        self.m = create_state_machine()
        
        # Initialize components
        self.recorder = Recorder(self.m.finish_recording)
        self.transcriber = GroqTranscriber(self.m.finish_transcribing, args.model_name)
        self.replayer = KeyboardReplayer(self.m.finish_replaying)
        
        # Configure state machine callbacks
        self.m.on_enter_RECORDING(self._safe_start_recording)
        self.m.on_enter_TRANSCRIBING(self._safe_start_transcription)
        self.m.on_enter_REPLAYING(self._safe_start_replay)
        
        # Load sound effects with validation
        self.SOUND_EFFECTS = self._load_sound_effects()
        
        # Configure ready state message
        self.m.on_enter_READY(
            lambda *_: logger.info(
                f"Double tap {self.args.trigger_key} to start recording. "
                f"Tap once to stop recording"
            )
        )

    def _load_sound_effects(self) -> dict[str, np.ndarray | None]:
        """
        Load and validate sound effects.
        
        Returns:
            dict: Mapping of sound effect names to audio data
        """
        sounds = {
            "start_recording": loadwav("assets/107786__leviclaassen__beepbeep.wav"),
            "finish_recording": loadwav("assets/559318__alejo902__sonido-3-regulator.wav"),
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
            self.m.to_READY()

    def _safe_start_transcription(self, event) -> None:
        """Wrapper for transcription start with error handling."""
        try:
            self.transcriber.transcribe(event)
        except Exception as e:
            logger.error(f"Error starting transcription: {str(e)}")
            self.m.to_READY()

    def _safe_start_replay(self, event) -> None:
        """Wrapper for replay start with error handling."""
        try:
            self.replayer.replay(event)
        except Exception as e:
            logger.error(f"Error starting replay: {str(e)}")
            self.m.to_READY()

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
                    self.timer = threading.Timer(self.args.max_time, self.timer_stop)
                    self.timer.start()
                    
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
                if self.timer is not None:
                    self.timer.cancel()
                    self.timer = None
                    
                self.beep("finish_recording", wait=False)
                self.last_state_change = time.time()
                return True
            except Exception as e:
                logger.error(f"Error stopping recording: {str(e)}")
                return False
        return False

    def timer_stop(self) -> None:
        """Handle timer expiration by stopping recording."""
        logger.info('Timer stop')
        try:
            self.stop()
        except Exception as e:
            logger.error(f"Error in timer stop: {str(e)}")

    def _setup_key_listener(self) -> DoubleKeyListener:
        """
        Configure and return the key listener with normalized trigger key.
        
        Returns:
            DoubleKeyListener: Configured key listener instance
        """
        def normalize_key(key: str) -> str:
            """
            Normalize key string to handle platform-specific variations.
            
            Args:
                key: Key string to normalize
                
            Returns:
                str: Normalized key string
            """
            key = key.replace('<win>', '<cmd>').replace('<super>', '<cmd>')
            try:
                parsed_key = keyboard.HotKey.parse(key)[0]
                logger.info(f'Using trigger key: {parsed_key}')
                return parsed_key
            except ValueError as e:
                logger.error(f"Invalid trigger key: {key} - {str(e)}")
                raise

        try:
            trigger_key = normalize_key(self.args.trigger_key)
            return DoubleKeyListener(self.start, self.stop, trigger_key)
        except Exception as e:
            logger.error(f"Error setting up key listener: {str(e)}")
            raise

    def run(self) -> None:
        """Main application loop that handles key listening and state management."""
        try:
            # Set up key listener
            keylistener = self._setup_key_listener()
            
            # Initialize state machine
            self.m.to_READY()
            
            # Start key listener
            keylistener.run()
        except Exception as e:
            logger.error(f"Application error: {str(e)}")
            raise

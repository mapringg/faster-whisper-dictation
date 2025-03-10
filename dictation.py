import enum
import time
import threading
import argparse
import os
import requests
import json
import tempfile
import logging
from pynput import keyboard
from transitions import Machine
from pathlib import Path
import soundfile as sf
import sounddevice as sd
import numpy as np

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/dictation.log')
    ]
)
logger = logging.getLogger(__name__)

# Configure sounddevice defaults
sd.default.samplerate = 44100
sd.default.channels = 1

def get_default_devices():
    """Get the current default input and output devices."""
    try:
        devices = sd.query_devices()
        default_input = sd.default.device[0]
        default_output = sd.default.device[1]
        
        input_info = devices[default_input] if default_input is not None else None
        output_info = devices[default_output] if default_output is not None else None
        
        logger.info(f"Default input device: {input_info['name'] if input_info else 'None'}")
        logger.info(f"Default output device: {output_info['name'] if output_info else 'None'}")
        
        return default_input, default_output
    except Exception as e:
        logger.error(f"Error getting default devices: {str(e)}")
        return None, None

def playsound(data, wait=True):
    """Play audio data through the default output device."""
    try:
        _, output_device = get_default_devices()
        if output_device is not None:
            sd.play(data, device=output_device)
            if wait:
                sd.wait()
        else:
            logger.error("No default output device available")
    except Exception as e:
        logger.error(f"Error playing sound: {str(e)}")

def loadwav(filename):
    """Load a WAV file as float32 data."""
    try:
        data, _ = sf.read(filename, dtype='float32')
        return data
    except Exception as e:
        logger.error(f"Error loading WAV file {filename}: {str(e)}")
        return None


def load_env_from_file(env_file_path):
    """Load environment variables from a file."""
    try:
        if not os.path.exists(env_file_path):
            return False
        
        with open(env_file_path, 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        return True
    except Exception as e:
        logger.error(f"Error loading environment file {env_file_path}: {str(e)}")
        return False


class GroqTranscriber:
    """Handles audio transcription using the Groq API."""
    
    def __init__(self, callback, model="whisper-large-v3"):
        """
        Initialize the transcriber with callback and model.
        
        Args:
            callback: Function to call with transcription results
            model: Name of the Groq model to use (default: whisper-large-v3)
        """
        self.callback = callback
        self.model = model
        self.max_retries = 3
        self.retry_delay = 1  # Initial delay in seconds
        
        # Try to get API key from environment
        self.api_key = os.environ.get("GROQ_API_KEY")
        
        # If not found, try to load from ~/.env file
        if not self.api_key:
            env_file = os.path.join(str(Path.home()), '.env')
            if load_env_from_file(env_file):
                self.api_key = os.environ.get("GROQ_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY environment variable is not set. "
                "Please set it in your environment or in ~/.env file."
            )
        
    def save_audio_to_wav(self, audio_data: np.ndarray, filename: str) -> bool:
        """
        Save audio data to a WAV file.
        
        Args:
            audio_data: Numpy array containing audio samples
            filename: Path to save the WAV file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            sf.write(filename, audio_data, 16000, format='WAV', subtype='PCM_16')
            return True
        except Exception as e:
            logger.error(f"Error saving audio to WAV: {str(e)}")
            return False

    def make_api_request(self, temp_filename: str, language: str | None = None) -> dict | None:
        """
        Make API request with retry mechanism and enhanced error handling.
        
        Args:
            temp_filename: Path to temporary WAV file
            language: Optional language code for transcription
            
        Returns:
            dict: JSON response from API if successful
            None: If all retries failed
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        for attempt in range(self.max_retries):
            try:
                with open(temp_filename, 'rb') as audio_file:
                    files = {'file': audio_file}
                    data = {
                        'model': self.model,
                        'prompt': "Transcribe this audio, which may contain technical discussions related to software development, programming languages, APIs, and system architecture. Use precise terminology where appropriate.",
                        'temperature': 0.0
                    }
                    
                    if language and isinstance(language, str):
                        data['language'] = language
                        logger.info(f"Using language: {language}")
                    
                    response = requests.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=30  # Add timeout
                    )
                    
                    # Handle successful response
                    if response.status_code == 200:
                        try:
                            return response.json()
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode JSON response: {str(e)}")
                            continue
                    
                    # Handle rate limiting
                    elif response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', self.retry_delay))
                        logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                        time.sleep(retry_after)
                        continue
                    
                    # Handle other API errors
                    else:
                        error_msg = f"API error: {response.status_code} - {response.text}"
                        logger.error(error_msg)
                        
                        # Handle specific error cases
                        if response.status_code == 401:
                            logger.error("Invalid API key - please check your GROQ_API_KEY")
                            break
                        elif response.status_code == 413:
                            logger.error("Audio file too large - try recording a shorter segment")
                            break
                        
                        # Exponential backoff for retries
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (2 ** attempt)
                            logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                        
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error: {str(e)}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
        
        return None

    def transcribe(self, event) -> None:
        """
        Handle the transcription process from audio input to text output.
        
        Args:
            event: State machine event containing audio data and language info
            
        Returns:
            None: Results are passed to the callback function
        """
        logger.info('Starting transcription with Groq API...')
        audio = event.kwargs.get('audio', None)
        language = event.kwargs.get('language')
        
        # Validate audio input
        if audio is None or not isinstance(audio, np.ndarray) or audio.size == 0:
            logger.warning("Invalid audio data provided")
            self.callback(segments=[])
            return
            
        # Validate audio format
        if audio.dtype != np.float32:
            logger.warning(f"Audio data has incorrect dtype: {audio.dtype}")
            self.callback(segments=[])
            return
            
        # Save audio to a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_filename = temp_file.name
            
        try:
            # Save audio and handle potential errors
            if not self.save_audio_to_wav(audio, temp_filename):
                logger.error("Failed to save audio to temporary file")
                self.callback(segments=[])
                return
                
            # Make API request and handle response
            result = self.make_api_request(temp_filename, language)
            
            if result:
                text = result.get("text", "")
                if not text:
                    logger.warning("Received empty transcription")
                
                logger.info("Transcription successful")
                
                # Create a simple segment object to match the Whisper format
                class Segment:
                    def __init__(self, text: str):
                        self.text = text
                
                segments = [Segment(text)]
                self.callback(segments=segments)
            else:
                logger.error("Failed to get transcription after retries")
                self.callback(segments=[])
        
        except Exception as e:
            logger.error(f"Error during transcription: {str(e)}")
            self.callback(segments=[])
        
        finally:
            # Clean up the temporary file
            try:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except Exception as e:
                logger.error(f"Error deleting temporary file: {str(e)}")


class Recorder:
    """Handles audio recording functionality with state management and error handling."""
    
    def __init__(self, callback):
        """
        Initialize the recorder with a callback function.
        
        Args:
            callback: Function to call with recorded audio data
        """
        self.callback = callback
        self.recording = False
        self.stream = None
        self.frames = []
        self.lock = threading.Lock()  # Thread-safe state management

    def start(self, event) -> None:
        """Start recording in a new thread."""
        logger.info('Starting recording...')
        with self.lock:
            self._cleanup_previous_session()
            
        language = event.kwargs.get('language') if hasattr(event, 'kwargs') else None
        thread = threading.Thread(target=self._record_impl, args=(language,))
        thread.start()

    def stop(self) -> None:
        """Stop recording and cleanup resources."""
        logger.info('Stopping recording...')
        with self.lock:
            self.recording = False
            self._cleanup_stream()

    def _cleanup_previous_session(self) -> None:
        """Clean up any existing recording session."""
        self.recording = False
        self.frames = []
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error cleaning up previous stream: {str(e)}")
            finally:
                self.stream = None

    def _setup_audio_stream(self, input_device: int) -> sd.InputStream | None:
        """
        Set up and return an audio input stream.
        
        Args:
            input_device: Device ID for audio input
            
        Returns:
            sd.InputStream: Configured audio stream
            None: If setup fails
        """
        def callback(indata: np.ndarray, frames: int, time, status: sd.CallbackFlags):
            """Capture incoming audio data while recording is active."""
            if status:
                logger.warning(f"Stream callback status: {status}")
            if self.recording:
                self.frames.append(indata.copy())
        
        try:
            return sd.InputStream(
                device=input_device,
                channels=1,
                samplerate=16000,
                callback=callback,
                dtype=np.float32
            )
        except sd.PortAudioError as e:
            logger.error(f"Error setting up audio stream: {str(e)}")
            return None

    def _process_recorded_audio(self, language: str | None) -> tuple[np.ndarray, str | None] | None:
        """
        Process recorded audio frames into a single array.
        
        Args:
            language: Optional language code for transcription
            
        Returns:
            tuple: (audio_data, language) if successful
            None: If no audio was recorded
        """
        if not self.frames:
            logger.warning("No audio data recorded")
            return None
            
        try:
            audio_data = np.concatenate(self.frames, axis=0)
            if language and isinstance(language, str):
                logger.info(f"Passing language to transcriber: {language}")
                return audio_data, language
            return audio_data, None
        except Exception as e:
            logger.error(f"Error processing audio data: {str(e)}")
            return None

    def _cleanup_stream(self) -> None:
        """Safely stop and close the audio stream."""
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error closing audio stream: {str(e)}")
            finally:
                self.stream = None

    def _record_impl(self, language: str | None = None) -> None:
        """
        Main recording implementation that handles audio capture.
        
        Args:
            language: Optional language code for transcription
        """
        try:
            # Get and validate input device
            input_device, _ = get_default_devices()
            if input_device is None:
                logger.error("No default input device available")
                self.callback(audio=None)
                return

            # Initialize recording state
            with self.lock:
                self.recording = True
                self.frames = []
            
            # Set up and run audio stream
            self.stream = self._setup_audio_stream(input_device)
            if self.stream is None:
                self.callback(audio=None)
                return
                
            with self.stream:
                while self.recording:
                    sd.sleep(100)  # Sleep to prevent busy-waiting

            # Process and return recorded audio
            processed_audio = self._process_recorded_audio(language)
            if processed_audio:
                audio_data, lang = processed_audio
                self.callback(audio=audio_data, language=lang)
            else:
                self.callback(audio=None)
                
        except sd.PortAudioError as e:
            logger.error(f"Audio device error during recording: {str(e)}")
            self.callback(audio=None)
        except Exception as e:
            logger.error(f"Unexpected error during recording: {str(e)}")
            self.callback(audio=None)
        finally:
            with self.lock:
                self.recording = False
                self._cleanup_stream()


class KeyboardReplayer:
    """Handles typing out transcribed text with rate limiting and error handling."""
    
    def __init__(self, callback):
        """
        Initialize the replayer with a callback function.
        
        Args:
            callback: Function to call after typing is complete
        """
        self.callback = callback
        self.kb = keyboard.Controller()
        self.typing_delay = 0.0025  # Delay between keystrokes in seconds
        self.max_retries = 3
        self.lock = threading.Lock()  # Thread-safe state management

    def _validate_segments(self, segments: list) -> bool:
        """
        Validate the transcription segments.
        
        Args:
            segments: List of transcription segments
            
        Returns:
            bool: True if segments are valid, False otherwise
        """
        if not isinstance(segments, list):
            logger.error(f"Invalid segments type: {type(segments)}")
            return False
            
        for segment in segments:
            if not hasattr(segment, 'text') or not isinstance(segment.text, str):
                logger.error("Segment missing text attribute or text is not a string")
                return False
                
        return True

    def _type_with_retry(self, char: str) -> bool:
        """
        Type a single character with retry mechanism.
        
        Args:
            char: Character to type
            
        Returns:
            bool: True if successful, False after max retries
        """
        for attempt in range(self.max_retries):
            try:
                self.kb.type(char)
                return True
            except Exception as e:
                logger.warning(f"Error typing character '{char}' (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
        
        logger.error(f"Failed to type character '{char}' after {self.max_retries} attempts")
        return False

    def replay(self, event) -> None:
        """
        Handle the text replay process with error handling and rate limiting.
        
        Args:
            event: State machine event containing transcription segments
        """
        logger.info('Starting text replay...')
        segments = event.kwargs.get('segments', [])
        text_buffer = []
        
        # Validate input segments
        if not self._validate_segments(segments):
            logger.error("Invalid transcription segments")
            self.callback()
            return
            
        try:
            with self.lock:
                # Process each segment
                for segment in segments:
                    is_first = True
                    
                    # Process each character in segment
                    for char in segment.text:
                        # Skip leading space in first segment
                        if is_first and char == " ":
                            is_first = False
                            continue
                            
                        # Type character with retry mechanism
                        if self._type_with_retry(char):
                            text_buffer.append(char)
                            time.sleep(self.typing_delay)
                        else:
                            logger.warning(f"Skipping character '{char}' due to repeated errors")
                            
                # Log final typed text
                if text_buffer:
                    logger.info(f"Successfully typed text: {''.join(text_buffer)}")
                else:
                    logger.warning("No text was typed")
                    
        except Exception as e:
            logger.error(f"Unexpected error during text replay: {str(e)}")
        finally:
            self.callback()


class KeyListener:
    """Handles single key press events with error handling and cleanup."""
    
    def __init__(self, callback, key: str):
        """
        Initialize the key listener with callback and key binding.
        
        Args:
            callback: Function to call when key is pressed
            key: Key combination to listen for (e.g. '<alt_l>')
        """
        self.callback = callback
        self.key = key
        self.listener = None
        self.lock = threading.Lock()  # Thread-safe state management

    def _validate_key(self) -> bool:
        """
        Validate the key combination.
        
        Returns:
            bool: True if key is valid, False otherwise
        """
        try:
            keyboard.HotKey.parse(self.key)
            return True
        except ValueError as e:
            logger.error(f"Invalid key combination '{self.key}': {str(e)}")
            return False

    def run(self) -> None:
        """Start listening for key presses with error handling."""
        if not self._validate_key():
            logger.error("Cannot start key listener with invalid key")
            return
            
        try:
            with self.lock:
                self.listener = keyboard.GlobalHotKeys({self.key: self._safe_callback})
                self.listener.start()
                self.listener.join()
        except Exception as e:
            logger.error(f"Error in key listener: {str(e)}")
        finally:
            self._cleanup()

    def _safe_callback(self) -> None:
        """Wrapper for callback with error handling."""
        try:
            self.callback()
        except Exception as e:
            logger.error(f"Error in key callback: {str(e)}")

    def _cleanup(self) -> None:
        """Clean up listener resources."""
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception as e:
                logger.error(f"Error stopping key listener: {str(e)}")
            finally:
                self.listener = None


class DoubleKeyListener:
    """Handles double-click key events with rate limiting and error handling."""
    
    def __init__(self, activate_callback, deactivate_callback, key=keyboard.Key.cmd_r):
        """
        Initialize the double key listener with callbacks and key binding.
        
        Args:
            activate_callback: Function to call on double-click
            deactivate_callback: Function to call on single-click
            key: Key to listen for (default: right command key)
        """
        self.activate_callback = activate_callback
        self.deactivate_callback = deactivate_callback
        self.key = key
        self.last_press_time = 0
        self.double_click_threshold = 0.5  # Seconds between clicks
        self.min_press_duration = 0.1  # Minimum press duration in seconds
        self.listener = None
        self.lock = threading.Lock()  # Thread-safe state management

    def _safe_activate(self) -> None:
        """Wrapper for activate callback with error handling."""
        try:
            self.activate_callback()
        except Exception as e:
            logger.error(f"Error in activate callback: {str(e)}")

    def _safe_deactivate(self) -> None:
        """Wrapper for deactivate callback with error handling."""
        try:
            self.deactivate_callback()
        except Exception as e:
            logger.error(f"Error in deactivate callback: {str(e)}")

    def on_press(self, key) -> bool | None:
        """
        Handle key press events with rate limiting.
        
        Args:
            key: The key that was pressed
            
        Returns:
            bool | None: Return value depends on pynput requirements
        """
        if key != self.key:
            return None
            
        current_time = time.time()
        time_since_last = current_time - self.last_press_time
        
        # Rate limiting
        if time_since_last < self.min_press_duration:
            return None
            
        self.last_press_time = current_time
        
        # Determine if double click
        is_dbl_click = time_since_last < self.double_click_threshold
        
        try:
            if is_dbl_click:
                self._safe_activate()
            else:
                self._safe_deactivate()
        except Exception as e:
            logger.error(f"Error handling key press: {str(e)}")
            
        return None

    def on_release(self, key) -> None:
        """Handle key release events."""
        pass

    def run(self) -> None:
        """Start listening for key events with error handling."""
        try:
            with self.lock:
                self.listener = keyboard.Listener(
                    on_press=self.on_press,
                    on_release=self.on_release
                )
                self.listener.start()
                self.listener.join()
        except Exception as e:
            logger.error(f"Error in double key listener: {str(e)}")
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """Clean up listener resources."""
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception as e:
                logger.error(f"Error stopping double key listener: {str(e)}")
            finally:
                self.listener = None


def parse_args():
    parser = argparse.ArgumentParser(description='Dictation app powered by Groq API')
    parser.add_argument('-m', '--model-name', type=str, default='whisper-large-v3',
                        help='''\
Groq model to use for transcription.
Default: whisper-large-v3.''')
    parser.add_argument('-d', '--trigger-key', type=str, default='<alt_l>',
                        help='''\
Key to use for triggering recording. Double tap to start, single tap to stop.
Default: Left Alt (<alt_l>)

See https://pynput.readthedocs.io/en/latest/keyboard.html#pynput.keyboard.Key for supported keys.''')
    parser.add_argument('-t', '--max-time', type=int, default=30,
                        help='''\
Specify the maximum recording time in seconds.
The app will automatically stop recording after this duration.
Default: 30 seconds.''')
    parser.add_argument('-l', '--language', type=str, default='en',
                        help='''\
Specify the language of the audio for better transcription accuracy.
If not specified, defaults to English ('en').
Example: 'en' for English, 'fr' for French, etc.

Supported languages: af, am, ar, as, az, ba, be, bg, bn, bo, br, bs, ca, cs, cy, da, de, el, en, es, et, eu, fa, fi, fo, fr, gl, gu, ha, haw, he, hi, hr, ht, hu, hy, id, is, it, ja, jv, ka, kk, km, kn, ko, la, lb, ln, lo, lt, lv, mg, mi, mk, ml, mn, mr, ms, mt, my, ne, nl, nn, no, oc, pa, pl, ps, pt, ro, ru, sa, sd, si, sk, sl, sn, so, sq, sr, su, sv, sw, ta, te, tg, th, tl, tr, tt, uk, ur, uz, vi, yi, yo, yue, zh''')

    args = parser.parse_args()
    return args


class States(enum.Enum):
    READY        = 1
    RECORDING    = 2
    TRANSCRIBING = 3
    REPLAYING    = 4


transitions = [
    {'trigger':'start_recording'     ,'source': States.READY        ,'dest': States.RECORDING    },
    {'trigger':'finish_recording'    ,'source': States.RECORDING    ,'dest': States.TRANSCRIBING },
    {'trigger':'finish_transcribing' ,'source': States.TRANSCRIBING ,'dest': States.REPLAYING    },
    {'trigger':'finish_replaying'    ,'source': States.REPLAYING    ,'dest': States.READY        },
]


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
        self.m = Machine(
            states=States,
            transitions=transitions,
            send_event=True,
            ignore_invalid_triggers=True,
            initial=States.READY
        )
        
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


if __name__ == "__main__":
    args = parse_args()
    App(args).run()

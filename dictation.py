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
    def __init__(self, callback, model="whisper-large-v3-turbo"):
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
            raise ValueError("GROQ_API_KEY environment variable is not set. Please set it in your environment or in ~/.env file.")
        
    def save_audio_to_wav(self, audio_data, filename):
        """Save audio data to a WAV file."""
        try:
            sf.write(filename, audio_data, 16000, format='WAV', subtype='PCM_16')
            return True
        except Exception as e:
            logger.error(f"Error saving audio to WAV: {str(e)}")
            return False

    def make_api_request(self, temp_filename, language=None):
        """Make API request with retry mechanism."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        for attempt in range(self.max_retries):
            try:
                with open(temp_filename, 'rb') as audio_file:
                    files = {'file': audio_file}
                    data = {
                        'model': self.model,
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
                    
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 429:  # Rate limit
                        retry_after = int(response.headers.get('Retry-After', self.retry_delay))
                        logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                        time.sleep(retry_after)
                    else:
                        logger.error(f"API error: {response.status_code} - {response.text}")
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                            logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                        
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error: {str(e)}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
        
        return None

    def transcribe(self, event):
        logger.info('Starting transcription with Groq API...')
        audio = event.kwargs.get('audio', None)
        language = event.kwargs.get('language')
        
        if audio is None:
            logger.warning("No audio data provided")
            self.callback(segments=[])
            return
            
        # Save audio to a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_filename = temp_file.name
            
        try:
            if not self.save_audio_to_wav(audio, temp_filename):
                self.callback(segments=[])
                return
                
            result = self.make_api_request(temp_filename, language)
            
            if result:
                text = result.get("text", "")
                logger.info("Transcription successful")
                
                # Create a simple segment object to match the Whisper format
                class Segment:
                    def __init__(self, text):
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
                os.unlink(temp_filename)
            except Exception as e:
                logger.error(f"Error deleting temporary file: {str(e)}")


class Recorder:
    def __init__(self, callback):
        self.callback = callback
        self.recording = False
        self.stream = None
        self.frames = []

    def start(self, event):
        logger.info('Starting recording...')
        language = event.kwargs.get('language') if hasattr(event, 'kwargs') else None
        thread = threading.Thread(target=self._record_impl, args=(language,))
        thread.start()

    def stop(self):
        logger.info('Stopping recording...')
        self.recording = False
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error stopping stream: {str(e)}")

    def _record_impl(self, language=None):
        try:
            self.recording = True
            self.frames = []
            
            # Get default input device
            input_device, _ = get_default_devices()
            if input_device is None:
                raise RuntimeError("No default input device available")

            def callback(indata, frames, time, status):
                if status:
                    logger.warning(f"Stream callback status: {status}")
                if self.recording:
                    self.frames.append(indata.copy())

            # Open the input stream
            self.stream = sd.InputStream(
                device=input_device,
                channels=1,
                samplerate=16000,
                callback=callback,
                dtype=np.float32
            )
            
            with self.stream:
                while self.recording:
                    sd.sleep(100)  # Sleep to prevent busy-waiting

            # Combine all frames
            if self.frames:
                audio_data = np.concatenate(self.frames, axis=0)
                if language and isinstance(language, str):
                    logger.info(f"Passing language to transcriber: {language}")
                    self.callback(audio=audio_data, language=language)
                else:
                    self.callback(audio=audio_data)
            else:
                logger.warning("No audio data recorded")
                
        except Exception as e:
            logger.error(f"Error during recording: {str(e)}")
            self.recording = False


class KeyboardReplayer():
    def __init__(self, callback):
        self.callback = callback
        self.kb = keyboard.Controller()
        
    def replay(self, event):
        logger.info('Typing transcribed words...')
        segments = event.kwargs.get('segments', [])
        text_buffer = []
        
        for segment in segments:
            is_first = True
            for element in segment.text:
                if is_first and element == " ":
                    is_first = False
                    continue
                try:
                    text_buffer.append(element)
                    self.kb.type(element)
                    time.sleep(0.0025)
                except Exception as e:
                    logger.error(f"Error typing character '{element}': {str(e)}")
        
        if text_buffer:
            logger.info(f"Typed text: {''.join(text_buffer)}")
        else:
            logger.warning("No text was typed")
            
        self.callback()


class KeyListener():
    def __init__(self, callback, key):
        self.callback = callback
        self.key = key
    def run(self):
        with keyboard.GlobalHotKeys({self.key : self.callback}) as h:
            h.join()


class DoubleKeyListener():
    def __init__(self, activate_callback, deactivate_callback, key=keyboard.Key.cmd_r):
        self.activate_callback = activate_callback
        self.deactivate_callback = deactivate_callback
        self.key = key
        self.pressed = 0
        self.last_press_time = 0

    def on_press(self, key):
        if key == self.key:
            current_time = time.time()
            is_dbl_click = current_time - self.last_press_time < 0.5
            self.last_press_time = current_time
            if is_dbl_click:
                return self.activate_callback()
            else:
                return self.deactivate_callback()

    def on_release(self, key):
        pass
    def run(self):
        with keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release) as listener:
            listener.join()


def parse_args():
    parser = argparse.ArgumentParser(description='Dictation app powered by Groq API')
    parser.add_argument('-m', '--model-name', type=str, default='whisper-large-v3-turbo',
                        help='''\
Groq model to use for transcription.
Default: whisper-large-v3-turbo.''')
    parser.add_argument('-k', '--key-combo', type=str,
                        help='''\
Specify the key combination to toggle the app.

See https://pynput.readthedocs.io/en/latest/keyboard.html#pynput.keyboard.Key for a list of keys supported.

Examples: <cmd_l>+<alt>+x , <ctrl>+<alt>+a. Note on windows, the winkey is specified using <cmd>.

Default: <win>+z on Windows (see below for MacOS and Linux defaults).''')
    parser.add_argument('-d', '--double-key', type=str,
                        help='''\
If key-combo is not set, on macOS/linux the default behavior is double tapping a key to start recording.
Tap the same key again to stop recording.

On MacOS and on Linux the default key is Left Alt

You can set to a different key for double triggering.

''')
    parser.add_argument('-t', '--max-time', type=int, default=30,
                        help='''\
Specify the maximum recording time in seconds.
The app will automatically stop recording after this duration.
Default: 30 seconds.''')
    parser.add_argument('-l', '--language', type=str, default=None,
                        help='''\
Specify the language of the audio for better transcription accuracy.
If not specified, Groq will auto-detect the language.
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


class App():
    def __init__(self, args):
        m = Machine(states=States, transitions=transitions, send_event=True, ignore_invalid_triggers=True, initial=States.READY)

        self.m = m
        self.args = args
        self.recorder    = Recorder(m.finish_recording)
        self.transcriber = GroqTranscriber(m.finish_transcribing, args.model_name)
        self.replayer    = KeyboardReplayer(m.finish_replaying)
        self.timer = None
        self.language = args.language

        m.on_enter_RECORDING(self.recorder.start)
        m.on_enter_TRANSCRIBING(self.transcriber.transcribe)
        m.on_enter_REPLAYING(self.replayer.replay)

        # Sound effects attribution:
        # start_recording: https://freesound.org/people/MATRIXXX_/sounds/523763/ (CC-BY)
        # finish_recording: https://freesound.org/people/MATRIXXX_/sounds/705952/ (CC-BY)
        self.SOUND_EFFECTS = {
            "start_recording": loadwav("assets/523763__matrixxx__select-granted-06.wav"),
            "finish_recording": loadwav("assets/705952__matrixxx__ai-technology.wav")
        }

    def beep(self, k, wait=True):
        # wait=True will block until the beeping sound finished playing before continue to start recording
        # just in case if the beep sound interfere with voice recording
        # when done recording, we don't want to block while continuing to transcribe while beeping async
        playsound(self.SOUND_EFFECTS[k], wait=wait)

    def start(self):
        if self.m.is_READY():
            self.beep("start_recording")
            if self.args.max_time:
                self.timer = threading.Timer(self.args.max_time, self.timer_stop)
                self.timer.start()
            self.m.start_recording(language=self.language)
            return True

    def stop(self):
        if self.m.is_RECORDING():
            self.recorder.stop()
            if self.timer is not None:
                self.timer.cancel()
            self.beep("finish_recording", wait=False)
            return True

    def timer_stop(self):
        logger.info('Timer stop')
        self.stop()

    def toggle(self):
        return self.start() or self.stop()

    def run(self):
        def normalize_key_names(keyseqs, parse=False):
            k = keyseqs.replace('<win>', '<cmd>').replace('<win_r>', '<cmd_r>').replace('<win_l>', '<cmd_l>').replace('<super>', '<cmd>').replace('<super_r>', '<cmd_r>').replace('<super_l>', '<cmd_l>')
            if parse:
                k = keyboard.HotKey.parse(k)[0]
            logger.info(f'Using key: {k}')
            return k

        # Re-import platform here since we need it for OS detection
        import platform
        if (platform.system() != 'Windows' and not self.args.key_combo) or self.args.double_key:
            key = self.args.double_key or '<alt_l>'
            keylistener = DoubleKeyListener(self.start, self.stop, normalize_key_names(key, parse=True))
            self.m.on_enter_READY(lambda *_: logger.info(f"Double tap {key} to start recording. Tap again to stop recording"))
        else:
            key = self.args.key_combo or '<win>+z'
            keylistener = KeyListener(self.toggle, normalize_key_names(key))
            self.m.on_enter_READY(lambda *_: logger.info(f"Press {key} to start/stop recording"))
        self.m.to_READY()
        keylistener.run()


if __name__ == "__main__":
    args = parse_args()
    App(args).run()

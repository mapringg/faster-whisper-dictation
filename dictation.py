import enum
import time
import threading
import argparse
import platform
import pyaudio
import numpy as np
import os
import requests
import json
import wave
import tempfile
from pynput import keyboard
from transitions import Machine
from pathlib import Path

if platform.system() == 'Windows':
    import winsound
    def playsound(s, wait=True):
        # SND_ASYNC winsound cannot play asynchronously from memory
        winsound.PlaySound(s, winsound.SND_MEMORY)
    def loadwav(filename):
        with open(filename, "rb") as f:
            data = f.read()
        return data            
else:
    import soundfile as sf
    import sounddevice # or pygame.mixer, py-simple-audio
    sounddevice.default.samplerate = 44100
    def playsound(s, wait=True):
        sounddevice.play(s) # samplerate=16000
        if wait:
            sounddevice.wait()
    def loadwav(filename):
        data, fs = sf.read(filename, dtype='float32')
        return data            


def load_env_from_file(env_file_path):
    """Load environment variables from a file."""
    if not os.path.exists(env_file_path):
        return False
    
    with open(env_file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    return True


class GroqTranscriber:
    def __init__(self, callback, model="whisper-large-v3-turbo"):
        self.callback = callback
        self.model = model
        
        # Try to get API key from environment
        self.api_key = os.environ.get("GROQ_API_KEY")
        
        # If not found, try to load from ~/.env file
        if not self.api_key:
            env_file = os.path.join(str(Path.home()), '.env')
            if load_env_from_file(env_file):
                self.api_key = os.environ.get("GROQ_API_KEY")
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set. Please set it in your environment or in ~/.env file.")
        
    def transcribe(self, event):
        print('Transcribing with Groq API...')
        audio = event.kwargs.get('audio', None)
        language = None
        
        # Extract language from the audio callback parameters
        if 'language' in event.kwargs:
            language = event.kwargs['language']
            print(f"Using language: {language}")
            
        if audio is not None:
            # Save audio to a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_filename = temp_file.name
                
            # Convert numpy array to WAV file
            with wave.open(temp_filename, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(16000)
                wf.writeframes((audio * 32768).astype(np.int16).tobytes())
            
            try:
                # Send the audio file to Groq API for transcription
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                # Create a prompt for the Groq API to transcribe the audio
                prompt = "Please transcribe the following audio accurately:"
                
                # Prepare the API request
                with open(temp_filename, 'rb') as audio_file:
                    files = {
                        'file': audio_file,
                    }
                    data = {
                        'model': self.model,
                        'prompt': prompt,
                        'temperature': 0.0
                    }
                    
                    # Add language parameter if specified
                    if language:
                        # Validate that language is a string and not an event object
                        if isinstance(language, str):
                            data['language'] = language
                        else:
                            print(f"Warning: Invalid language format: {language}, ignoring language parameter")
                    
                    # Make the API request to Groq
                    response = requests.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers=headers,
                        files=files,
                        data=data
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    text = result.get("text", "")
                    
                    # Create a simple segment object to match the Whisper format
                    class Segment:
                        def __init__(self, text):
                            self.text = text
                    
                    segments = [Segment(text)]
                    self.callback(segments=segments)
                else:
                    print(f"Error from Groq API: {response.status_code}")
                    print(response.text)
                    self.callback(segments=[])
            
            except Exception as e:
                print(f"Error during transcription: {str(e)}")
                self.callback(segments=[])
            
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_filename)
                except:
                    pass
        else:
            self.callback(segments=[])


class Recorder:
    def __init__(self, callback):
        self.callback = callback
        self.recording = False

    def start(self, event):
        print('Recording ...')
        # Extract language from event if it exists, otherwise use None
        language = None
        if hasattr(event, 'kwargs') and 'language' in event.kwargs:
            language = event.kwargs['language']
        thread = threading.Thread(target=self._record_impl, args=(language,))
        thread.start()

    def stop(self):
        print('Done recording.')
        self.recording = False

    def _record_impl(self, language=None):
        self.recording = True

        frames_per_buffer = 1024
        p = pyaudio.PyAudio()
        stream = p.open(format            = pyaudio.paInt16,
                        channels          = 1,
                        rate              = 16000,
                        frames_per_buffer = frames_per_buffer,
                        input             = True)
        frames = []

        while self.recording:
            data = stream.read(frames_per_buffer)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
        audio_data_fp32 = audio_data.astype(np.float32) / 32768.0

        # Pass language parameter to callback if it's a valid string
        if language and isinstance(language, str):
            print(f"Passing language to transcriber: {language}")
            self.callback(audio=audio_data_fp32, language=language)
        else:
            self.callback(audio=audio_data_fp32)


class KeyboardReplayer():
    def __init__(self, callback):
        self.callback = callback
        self.kb = keyboard.Controller()
    def replay(self, event):
        print('Typing transcribed words...')
        segments = event.kwargs.get('segments', [])
        for segment in segments:
            is_first = True
            for element in segment.text:
                if is_first and element == " ":
                    is_first = False
                    continue
                try:
                    print(element, end='')
                    self.kb.type(element)
                    time.sleep(0.0025)
                except:
                    pass
        print('')
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

        # https://freesound.org/people/leviclaassen/sounds/107786/
        # https://freesound.org/people/MATRIXXX_/
        self.SOUND_EFFECTS = {
            "start_recording": loadwav("assets/beepbeep.wav"),
            "finish_recording": loadwav("assets/beepbeep.wav")
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
        print('Timer stop')
        self.stop()

    def toggle(self):
        return self.start() or self.stop()

    def run(self):
        def normalize_key_names(keyseqs, parse=False):
            k = keyseqs.replace('<win>', '<cmd>').replace('<win_r>', '<cmd_r>').replace('<win_l>', '<cmd_l>').replace('<super>', '<cmd>').replace('<super_r>', '<cmd_r>').replace('<super_l>', '<cmd_l>')
            if parse:
                k = keyboard.HotKey.parse(k)[0]
            print('Using key:', k)
            return k

        if (platform.system() != 'Windows' and not self.args.key_combo) or self.args.double_key:
            key = self.args.double_key or '<alt_l>'
            keylistener= DoubleKeyListener(self.start, self.stop, normalize_key_names(key, parse=True))
            self.m.on_enter_READY(lambda *_: print("Double tap ", key, " to start recording. Tap again to stop recording"))
        else:
            key = self.args.key_combo or '<win>+z'
            keylistener= KeyListener(self.toggle, normalize_key_names(key))
            self.m.on_enter_READY(lambda *_: print("Press ", key, " to start/stop recording."))
        self.m.to_READY()
        keylistener.run()


if __name__ == "__main__":
    args = parse_args()
    App(args).run() 
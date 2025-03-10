import os
import logging
import soundfile as sf
import sounddevice as sd
import numpy as np
from pathlib import Path

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

import logging
import os
import time

import sounddevice as sd
import soundfile as sf

logger = logging.getLogger(__name__)

# Configure sounddevice defaults
sd.default.samplerate = 44100
sd.default.channels = 1


def refresh_devices():
    """
    Force a refresh of the audio devices system.
    Useful after hardware changes like connecting/disconnecting devices.
    """
    try:
        logger.info("Refreshing audio devices...")
        # Close and reinitialize PortAudio to detect device changes
        sd._terminate()
        time.sleep(0.5)  # Give system time to register changes
        sd._initialize()

        # Log available devices after refresh
        devices = sd.query_devices()
        logger.info(f"Found {len(devices)} audio devices after refresh")

        # Log all available input devices for debugging
        input_devices = [d for d in devices if d["max_input_channels"] > 0]
        logger.debug(f"Available input devices: {len(input_devices)}")
        for i, device in enumerate(input_devices):
            logger.debug(
                f"  {i}: {device['name']} (channels: {device['max_input_channels']})"
            )

        # Verify default devices are accessible
        default_input, default_output = get_default_devices()
        if default_input is None:
            logger.warning("No default input device detected after refresh")

        return True
    except Exception as e:
        logger.error(f"Error refreshing audio devices: {str(e)}")
        return False


def get_default_devices():
    """Get the current default input and output devices."""
    try:
        # Query the system for current devices and defaults
        devices = sd.query_devices()

        # Get the current system default devices (not cached values)
        host_apis = sd.query_hostapis()
        default_host_api = host_apis[sd.default.hostapi]

        default_input = default_host_api["default_input_device"]
        default_output = default_host_api["default_output_device"]

        input_info = devices[default_input] if default_input is not None else None
        output_info = devices[default_output] if default_output is not None else None

        logger.info(
            f"Default input device: {input_info['name'] if input_info else 'None'}"
        )
        logger.info(
            f"Default output device: {output_info['name'] if output_info else 'None'}"
        )

        return default_input, default_output
    except Exception as e:
        logger.error(f"Error getting default devices: {str(e)}")
        return None, None


def playsound(data, wait=True):
    """Play audio data through the default output device."""
    try:
        # Always get the current default output device right before playback
        devices = sd.query_devices()
        _, output_device = get_default_devices()

        # First try with the default device
        try:
            if output_device is not None and output_device < len(devices):
                sd.play(data, device=output_device)
                if wait:
                    sd.wait()
                return
        except Exception as e:
            logger.warning(
                f"Could not play on default device: {str(e)}, trying fallback options"
            )

        # If default device fails, try system default (without specifying device)
        try:
            logger.info("Trying system default output device")
            sd.play(data)
            if wait:
                sd.wait()
            return
        except Exception as e:
            logger.error(f"Error playing on system default: {str(e)}")

        logger.error("No available output device found for playback")
    except Exception as e:
        logger.error(f"Error playing sound: {str(e)}")


def loadwav(filename):
    """Load a WAV file as float32 data."""
    try:
        data, _ = sf.read(filename, dtype="float32")
        return data
    except Exception as e:
        logger.error(f"Error loading WAV file {filename}: {str(e)}")
        return None


def load_env_from_file(env_file_path):
    """Load environment variables from a file."""
    try:
        if not os.path.exists(env_file_path):
            return False

        with open(env_file_path) as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
        return True
    except Exception as e:
        logger.error(f"Error loading environment file {env_file_path}: {str(e)}")
        return False

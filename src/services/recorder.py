import logging
import threading

import numpy as np
import sounddevice as sd

from ..core.utils import get_default_devices, refresh_devices

logger = logging.getLogger(__name__)


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
        logger.info("Starting recording...")
        with self.lock:
            self._cleanup_previous_session()

        language = event.kwargs.get("language") if hasattr(event, "kwargs") else None
        thread = threading.Thread(target=self._record_impl, args=(language,))
        thread.start()

    def stop(self) -> None:
        """Stop recording and cleanup resources."""
        logger.info("Stopping recording...")
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
                if status.input_overflow:
                    logger.warning("Input overflow - audio data may be lost")
                if status.input_underflow:
                    logger.warning("Input underflow - audio device may be unavailable")
            if self.recording:
                self.frames.append(indata.copy())

        try:
            # Get detailed device info to verify it's valid
            try:
                device_info = sd.query_devices(input_device)
                logger.info(
                    f"Using audio device: {device_info['name']} (ID: {input_device})"
                )
                if device_info["max_input_channels"] < 1:
                    logger.error(f"Device has no input channels: {device_info}")
                    return None
            except Exception as e:
                logger.error(
                    f"Failed to query device info for device {input_device}: {str(e)}"
                )

            stream = sd.InputStream(
                device=input_device,
                channels=1,
                samplerate=16000,
                callback=callback,
                dtype=np.float32,
            )
            logger.info("Audio stream created successfully")
            return stream
        except sd.PortAudioError as e:
            logger.error(f"Error setting up audio stream: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error setting up audio stream: {str(e)}")
            return None

    def _process_recorded_audio(
        self, language: str | None
    ) -> tuple[np.ndarray, str | None] | None:
        """
        Process recorded audio frames into a single array.
        Check if the audio file size exceeds 40 MB.

        Args:
            language: Optional language code for transcription

        Returns:
            tuple: (audio_data, language) if successful
            None: If no audio was recorded or if file size exceeds limit
        """
        if not self.frames:
            logger.warning("No audio data recorded")
            return None

        try:
            audio_data = np.concatenate(self.frames, axis=0)

            # Check file size (40 MB limit)
            # Each sample is 4 bytes (float32) and we have 1 channel
            # 40 MB = 40 * 1024 * 1024 bytes
            max_size_bytes = 40 * 1024 * 1024
            estimated_size_bytes = audio_data.size * 4  # float32 = 4 bytes per sample

            if estimated_size_bytes > max_size_bytes:
                logger.warning(
                    f"Audio file too large: {estimated_size_bytes / (1024 * 1024):.2f} MB exceeds 40 MB limit"
                )
                logger.info("Truncating audio to fit within 40 MB limit")

                # Calculate how many samples we can keep
                max_samples = max_size_bytes // 4
                audio_data = audio_data[:max_samples]

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
            # Refresh audio devices to detect any hardware changes
            refresh_devices()

            # Get and validate input device - done right before starting recording
            # to ensure we use the most current system default devices
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
                logger.error("Failed to set up audio stream")
                self.callback(audio=None)
                return

            try:
                logger.info(f"Starting stream with input device: {input_device}")
                self.stream.start()
            except sd.PortAudioError as e:
                logger.error(f"Failed to start audio stream: {str(e)}")
                self.callback(audio=None)
                return

            with self.stream:
                while self.recording:
                    sd.sleep(100)  # Sleep to prevent busy-waiting

            # Process and return recorded audio
            processed_audio = self._process_recorded_audio(language)
            if processed_audio:
                audio_data, lang = processed_audio
                if len(self.frames) == 0:
                    logger.warning(
                        "Recording stopped immediately - no audio frames captured"
                    )
                    self.callback(audio=None)
                else:
                    logger.info(
                        f"Recording successful with {len(self.frames)} audio frames"
                    )
                    self.callback(audio=audio_data, language=lang)
            else:
                logger.warning("No processed audio available after recording")
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

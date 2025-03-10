import threading
import logging
import time
import numpy as np
import sounddevice as sd
from ..core.utils import get_default_devices

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

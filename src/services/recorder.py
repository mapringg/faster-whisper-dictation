import logging
import threading
from contextlib import contextmanager

import numpy as np
import sounddevice as sd

from ..core.utils import get_default_devices, refresh_devices

logger = logging.getLogger(__name__)


class Recorder:
    """Handles audio recording functionality with state management and error handling."""

    @contextmanager
    def _stream_context(self, input_device):
        """Context manager for audio stream setup and cleanup."""
        stream = None
        try:
            stream = self._setup_audio_stream(input_device)
            if stream is not None:
                try:
                    logger.info(f"Starting stream with input device: {input_device}")
                    stream.start()
                    self.stream = stream  # Store reference in instance
                    yield stream
                except sd.PortAudioError as e:
                    logger.error(f"Failed to start audio stream: {str(e)}")
                    yield None
            else:
                logger.error("Failed to set up audio stream")
                yield None
        except Exception as e:
            logger.error(f"Error in stream setup: {str(e)}")
            yield None
        finally:
            # Always clean up the stream
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception as e:
                    logger.error(f"Error closing audio stream: {str(e)}")
                finally:
                    self.stream = None

    @contextmanager
    def _recording_state(self):
        """Context manager for the recording state."""
        try:
            with self.lock:
                self._cleanup_previous_session()
                self.recording = True
                self.frames = []
            yield
        finally:
            with self.lock:
                self.recording = False

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
        # The _recording_state context manager will handle cleanup of previous session

        language = event.kwargs.get("language") if hasattr(event, "kwargs") else None
        thread = threading.Thread(target=self._record_impl, args=(language,))
        thread.start()

    def stop(self) -> None:
        """Stop recording."""
        logger.info("Stopping recording...")
        with self.lock:
            self.recording = False
        # Stream cleanup is handled by the context manager

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
            # Check if we have valid frames before processing
            valid_frames = [frame for frame in self.frames if frame is not None]

            # Clear original frames list immediately to free memory
            self.frames = []

            if not valid_frames:
                logger.warning("No valid audio frames to process")
                return None

            # Process frames in chunks to avoid excessive memory usage
            chunk_size = 50  # Smaller chunk size to reduce memory usage
            all_chunks = []

            for i in range(0, len(valid_frames), chunk_size):
                chunk_frames = valid_frames[i : i + chunk_size]
                if chunk_frames:
                    # Concatenate this chunk
                    chunk_data = np.concatenate(chunk_frames, axis=0)
                    all_chunks.append(chunk_data)
                    # Clear references to processed frames
                    for j in range(i, min(i + chunk_size, len(valid_frames))):
                        valid_frames[j] = None

                    # Force garbage collection periodically
                    if i % 200 == 0:
                        import gc

                        gc.collect()

            # Free memory from valid_frames
            valid_frames = None

            # Concatenate all chunks
            if all_chunks:
                audio_data = np.concatenate(all_chunks, axis=0)
                # Clear chunk list to free memory immediately
                for i in range(len(all_chunks)):
                    all_chunks[i] = None
                all_chunks = []
            else:
                logger.warning("No audio chunks processed")
                return None

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
                # Create a new array with just the data we need instead of slicing
                truncated_data = np.array(audio_data[:max_samples], copy=True)
                # Free the original array
                audio_data = None
                # Assign the truncated data
                audio_data = truncated_data

            # Force garbage collection
            import gc

            gc.collect()

            if language and isinstance(language, str):
                logger.info(f"Passing language to transcriber: {language}")
                return audio_data, language
            return audio_data, None
        except Exception as e:
            logger.error(f"Error processing audio data: {str(e)}")
            # Clear frames on error to avoid memory leaks
            self.frames = []

            # Force garbage collection
            import gc

            gc.collect()
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

            # Get and validate input device
            input_device, _ = get_default_devices()
            if input_device is None:
                logger.error("No default input device available")
                self.callback(audio=None)
                return

            # Use context managers for recording state and stream management
            with self._recording_state():
                with self._stream_context(input_device) as stream:
                    if stream is None:
                        self.callback(audio=None)
                        return

                    # Main recording loop
                    while self.recording:
                        sd.sleep(100)  # Sleep to prevent busy-waiting

                # Process recorded audio (after stream is closed but while still in recording state)
                # Store frame count before processing
                frame_count = len(self.frames)
                processed_audio = self._process_recorded_audio(language)

                if processed_audio:
                    audio_data, lang = processed_audio
                    if frame_count == 0:
                        logger.warning(
                            "Recording stopped immediately - no audio frames captured"
                        )
                        self.callback(audio=None)
                    else:
                        logger.info(
                            f"Recording successful with {frame_count} audio frames"
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

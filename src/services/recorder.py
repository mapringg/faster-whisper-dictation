import io
import logging
import threading
from contextlib import contextmanager

import numpy as np
import sounddevice as sd
import soundfile as sf

from ..core.utils import get_default_devices

logger = logging.getLogger(__name__)


class Recorder:
    """Handles audio recording functionality with state management and error handling."""

    @contextmanager
    def _stream_context(self, input_device):
        """Context manager for audio stream setup and cleanup."""
        stream = None
        try:
            # Reset error tracking at the start of each recording
            with self.lock:
                self.stream_error_count = 0
                self.persistent_stream_error = False

            stream = self._setup_audio_stream(input_device)
            if stream is not None:
                try:
                    logger.info(f"Starting stream with input device: {input_device}")
                    stream.start()
                    self.stream = stream  # Store reference in instance
                    yield stream
                except sd.PortAudioError as e:
                    logger.error(f"Failed to start audio stream: {str(e)}")
                    with self.lock:
                        self.persistent_stream_error = True
                    yield None
            else:
                logger.error("Failed to set up audio stream")
                with self.lock:
                    self.persistent_stream_error = True
                yield None
        except Exception as e:
            logger.error(f"Error in stream setup: {str(e)}")
            with self.lock:
                self.persistent_stream_error = True
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
        self.lock = threading.Lock()  # Thread-safe state management
        self.audio_buffer = None
        self.accumulated_audio_data = []

        # Stream error tracking
        self.stream_error_count = 0
        self.persistent_stream_error = False
        self.max_stream_errors = 5  # Maximum consecutive errors before giving up

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
            # Add debug info about the current state
            if self.audio_buffer is not None:
                logger.info("Audio buffer exists when stopping recording")
            else:
                logger.warning("Audio buffer is None when stopping recording")
        # Stream cleanup is handled by the context manager

    def _cleanup_previous_session(self) -> None:
        """Clean up any existing recording session."""
        self.recording = False
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error cleaning up previous stream: {str(e)}")
            finally:
                self.stream = None

        # Close and reset any existing audio buffer
        if self.audio_buffer is not None:
            try:
                if isinstance(self.audio_buffer, io.BytesIO):
                    self.audio_buffer.close()
                logger.info("Closed previous audio buffer")
            except Exception as e:
                logger.error(f"Error closing previous audio buffer: {str(e)}")
            finally:
                self.audio_buffer = None

        # Clear accumulated data
        self.accumulated_audio_data = []

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

                # Track stream errors
                if status.input_overflow or status.input_underflow:
                    with self.lock:
                        self.stream_error_count += 1

                        if status.input_overflow:
                            logger.warning(
                                f"Input overflow - audio data may be lost (error {self.stream_error_count}/{self.max_stream_errors})"
                            )
                        if status.input_underflow:
                            logger.warning(
                                f"Input underflow - audio device may be unavailable (error {self.stream_error_count}/{self.max_stream_errors})"
                            )

                        # If we've had too many consecutive errors, mark as persistent error
                        if self.stream_error_count >= self.max_stream_errors:
                            logger.error(
                                f"Persistent audio stream errors detected ({self.stream_error_count} consecutive errors)"
                            )
                            self.persistent_stream_error = True
                            self.recording = False  # Stop recording early
                else:
                    # Reset error count if this callback had no errors
                    with self.lock:
                        if self.stream_error_count > 0:
                            self.stream_error_count = 0

            # Only write data if we're recording
            with self.lock:
                if self.recording:
                    try:
                        # Check if we have valid audio data
                        if indata is not None and indata.size > 0:
                            # Log the first callback with data details
                            if not hasattr(callback, "first_data_logged"):
                                logger.info(
                                    f"First audio data received: shape={indata.shape}, dtype={indata.dtype}, max={np.max(np.abs(indata))}"
                                )
                                callback.first_data_logged = True

                            self.accumulated_audio_data.append(indata.copy())
                        else:
                            logger.warning("Received empty audio data in callback")
                    except Exception as e:
                        logger.error(f"Error accumulating audio data: {str(e)}")

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
            except sd.PortAudioError as e:
                logger.error(f"Invalid audio device {input_device}: {str(e)}")
                return None
            except Exception as e:
                logger.error(
                    f"Failed to query device info for device {input_device}: {str(e)}"
                )
                return None

            try:
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

    def _cleanup_stream(self) -> None:
        """Clean up the audio stream if it exists."""
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
                logger.info("Audio stream stopped and closed.")
            except Exception as e:
                logger.error(f"Error stopping or closing stream: {str(e)}")
            finally:
                self.stream = None

    def _record_impl(self, language: str | None = None) -> None:
        """
        Core recording logic executed in a separate thread.
        Records audio from the specified input device until recording is stopped.

        Args:
            language: Optional language hint (currently unused in recorder)
        """
        input_device, _ = get_default_devices()
        if input_device is None:
            logger.error("No input device found. Cannot start recording.")
            # Notify callback of failure
            self.callback(audio_data=None, error="No input device")
            return

        # Reset stream error tracking for this recording session
        with self.lock:
            self.stream_error_count = 0
            self.persistent_stream_error = False
            self.accumulated_audio_data = []  # Ensure it's clear

        samplerate = 16000  # Standard samplerate for transcription

        try:
            with self._recording_state(), self._stream_context(input_device) as stream:
                if stream is None or self.persistent_stream_error:
                    logger.error(
                        "Failed to initialize or stream encountered persistent error."
                    )
                    self.callback(
                        audio_data=None,
                        error="Stream initialization failed or persistent error",
                    )
                    return

                logger.info(
                    f"Recording started. Samplerate: {samplerate}, Device: {input_device}"
                )

                # Loop to keep the recording active while self.recording is True
                while True:
                    with self.lock:
                        if not self.recording or self.persistent_stream_error:
                            break
                    sd.sleep(
                        100
                    )  # Sleep briefly to avoid busy-waiting, stream callback handles data

                logger.info("Recording loop finished.")

            # Process and save the recorded audio
            with self.lock:
                if self.persistent_stream_error:
                    logger.error(
                        "Persistent stream error occurred. No audio will be processed."
                    )
                    self.callback(
                        audio_data=None, error="Persistent audio stream error"
                    )
                    return

                if not self.accumulated_audio_data:
                    logger.warning("No audio data recorded.")
                    self.callback(audio_data=None, error="No audio data recorded")
                    return

                logger.info(
                    f"Processing {len(self.accumulated_audio_data)} accumulated audio chunks."
                )
                # Concatenate all recorded numpy arrays
                full_audio_np = np.concatenate(self.accumulated_audio_data)
                self.accumulated_audio_data = []  # Clear after concatenating

                # Create a BytesIO buffer to hold the WAV data
                self.audio_buffer = io.BytesIO()
                try:
                    # Write the numpy array to the BytesIO buffer as a WAV file
                    sf.write(
                        self.audio_buffer,
                        full_audio_np,
                        samplerate,
                        format="WAV",
                        subtype="PCM_16",
                    )
                    self.audio_buffer.seek(
                        0
                    )  # Reset buffer position to the beginning for reading
                    logger.info(
                        f"Audio data written to in-memory WAV buffer (size: {self.audio_buffer.getbuffer().nbytes} bytes)."
                    )
                    # Pass the BytesIO object to the callback
                    self.callback(audio_data=self.audio_buffer, language=language)
                except Exception as e:
                    logger.error(f"Error writing WAV data to memory buffer: {str(e)}")
                    self.callback(
                        audio_data=None, error=f"Failed to create WAV in memory: {e}"
                    )
                    if self.audio_buffer:
                        self.audio_buffer.close()
                    self.audio_buffer = None

        except Exception as e:
            logger.error(f"An error occurred during recording: {str(e)}")
            self.callback(audio_data=None, error=f"Recording error: {e}")
        finally:
            logger.info("Recording implementation finished.")
            # Ensure accumulated data is cleared if an exception occurred before processing
            with self.lock:
                self.accumulated_audio_data = []
            # Cleanup of the stream is handled by _stream_context
            # Cleanup of the audio_buffer (if created) happens when it's used or in _cleanup_previous_session

import io
import logging
import queue
import threading
from collections import deque
from contextlib import contextmanager

import numpy as np
import sounddevice as sd
import soundfile as sf

try:
    import webrtcvad
except ImportError:  # Fallback for unsupported platforms
    webrtcvad = None
    logging.getLogger(__name__).warning(
        "webrtcvad is not available on this platform – Voice Activity Detection will be disabled."
    )

from ..core import constants as const
from ..core.utils import get_default_devices

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Pre-allocated buffer for audio data with zero-copy operations."""

    def __init__(self, size: int, dtype=np.float32):
        self.buffer = np.zeros(size, dtype=dtype)
        self.write_pos = 0
        self.data_size = 0
        self.max_size = size

    def append(self, data: np.ndarray) -> bool:
        """Append data to buffer. Returns True if successful, False if buffer full."""
        if self.write_pos + len(data) > self.max_size:
            return False

        self.buffer[self.write_pos : self.write_pos + len(data)] = data.flatten()
        self.write_pos += len(data)
        self.data_size += len(data)
        return True

    def get_data(self) -> np.ndarray:
        """Get the accumulated data as a view (zero-copy)."""
        return self.buffer[: self.data_size]

    def reset(self):
        """Reset buffer for reuse."""
        self.write_pos = 0
        self.data_size = 0


class BufferPool:
    """Pool of pre-allocated buffers for efficient memory management."""

    def __init__(self, buffer_size: int, pool_size: int = 4):
        self.available_buffers = deque()
        self.buffer_size = buffer_size

        # Pre-allocate buffers
        for _ in range(pool_size):
            self.available_buffers.append(AudioBuffer(buffer_size))

    def get_buffer(self) -> AudioBuffer:
        """Get a buffer from the pool or create new one if empty."""
        if self.available_buffers:
            buffer = self.available_buffers.popleft()
            buffer.reset()
            return buffer
        else:
            # Pool exhausted, create new buffer
            return AudioBuffer(self.buffer_size)

    def return_buffer(self, buffer: AudioBuffer):
        """Return a buffer to the pool for reuse."""
        buffer.reset()
        self.available_buffers.append(buffer)


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
            # Stop VAD worker thread first
            self._stop_vad_worker()

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
                self._initialize_recording_buffer()
                self.recording = True
            yield
        finally:
            with self.lock:
                self.recording = False

    def __init__(self, callback, vad_enabled=True, vad_sensitivity=1):
        """
        Initialize the recorder with a callback function and VAD settings.

        Args:
            callback: Function to call with recorded audio data
            vad_enabled: Boolean to enable/disable Voice Activity Detection
            vad_sensitivity: Integer for VAD aggressiveness (0-3)
        """
        self.callback = callback
        self.recording = False
        self.stream = None
        self.lock = threading.Lock()  # Thread-safe state management
        self.audio_buffer = None

        # Calculate buffer size: 30 seconds at 16kHz sample rate
        max_recording_samples = const.AUDIO_SAMPLE_RATE_HZ * 30
        self.buffer_pool = BufferPool(max_recording_samples, pool_size=4)
        self.current_audio_buffer = None

        # Legacy list for backward compatibility - will be phased out
        self.accumulated_audio_data = []

        # Lock-free queue for audio data from callback to worker thread
        self.audio_queue = queue.Queue()
        self.vad_worker_thread = None
        self.vad_worker_stop_event = threading.Event()

        # Persistent worker thread for recording tasks
        self.worker_thread = None
        self.worker_stop_event = threading.Event()
        self.recording_tasks = queue.Queue()
        self._start_worker_thread()

        # Stream error tracking
        self.stream_error_count = 0
        self.persistent_stream_error = False
        self.max_stream_errors = const.MAX_STREAM_ERRORS

        # VAD settings
        self.vad_enabled = vad_enabled
        self.vad_sensitivity = vad_sensitivity
        if self.vad_enabled:
            self.vad = webrtcvad.Vad()
            try:
                self.vad.set_mode(self.vad_sensitivity)
            except Exception as e:
                logger.warning(
                    f"Failed to set VAD mode: {e}. Using default sensitivity."
                )
                self.vad.set_mode(
                    1
                )  # Default to moderate if provided sensitivity is invalid

            self.vad_sample_rate = (
                const.AUDIO_SAMPLE_RATE_HZ
            )  # VAD expects 8k, 16k, 32k, or 48k
            self.vad_frame_duration_ms = (
                const.VAD_FRAME_DURATION_MS
            )  # VAD supports 10, 20, or 30 ms frames
            # Calculate frame size in bytes (16-bit samples, 1 channel)
            self.vad_frame_size = int(
                self.vad_sample_rate * (self.vad_frame_duration_ms / 1000.0) * 2
            )
            self.vad_buffer = bytearray()
            self.speech_frames = []  # To store frames identified as speech
            self.silence_frames_after_speech = 0
            self.min_silence_frames_to_stop = const.VAD_MIN_SILENCE_FRAMES_TO_STOP
            self.is_currently_speech = False

            # Pre-allocate conversion buffer to avoid temporary arrays
            # Maximum expected audio chunk size (e.g., 1024 samples per callback)
            self.conversion_buffer = np.zeros(1024, dtype=np.int16)

    def start(self, event) -> None:
        """Start recording using persistent worker thread."""
        logger.info("Starting recording...")
        language = event.kwargs.get("language") if hasattr(event, "kwargs") else None

        # Send recording task to worker thread instead of creating new thread
        self.recording_tasks.put(("start", language))

    def _start_worker_thread(self) -> None:
        """Start the persistent worker thread for recording tasks."""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_stop_event.clear()
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logger.info("Worker thread started")

    def _worker_loop(self) -> None:
        """Main loop for the persistent worker thread."""
        logger.info("Worker thread loop started")
        while not self.worker_stop_event.is_set():
            try:
                # Wait for recording tasks with timeout
                task = self.recording_tasks.get(timeout=1.0)
                if task[0] == "start":
                    language = task[1]
                    self._record_impl(language)
                elif task[0] == "stop":
                    break
                self.recording_tasks.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in worker thread: {e}")
        logger.info("Worker thread loop ended")

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
        # Stop VAD worker thread
        self._stop_vad_worker()
        # Stream cleanup is handled by the context manager

    def cleanup(self) -> None:
        """Clean up resources including worker thread."""
        logger.info("Cleaning up recorder resources...")
        # Stop worker thread
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_stop_event.set()
            self.recording_tasks.put(("stop", None))
            self.worker_thread.join(timeout=2.0)
            if self.worker_thread.is_alive():
                logger.warning("Worker thread did not stop gracefully")

        # Stop VAD worker thread
        self._stop_vad_worker()

        # Clean up any remaining session
        with self.lock:
            self._cleanup_previous_session()

    def _initialize_recording_buffer(self) -> None:
        """Initialize the recording buffer from the pool."""
        if self.current_audio_buffer is None:
            self.current_audio_buffer = self.buffer_pool.get_buffer()

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

        # Return current buffer to pool
        if self.current_audio_buffer is not None:
            self.buffer_pool.return_buffer(self.current_audio_buffer)
            self.current_audio_buffer = None

        # Reset VAD state if enabled
        if self.vad_enabled:
            self.vad_buffer = bytearray()
            self.speech_frames = []
            self.is_currently_speech = False
            self.silence_frames_after_speech = 0

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
                        if indata is not None and indata.size > 0:
                            if not hasattr(callback, "first_data_logged"):
                                logger.info(
                                    f"First audio data received: shape={indata.shape}, dtype={indata.dtype}, max={np.max(np.abs(indata))}"
                                )
                                callback.first_data_logged = True

                            # Send audio data to worker thread via queue (non-blocking)
                            if self.vad_enabled:
                                # Use pre-allocated buffer for conversion to avoid temporary arrays
                                chunk_size = min(
                                    len(indata), len(self.conversion_buffer)
                                )
                                if chunk_size > 0:
                                    # Convert to int16 using pre-allocated buffer
                                    flat_data = indata.flatten()[:chunk_size]
                                    # Safely convert float32 to int16 with proper scaling
                                    scaled_data = flat_data * 32767
                                    self.conversion_buffer[:chunk_size] = (
                                        scaled_data.astype(np.int16)
                                    )
                                    try:
                                        self.audio_queue.put_nowait(
                                            self.conversion_buffer[
                                                :chunk_size
                                            ].tobytes()
                                        )
                                    except queue.Full:
                                        logger.warning(
                                            "Audio queue full, dropping audio data"
                                        )
                            else:
                                # For non-VAD, use optimized buffer management
                                if self.current_audio_buffer is not None:
                                    # Try to append to current buffer
                                    if not self.current_audio_buffer.append(indata):
                                        # Buffer full, fallback to list (this should be rare)
                                        logger.warning(
                                            "Audio buffer full, falling back to list"
                                        )
                                        self.accumulated_audio_data.append(
                                            indata.copy()
                                        )
                                else:
                                    # Fallback to list if no buffer available
                                    self.accumulated_audio_data.append(indata.copy())
                        else:
                            logger.warning("Received empty audio data in callback")
                    except Exception as e:
                        logger.error(
                            f"Error processing audio data in callback: {str(e)}"
                        )

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

    def _start_vad_worker(self) -> None:
        """Start the VAD worker thread."""
        if self.vad_enabled and self.vad_worker_thread is None:
            self.vad_worker_stop_event.clear()
            self.vad_worker_thread = threading.Thread(
                target=self._vad_worker_thread, daemon=True
            )
            self.vad_worker_thread.start()
            logger.info("VAD worker thread started")

    def _stop_vad_worker(self) -> None:
        """Stop the VAD worker thread."""
        if self.vad_worker_thread is not None:
            self.vad_worker_stop_event.set()
            self.vad_worker_thread.join(timeout=1.0)
            self.vad_worker_thread = None
            logger.info("VAD worker thread stopped")

    def _vad_worker_thread(self) -> None:
        """VAD worker thread that processes audio data from the queue."""
        logger.info("VAD worker thread started processing")

        while not self.vad_worker_stop_event.is_set():
            try:
                # Get audio data from queue with timeout
                audio_bytes = self.audio_queue.get(timeout=0.1)

                # Process VAD on this audio data
                self.vad_buffer.extend(audio_bytes)

                while len(self.vad_buffer) >= self.vad_frame_size:
                    frame_bytes = self.vad_buffer[: self.vad_frame_size]
                    del self.vad_buffer[: self.vad_frame_size]

                    try:
                        is_speech = self.vad.is_speech(
                            frame_bytes, self.vad_sample_rate
                        )
                        if is_speech:
                            self.speech_frames.append(frame_bytes)
                            self.is_currently_speech = True
                            self.silence_frames_after_speech = 0
                        elif self.is_currently_speech:
                            # If speech was ongoing, append silence frame too for a short duration
                            self.speech_frames.append(frame_bytes)
                            self.silence_frames_after_speech += 1
                            if (
                                self.silence_frames_after_speech
                                >= self.min_silence_frames_to_stop
                            ):
                                logger.info(
                                    f"VAD: Detected end of speech after {self.silence_frames_after_speech} silent frames."
                                )
                                self.is_currently_speech = False
                        # else: VAD is not speech and was not speech (initial silence) - do nothing
                    except Exception as e:
                        logger.error(f"VAD processing error: {e}")

                self.audio_queue.task_done()

            except queue.Empty:
                # Timeout reached, continue loop to check stop event
                continue
            except Exception as e:
                logger.error(f"Error in VAD worker thread: {e}")

        logger.info("VAD worker thread finished")

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
            self.accumulated_audio_data = []  # Ensure it's clear for non-VAD case
            if self.vad_enabled:  # Ensure VAD states are pristine for this recording
                self.vad_buffer = bytearray()
                self.speech_frames = []
                self.is_currently_speech = False
                self.silence_frames_after_speech = 0
                # Clear the audio queue
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        break
                # Start VAD worker thread only after stream is ready
                pass  # Will start in stream context

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

                # Start VAD worker thread now that stream is ready
                if self.vad_enabled:
                    self._start_vad_worker()

                # Loop to keep the recording active while self.recording is True
                while True:
                    with self.lock:
                        if not self.recording or self.persistent_stream_error:
                            break
                    sd.sleep(
                        const.RECORDER_LOOP_SLEEP_MS
                    )  # Sleep briefly to avoid busy-waiting, stream callback handles data

                logger.info("Recording loop finished.")

            # Process and save the recorded audio
            self._process_recorded_data(language)

        except Exception as e:
            logger.error(f"An error occurred during recording: {str(e)}")
            self.callback(audio_data=None, error=f"Recording error: {e}")
        finally:
            logger.info("Recording implementation finished.")
            # Ensure accumulated data and VAD frames are cleared if an exception occurred before processing
            with self.lock:
                self.accumulated_audio_data = []
                if self.vad_enabled:
                    self.speech_frames = []
                    self.vad_buffer = bytearray()  # Also clear vad_buffer
            # Cleanup of the stream is handled by _stream_context
            # Cleanup of the audio_buffer (if created) happens when it's used or in _cleanup_previous_session
            # VAD worker cleanup is handled by _stream_context

    def _process_recorded_data(self, language: str | None) -> None:
        """Processes audio data after the recording loop finishes."""
        with self.lock:
            if self.persistent_stream_error:
                logger.error(
                    "Persistent stream error occurred. No audio will be processed."
                )
                self.callback(audio_data=None, error="Persistent audio stream error")
                return

            full_audio_np = None
            if self.vad_enabled:
                full_audio_np = self._process_vad_frames()
            else:
                full_audio_np = self._process_non_vad_chunks()

            if full_audio_np is None or full_audio_np.size == 0:
                logger.warning(
                    "Resulting audio data is empty before writing to buffer."
                )
                self.callback(
                    audio_data=None, error="Empty audio data after processing"
                )
                return

            audio_buffer = self._package_audio_as_wav(full_audio_np)
            if audio_buffer:
                self.callback(audio_data=audio_buffer, language=language)
            else:
                self.callback(audio_data=None, error="Failed to create WAV in memory")

    def _process_vad_frames(self) -> np.ndarray | None:
        """Process VAD speech frames into audio numpy array."""
        if not self.speech_frames:
            logger.warning("VAD enabled, but no speech frames recorded.")
            self.callback(audio_data=None, error="No speech detected")
            return None

        logger.info(f"Processing {len(self.speech_frames)} VAD speech frames.")
        # Concatenate all byte frames from VAD
        all_speech_bytes = b"".join(self.speech_frames)
        self.speech_frames = []  # Clear after processing

        if not all_speech_bytes:
            logger.warning("VAD speech frames were empty after join.")
            self.callback(audio_data=None, error="Empty speech data after VAD")
            return None

        # Convert bytes to int16 numpy array
        audio_int16_np = np.frombuffer(all_speech_bytes, dtype=np.int16)

        # Convert int16 to float32 numpy array
        full_audio_np = audio_int16_np.astype(np.float32) / 32767.0
        logger.info(
            f"VAD processed audio: {full_audio_np.shape}, {full_audio_np.dtype}"
        )
        return full_audio_np

    def _process_non_vad_chunks(self) -> np.ndarray | None:
        """Process accumulated audio chunks into audio numpy array."""
        # Priority: use optimized buffer if available
        if (
            self.current_audio_buffer is not None
            and self.current_audio_buffer.data_size > 0
        ):
            logger.info(
                f"Processing optimized audio buffer with {self.current_audio_buffer.data_size} samples."
            )
            # Get data as a view (zero-copy)
            full_audio_np = (
                self.current_audio_buffer.get_data().copy()
            )  # Copy for safety since buffer will be reused
            return full_audio_np

        # Fallback: use legacy accumulated data
        if not self.accumulated_audio_data:
            logger.warning("No audio data recorded (VAD disabled).")
            self.callback(audio_data=None, error="No audio data recorded")
            return None

        logger.info(
            f"Processing {len(self.accumulated_audio_data)} accumulated audio chunks (VAD disabled)."
        )
        # Concatenate all recorded numpy arrays
        full_audio_np = np.concatenate(self.accumulated_audio_data)
        self.accumulated_audio_data = []  # Clear after concatenating
        return full_audio_np

    def _package_audio_as_wav(self, audio_data: np.ndarray) -> io.BytesIO | None:
        """Package audio numpy array as WAV format in BytesIO buffer."""
        self.audio_buffer = io.BytesIO()
        try:
            # Write the numpy array to the BytesIO buffer as a WAV file
            sf.write(
                self.audio_buffer,
                audio_data,
                const.AUDIO_SAMPLE_RATE_HZ,
                format="WAV",
                subtype="PCM_16",
            )
            self.audio_buffer.seek(
                0
            )  # Reset buffer position to the beginning for reading
            logger.info(
                f"Audio data written to in-memory WAV buffer (size: {self.audio_buffer.getbuffer().nbytes} bytes)."
            )
            return self.audio_buffer
        except Exception as e:
            logger.error(f"Error writing WAV data to memory buffer: {str(e)}")
            if self.audio_buffer:
                self.audio_buffer.close()
            self.audio_buffer = None
            return None

import logging
import os
import tempfile
import threading
from contextlib import contextmanager

import numpy as np
import sounddevice as sd
import soundfile as sf

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
        self.audio_file_writer = None
        self.temp_filename = None

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
            if self.audio_file_writer is not None:
                logger.info("Audio file writer exists when stopping recording")
            else:
                logger.warning("Audio file writer is None when stopping recording")
            if self.temp_filename:
                logger.info(f"Temporary file exists: {self.temp_filename}")
            else:
                logger.warning("No temporary filename when stopping recording")
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
        
        # Close any existing audio file writer
        if self.audio_file_writer is not None:
            try:
                self.audio_file_writer.close()
                logger.info(f"Closed previous audio file writer")
            except Exception as e:
                logger.error(f"Error closing previous audio file writer: {str(e)}")
            finally:
                self.audio_file_writer = None
                
        # Delete any existing temporary file
        if self.temp_filename is not None and os.path.exists(self.temp_filename):
            try:
                os.unlink(self.temp_filename)
                logger.info(f"Deleted previous temporary file: {self.temp_filename}")
            except Exception as e:
                logger.error(f"Error deleting temporary file: {str(e)}")
            finally:
                self.temp_filename = None

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
            
            # Only write data if we're recording and the file writer exists
            with self.lock:  # Use lock to ensure thread safety when checking audio_file_writer
                if self.recording and self.audio_file_writer is not None:
                    try:
                        # Check if we have valid audio data
                        if indata is not None and indata.size > 0:
                            # Log the first callback with data details
                            if not hasattr(callback, 'first_data_logged'):
                                logger.info(f"First audio data received: shape={indata.shape}, dtype={indata.dtype}, max={np.max(np.abs(indata))}")
                                callback.first_data_logged = True
                            
                            self.audio_file_writer.write(indata)
                        else:
                            logger.warning("Received empty audio data in callback")
                    except Exception as e:
                        logger.error(f"Error writing audio data to file: {str(e)}")
                elif self.recording and self.audio_file_writer is None:
                    logger.warning("Audio file writer is None but recording is True - this should not happen")

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
                self.callback(audio_filename=None)
                return

            # Use recording state context manager
            with self._recording_state():
                # Create a temporary file for audio data BEFORE starting the stream
                try:
                    # Choose file format based on the default transcriber (WAV is more compatible)
                    suffix = '.wav'
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    self.temp_filename = temp_file.name
                    temp_file.close()  # Close the file so soundfile can open it
                    
                    # Open the file for writing with soundfile
                    self.audio_file_writer = sf.SoundFile(
                        self.temp_filename,
                        mode='w',
                        samplerate=16000,
                        channels=1,
                        format='WAV',
                        subtype='PCM_16'
                    )
                    logger.info(f"Created temporary audio file: {self.temp_filename}")
                except Exception as e:
                    logger.error(f"Failed to create temporary audio file: {str(e)}")
                    if self.temp_filename and os.path.exists(self.temp_filename):
                        try:
                            os.unlink(self.temp_filename)
                        except Exception as ex:
                            logger.error(f"Error deleting temporary file: {str(ex)}")
                    self.temp_filename = None
                    self.callback(audio_filename=None)
                    return

                # Now start the stream after the file is ready
                with self._stream_context(input_device) as stream:
                    if stream is None:
                        # Clean up the file if stream setup fails
                        if self.audio_file_writer:
                            self.audio_file_writer.close()
                            self.audio_file_writer = None
                        if self.temp_filename and os.path.exists(self.temp_filename):
                            try:
                                os.unlink(self.temp_filename)
                                self.temp_filename = None
                            except Exception as e:
                                logger.error(f"Error deleting temporary file: {str(e)}")
                        self.callback(audio_filename=None)
                        return

                    # Main recording loop
                    while self.recording:
                        sd.sleep(100)  # Sleep to prevent busy-waiting

            # After the stream context exits (stream is stopped and closed)
            with self.lock:
                # Close the audio file writer
                if self.audio_file_writer:
                    try:
                        self.audio_file_writer.close()
                        logger.info(f"Closed temporary audio file: {self.temp_filename}")
                    except Exception as e:
                        logger.error(f"Error closing audio file: {str(e)}")
                    finally:
                        self.audio_file_writer = None
                
                # Check if recording was successful (file exists and has non-zero size)
                if self.temp_filename and os.path.exists(self.temp_filename):
                    file_size = os.path.getsize(self.temp_filename)
                    logger.info(f"Temporary file size: {file_size} bytes")
                    
                    if file_size > 44:  # WAV header is 44 bytes, so we need more than that for actual audio content
                        logger.info(f"Recording successful, saved to: {self.temp_filename}")
                        # Pass the filename to the callback instead of audio data
                        temp_filename_to_pass = self.temp_filename
                        self.temp_filename = None  # Transfer ownership to the callback
                        self.callback(audio_filename=temp_filename_to_pass, language=language)
                    else:
                        logger.warning(f"No valid audio data in file (size: {file_size} bytes)")
                        # Clean up the file if it exists but is invalid/empty
                        try:
                            os.unlink(self.temp_filename)
                            logger.info(f"Deleted empty audio file: {self.temp_filename}")
                        except Exception as e:
                            logger.error(f"Error deleting invalid temporary file: {str(e)}")
                        self.temp_filename = None
                        self.callback(audio_filename=None)
                else:
                    logger.warning("No valid audio file created during recording")
                    self.temp_filename = None
                    self.callback(audio_filename=None)

        except sd.PortAudioError as e:
            logger.error(f"Audio device error during recording: {str(e)}")
            # Clean up resources
            with self.lock:
                if self.audio_file_writer:
                    try:
                        self.audio_file_writer.close()
                    except:
                        pass
                    self.audio_file_writer = None
                if self.temp_filename and os.path.exists(self.temp_filename):
                    try:
                        os.unlink(self.temp_filename)
                    except:
                        pass
                    self.temp_filename = None
            self.callback(audio_filename=None)
        except Exception as e:
            logger.error(f"Unexpected error during recording: {str(e)}")
            # Clean up resources
            with self.lock:
                if self.audio_file_writer:
                    try:
                        self.audio_file_writer.close()
                    except:
                        pass
                    self.audio_file_writer = None
                if self.temp_filename and os.path.exists(self.temp_filename):
                    try:
                        os.unlink(self.temp_filename)
                    except:
                        pass
                    self.temp_filename = None
            self.callback(audio_filename=None)

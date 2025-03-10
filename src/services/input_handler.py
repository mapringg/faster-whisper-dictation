import time
import threading
import logging
from pynput import keyboard

logger = logging.getLogger(__name__)

class KeyboardReplayer:
    """Handles typing out transcribed text with rate limiting and error handling."""
    
    def __init__(self, callback):
        """
        Initialize the replayer with a callback function.
        
        Args:
            callback: Function to call after typing is complete
        """
        self.callback = callback
        self.kb = keyboard.Controller()
        self.typing_delay = 0.0025  # Delay between keystrokes in seconds
        self.max_retries = 3
        self.lock = threading.Lock()  # Thread-safe state management

    def _validate_segments(self, segments: list) -> bool:
        """
        Validate the transcription segments.
        
        Args:
            segments: List of transcription segments
            
        Returns:
            bool: True if segments are valid, False otherwise
        """
        if not isinstance(segments, list):
            logger.error(f"Invalid segments type: {type(segments)}")
            return False
            
        for segment in segments:
            if not hasattr(segment, 'text') or not isinstance(segment.text, str):
                logger.error("Segment missing text attribute or text is not a string")
                return False
                
        return True

    def _type_with_retry(self, char: str) -> bool:
        """
        Type a single character with retry mechanism.
        
        Args:
            char: Character to type
            
        Returns:
            bool: True if successful, False after max retries
        """
        for attempt in range(self.max_retries):
            try:
                self.kb.type(char)
                return True
            except Exception as e:
                logger.warning(f"Error typing character '{char}' (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
        
        logger.error(f"Failed to type character '{char}' after {self.max_retries} attempts")
        return False

    def replay(self, event) -> None:
        """
        Handle the text replay process with error handling and rate limiting.
        
        Args:
            event: State machine event containing transcription segments
        """
        logger.info('Starting text replay...')
        segments = event.kwargs.get('segments', [])
        text_buffer = []
        
        # Validate input segments
        if not self._validate_segments(segments):
            logger.error("Invalid transcription segments")
            self.callback()
            return
            
        try:
            with self.lock:
                # Process each segment
                for segment in segments:
                    is_first = True
                    
                    # Process each character in segment
                    for char in segment.text:
                        # Skip leading space in first segment
                        if is_first and char == " ":
                            is_first = False
                            continue
                            
                        # Type character with retry mechanism
                        if self._type_with_retry(char):
                            text_buffer.append(char)
                            time.sleep(self.typing_delay)
                        else:
                            logger.warning(f"Skipping character '{char}' due to repeated errors")
                            
                # Log final typed text
                if text_buffer:
                    logger.info(f"Successfully typed text: {''.join(text_buffer)}")
                else:
                    logger.warning("No text was typed")
                    
        except Exception as e:
            logger.error(f"Unexpected error during text replay: {str(e)}")
        finally:
            self.callback()


class KeyListener:
    """Handles single key press events with error handling and cleanup."""
    
    def __init__(self, callback, key: str):
        """
        Initialize the key listener with callback and key binding.
        
        Args:
            callback: Function to call when key is pressed
            key: Key combination to listen for (e.g. '<alt_l>')
        """
        self.callback = callback
        self.key = key
        self.listener = None
        self.lock = threading.Lock()  # Thread-safe state management

    def _validate_key(self) -> bool:
        """
        Validate the key combination.
        
        Returns:
            bool: True if key is valid, False otherwise
        """
        try:
            keyboard.HotKey.parse(self.key)
            return True
        except ValueError as e:
            logger.error(f"Invalid key combination '{self.key}': {str(e)}")
            return False

    def run(self) -> None:
        """Start listening for key presses with error handling."""
        if not self._validate_key():
            logger.error("Cannot start key listener with invalid key")
            return
            
        try:
            with self.lock:
                self.listener = keyboard.GlobalHotKeys({self.key: self._safe_callback})
                self.listener.start()
                self.listener.join()
        except Exception as e:
            logger.error(f"Error in key listener: {str(e)}")
        finally:
            self._cleanup()

    def _safe_callback(self) -> None:
        """Wrapper for callback with error handling."""
        try:
            self.callback()
        except Exception as e:
            logger.error(f"Error in key callback: {str(e)}")

    def _cleanup(self) -> None:
        """Clean up listener resources."""
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception as e:
                logger.error(f"Error stopping key listener: {str(e)}")
            finally:
                self.listener = None


class DoubleKeyListener:
    """Handles double-click key events with rate limiting and error handling."""
    
    def __init__(self, activate_callback, deactivate_callback, key=keyboard.Key.cmd_r):
        """
        Initialize the double key listener with callbacks and key binding.
        
        Args:
            activate_callback: Function to call on double-click
            deactivate_callback: Function to call on single-click
            key: Key to listen for (default: right command key)
        """
        self.activate_callback = activate_callback
        self.deactivate_callback = deactivate_callback
        self.key = key
        self.last_press_time = 0
        self.double_click_threshold = 0.5  # Seconds between clicks
        self.min_press_duration = 0.1  # Minimum press duration in seconds
        self.listener = None
        self.lock = threading.Lock()  # Thread-safe state management

    def _safe_activate(self) -> None:
        """Wrapper for activate callback with error handling."""
        try:
            self.activate_callback()
        except Exception as e:
            logger.error(f"Error in activate callback: {str(e)}")

    def _safe_deactivate(self) -> None:
        """Wrapper for deactivate callback with error handling."""
        try:
            self.deactivate_callback()
        except Exception as e:
            logger.error(f"Error in deactivate callback: {str(e)}")

    def on_press(self, key) -> bool | None:
        """
        Handle key press events with rate limiting.
        
        Args:
            key: The key that was pressed
            
        Returns:
            bool | None: Return value depends on pynput requirements
        """
        if key != self.key:
            return None
            
        current_time = time.time()
        time_since_last = current_time - self.last_press_time
        
        # Rate limiting
        if time_since_last < self.min_press_duration:
            return None
            
        self.last_press_time = current_time
        
        # Determine if double click
        is_dbl_click = time_since_last < self.double_click_threshold
        
        try:
            if is_dbl_click:
                self._safe_activate()
            else:
                self._safe_deactivate()
        except Exception as e:
            logger.error(f"Error handling key press: {str(e)}")
            
        return None

    def on_release(self, key) -> None:
        """Handle key release events."""
        pass

    def run(self) -> None:
        """Start listening for key events with error handling."""
        try:
            with self.lock:
                self.listener = keyboard.Listener(
                    on_press=self.on_press,
                    on_release=self.on_release
                )
                self.listener.start()
                self.listener.join()
        except Exception as e:
            logger.error(f"Error in double key listener: {str(e)}")
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """Clean up listener resources."""
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception as e:
                logger.error(f"Error stopping double key listener: {str(e)}")
            finally:
                self.listener = None

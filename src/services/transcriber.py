import json
import logging
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from ..core import constants as const
from ..core.utils import load_env_from_file

logger = logging.getLogger(__name__)


# Define Segment class at module level
class Segment:
    """Represents a segment of transcribed text."""

    def __init__(self, text: str):
        """
        Initialize a segment with text.

        Args:
            text: The transcribed text
        """
        self.text = text
        logger.debug(f"Segment created with text: '{self.text}'")


class BaseTranscriber(ABC):
    """Base class for audio transcription services."""

    # Common configuration from constants
    MAX_RETRIES = const.API_MAX_RETRIES
    INITIAL_RETRY_DELAY = const.API_INITIAL_RETRY_DELAY_SECS  # seconds
    REQUEST_TIMEOUT = const.API_REQUEST_TIMEOUT_SECS  # seconds

    def __init__(self, callback: Callable, api_key_env_var: str, model: str):
        """
        Initialize the base transcriber.

        Args:
            callback: Function to call with transcription results
            api_key_env_var: Name of environment variable for API key
            model: Name of the model to use
        """
        self.callback = callback
        self.model = model
        self.api_key_env_var = api_key_env_var

        # Try to get API key from environment
        self.api_key = os.environ.get(self.api_key_env_var)

        # If not found, try to load from ~/.env file
        if not self.api_key:
            env_file = os.path.join(str(Path.home()), ".env")
            if load_env_from_file(env_file):
                self.api_key = os.environ.get(self.api_key_env_var)

        if not self.api_key:
            raise ValueError(
                f"{self.api_key_env_var} environment variable is not set. "
                "Please set it in your environment or in ~/.env file."
            )

    def get_prompt(self, language: str | None) -> str:
        """
        Get appropriate prompt based on language.

        Args:
            language: Language code

        Returns:
            str: Prompt text
        """
        if language == "th":
            return "ถอดข้อความเสียงนี้ซึ่งอาจมีการสนทนาทั่วไปเกี่ยวกับชีวิตประจำวัน บทสนทนา หรือเนื้อหาทั่วไป ใช้คำศัพท์ที่เหมาะสม"
        else:  # Default to English software development focus
            return "Transcribe this audio, which may contain technical discussions related to software development, programming languages, APIs, and system architecture. Use precise terminology where appropriate."

    @abstractmethod
    def make_api_request(
        self, temp_filename: str, language: str | None = None
    ) -> tuple[bool, dict | str]:
        """
        Make API request with retry mechanism.

        Args:
            temp_filename: Path to temporary audio file
            language: Optional language code for transcription

        Returns:
            tuple: (success: bool, result_or_error: dict|str)
                   On success: (True, response.json())
                   On failure: (False, error_message)
        """
        pass

    def transcribe(self, event: Any) -> None:
        """
        Handle the transcription process from audio input to text output.

        Args:
            event: State machine event containing audio filename and language info

        Returns:
            None: Results are passed to the callback function
        """
        logger.info(f"Starting transcription with {self.__class__.__name__}...")
        audio_filename = event.kwargs.get("audio_filename", None)
        language = event.kwargs.get("language")

        # Validate audio filename
        if (
            audio_filename is None
            or not os.path.exists(audio_filename)
            or os.path.getsize(audio_filename) == 0
        ):
            logger.warning("Invalid or empty audio file provided")
            self.callback(segments=[])
            return

        try:
            # Make API request and handle response
            success, result_or_error = self.make_api_request(audio_filename, language)

            if success:
                text = result_or_error.get("text", "")
                if not text:
                    logger.warning("Received empty transcription")

                logger.info("Transcription successful")

                segments = [Segment(text)]
                self.callback(segments=segments)
            else:
                logger.error("Failed to get transcription after retries")
                self.callback(
                    segments=[], error=result_or_error if not success else None
                )

        except Exception as e:
            logger.error(f"Error during transcription: {str(e)}")
            self.callback(segments=[])

        finally:
            # Clean up the temporary file
            try:
                if audio_filename and os.path.exists(audio_filename):
                    os.unlink(audio_filename)
                    logger.info(f"Temporary file {audio_filename} deleted")
            except Exception as e:
                logger.error(f"Error deleting temporary file: {str(e)}")

            # Final garbage collection
            import gc

            gc.collect()


class GroqTranscriber(BaseTranscriber):
    """Handles audio transcription using the Groq API."""

    # Groq-specific configuration
    API_ENDPOINT = const.GROQ_API_ENDPOINT

    def __init__(self, callback: Callable, model: str = "whisper-large-v3"):
        """
        Initialize the Groq transcriber.

        Args:
            callback: Function to call with transcription results
            model: Name of the Groq model to use (default: whisper-large-v3)
        """
        super().__init__(callback, "GROQ_API_KEY", model)

    def make_api_request(
        self, temp_filename: str, language: str | None = None
    ) -> tuple[bool, dict | str]:
        """
        Make API request to Groq with retry mechanism.

        Args:
            temp_filename: Path to temporary FLAC file
            language: Optional language code for transcription

        Returns:
            dict: JSON response from API if successful
            None: If all retries failed
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(self.MAX_RETRIES):
            try:
                with open(temp_filename, "rb") as audio_file:
                    # Get appropriate prompt
                    prompt = self.get_prompt(language)

                    data = {
                        "model": self.model,
                        "prompt": prompt,
                        "temperature": 0.0,
                    }

                    if language and isinstance(language, str):
                        data["language"] = language
                        logger.info(f"Using language: {language}")

                    # Stream the file directly without loading into memory
                    files = {"file": (os.path.basename(temp_filename), audio_file)}
                    response = requests.post(
                        self.API_ENDPOINT,
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=self.REQUEST_TIMEOUT,
                    )

                    # Handle successful response
                    if response.status_code == 200:
                        try:
                            result = response.json()
                            # Close the response to release resources
                            response.close()
                            return (True, result)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode JSON response: {str(e)}")
                            # Close the response to release resources
                            if response:
                                response.close()
                            continue

                    # Handle rate limiting
                    elif response.status_code == 429:
                        retry_after = int(
                            response.headers.get(
                                "Retry-After", self.INITIAL_RETRY_DELAY
                            )
                        )
                        logger.warning(
                            f"Rate limited. Waiting {retry_after} seconds..."
                        )
                        # Close the response to release resources
                        response.close()
                        time.sleep(retry_after)
                        continue

                    # Handle other API errors
                    else:
                        error_msg = (
                            f"API error: {response.status_code} - {response.text}"
                        )
                        logger.error(error_msg)

                        # Close the response to release resources
                        response.close()

                        # Handle specific error cases
                        if response.status_code == 401:
                            error_msg = (
                                "Invalid API key - please check your GROQ_API_KEY"
                            )
                            logger.error(error_msg)
                            return (False, error_msg)
                        elif response.status_code == 413:
                            error_msg = (
                                "Audio file too large - try recording a shorter segment"
                            )
                            logger.error(error_msg)
                            return (False, error_msg)

                        # Exponential backoff for retries
                        if attempt < self.MAX_RETRIES - 1:
                            wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                            logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)

            except requests.exceptions.RequestException as e:
                logger.error(f"Network error: {str(e)}")
                # Close the response to release resources if it exists
                if response:
                    try:
                        response.close()
                    except:  # noqa: E722
                        pass

                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

            # Force garbage collection after each attempt
            if attempt % 2 == 1:
                import gc

                gc.collect()

        return (False, "Max retries exceeded for server/network error")


class OpenAITranscriber(BaseTranscriber):
    """Handles audio transcription using the OpenAI API."""

    # OpenAI-specific configuration
    API_ENDPOINT = const.OPENAI_API_ENDPOINT

    def __init__(self, callback: Callable, model: str = "gpt-4o-transcribe"):
        """
        Initialize the OpenAI transcriber.

        Args:
            callback: Function to call with transcription results
            model: Name of the OpenAI model to use (default: gpt-4o-transcribe)
        """
        super().__init__(callback, "OPENAI_API_KEY", model)

    def make_api_request(
        self, temp_filename: str, language: str | None = None
    ) -> tuple[bool, dict | str]:
        """
        Make API request to OpenAI with retry mechanism.

        Args:
            temp_filename: Path to temporary WAV file
            language: Optional language code for transcription

        Returns:
            dict: JSON response from API if successful
            None: If all retries failed
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(self.MAX_RETRIES):
            try:
                with open(temp_filename, "rb") as audio_file:
                    # Get appropriate prompt
                    prompt = self.get_prompt(language)

                    data = {
                        "model": self.model,
                        "prompt": prompt,
                        "temperature": 0.0,
                    }

                    if language and isinstance(language, str):
                        data["language"] = language
                        logger.info(f"Using language: {language}")

                    # Stream the file directly without loading into memory
                    files = {"file": (os.path.basename(temp_filename), audio_file)}
                    response = requests.post(
                        self.API_ENDPOINT,
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=self.REQUEST_TIMEOUT,
                    )

                    # Handle successful response
                    if response.status_code == 200:
                        try:
                            result = response.json()
                            # Close the response to release resources
                            response.close()
                            return (True, result)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode JSON response: {str(e)}")
                            # Close the response to release resources
                            if response:
                                response.close()
                            continue

                    # Handle rate limiting
                    elif response.status_code == 429:
                        retry_after = int(
                            response.headers.get(
                                "Retry-After", self.INITIAL_RETRY_DELAY
                            )
                        )
                        logger.warning(
                            f"Rate limited. Waiting {retry_after} seconds..."
                        )
                        # Close the response to release resources
                        response.close()
                        time.sleep(retry_after)
                        continue

                    # Handle other API errors
                    else:
                        error_msg = (
                            f"API error: {response.status_code} - {response.text}"
                        )
                        logger.error(error_msg)

                        # Close the response to release resources
                        response.close()

                        # Handle specific error cases
                        if response.status_code == 401:
                            error_msg = (
                                "Invalid API key - please check your OPENAI_API_KEY"
                            )
                            logger.error(error_msg)
                            return (False, error_msg)
                        elif response.status_code == 413:
                            error_msg = "Audio file too large - must be less than 25MB"
                            logger.error(error_msg)
                            return (False, error_msg)

                        # Exponential backoff for retries
                        if attempt < self.MAX_RETRIES - 1:
                            wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                            logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)

            except requests.exceptions.RequestException as e:
                logger.error(f"Network error: {str(e)}")
                # Close the response to release resources if it exists
                if response:
                    try:
                        response.close()
                    except:  # noqa: E722
                        pass

                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

            # Force garbage collection after each attempt
            if attempt % 2 == 1:
                import gc

                gc.collect()

        return (False, "Max retries exceeded for server/network error")

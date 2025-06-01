import asyncio  # Added
import io
import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

import aiohttp  # Added

# import requests # Removed
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

        # Load environment variables with priority: Shell > Project .env > Home .env
        # 1. Load from home directory .env (lowest priority)
        home_env_file = os.path.join(str(Path.home()), ".env")
        load_env_from_file(home_env_file)  # Function handles non-existence gracefully

        # 2. Load from project directory .env (overrides home .env)
        project_env_file = ".env"  # Assumes CWD is project root
        load_env_from_file(
            project_env_file
        )  # Function handles non-existence gracefully

        # 3. Check environment (highest priority, includes loaded vars)
        self.api_key = os.environ.get(self.api_key_env_var)

        if not self.api_key:
            raise ValueError(
                f"{self.api_key_env_var} environment variable is not set. "
                "Please set it directly, in ./env, or in ~/.env."
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
            return "ถอดข้อความเสียงนี้ให้ถูกต้อง ใส่เครื่องหมายวรรคตอนให้เหมาะสม เช่น จุด และคอมม่า"
        else:  # Default to English software development focus
            return "Transcribe this audio accurately. It likely contains technical software development discussion, including terms like Typescript, JavaScript, React, Next.js, React Native, Expo, Supabase, PostgreSQL, MongoDB, Tailwind CSS, Shadcn, and system design. Prioritize correct spelling of technical terms, acronyms, and proper nouns. Maintain standard punctuation and capitalization."

    @abstractmethod
    async def make_api_request(  # Changed to async def
        self, audio_data: io.BytesIO, language: str | None = None
    ) -> tuple[bool, dict | str]:
        """
        Make API request with retry mechanism. (Now asynchronous)

        Args:
            audio_data: BytesIO object containing audio data
            language: Optional language code for transcription

        Returns:
            tuple: (success: bool, result_or_error: dict|str)
                   On success: (True, response.json())
                   On failure: (False, error_message)
        """
        pass

    async def transcribe(self, event: Any) -> None:  # Changed to async def
        """
        Handle the transcription process from audio input to text output. (Now asynchronous)

        Args:
            event: State machine event containing audio_data (BytesIO) and language info

        Returns:
            None: Results are passed to the callback function
        """
        logger.info(f"Starting transcription with {self.__class__.__name__}...")
        audio_data = event.kwargs.get("audio_data", None)
        language = event.kwargs.get("language")

        # Validate audio data
        if audio_data is None or audio_data.getbuffer().nbytes == 0:
            logger.warning("Invalid or empty audio data provided")
            self.callback(segments=[])
            return

        try:
            # Make API request and handle response
            success, result_or_error = await self.make_api_request(
                audio_data, language
            )  # Added await

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
            # try:
            #     if audio_filename and os.path.exists(audio_filename):
            #         os.unlink(audio_filename)
            #         logger.info(f"Temporary file {audio_filename} deleted")
            # except Exception as e:
            #     logger.error(f"Error deleting temporary file: {str(e)}")

            # Ensure the BytesIO object is closed if it's still open
            if audio_data and not audio_data.closed:
                try:
                    audio_data.close()
                    logger.info("In-memory audio data buffer closed.")
                except Exception as e:
                    logger.error(f"Error closing in-memory audio data buffer: {str(e)}")

            # Final garbage collection
            import gc

            gc.collect()


class GroqTranscriber(BaseTranscriber):
    """Handles audio transcription using the Groq API."""

    # Groq-specific configuration
    API_ENDPOINT = const.GROQ_API_ENDPOINT

    def __init__(self, callback: Callable, model: str = const.DEFAULT_GROQ_MODEL):
        """
        Initialize the Groq transcriber.

        Args:
            callback: Function to call with transcription results
            model: Name of the Groq model to use (default: DEFAULT_GROQ_MODEL)
        """
        super().__init__(callback, "GROQ_API_KEY", model)

    async def make_api_request(  # Changed to async def
        self, audio_data: io.BytesIO, language: str | None = None
    ) -> tuple[bool, dict | str]:
        """
        Make API request to Groq with retry mechanism. (Now asynchronous)

        Args:
            audio_data: BytesIO object containing audio WAV data
            language: Optional language code for transcription

        Returns:
            dict: JSON response from API if successful
            None: If all retries failed
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:  # Added aiohttp session
            for attempt in range(self.MAX_RETRIES):
                try:
                    audio_data.seek(0)
                    prompt = self.get_prompt(language)

                    form_data = aiohttp.FormData()
                    form_data.add_field("model", self.model)
                    form_data.add_field("prompt", prompt)
                    form_data.add_field("temperature", "0.0")

                    if language and isinstance(language, str):
                        form_data.add_field("language", language)
                        logger.info(f"Using language: {language}")

                    form_data.add_field(
                        "file",
                        audio_data,
                        filename="audio.wav",
                        content_type="audio/wav",
                    )

                    async with session.post(  # Changed to async session.post
                        self.API_ENDPOINT, headers=headers, data=form_data
                    ) as response:
                        if response.status == 200:
                            try:
                                result = await response.json()  # Added await
                                return (True, result)
                            except json.JSONDecodeError as e:
                                logger.error(
                                    f"Failed to decode JSON response: {str(e)}"
                                )
                                continue
                            except aiohttp.ContentTypeError as e:
                                logger.error(
                                    f"Unexpected content type: {str(e)}. Response text: {await response.text()}"
                                )
                                continue

                        elif response.status == 429:
                            retry_after = int(
                                response.headers.get(
                                    "Retry-After", str(self.INITIAL_RETRY_DELAY)
                                )
                            )
                            logger.warning(
                                f"Rate limited. Waiting {retry_after} seconds..."
                            )
                            await asyncio.sleep(retry_after)  # Changed to asyncio.sleep
                            continue
                        else:
                            response_text = await response.text()  # Added await
                            error_msg = (
                                f"API error: {response.status} - {response_text}"
                            )
                            logger.error(error_msg)

                            if response.status == 401:
                                error_msg = (
                                    "Invalid API key - please check your GROQ_API_KEY"
                                )
                                logger.error(error_msg)
                                return (False, error_msg)
                            elif response.status == 413:
                                error_msg = "Audio file too large - try recording a shorter segment"
                                logger.error(error_msg)
                                return (False, error_msg)

                            if attempt < self.MAX_RETRIES - 1:
                                wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                                logger.info(f"Retrying in {wait_time} seconds...")
                                await asyncio.sleep(
                                    wait_time
                                )  # Changed to asyncio.sleep

                except aiohttp.ClientError as e:  # Changed exception type
                    logger.error(f"Network error: {str(e)}")
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)  # Changed to asyncio.sleep
                except Exception as e:  # Catch other potential errors
                    logger.error(f"An unexpected error occurred: {str(e)}")
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)  # Changed to asyncio.sleep
                    else:
                        return (False, f"An unexpected error occurred: {str(e)}")

            # Force garbage collection after each attempt
            if (
                attempt % 2 == 1
            ):  # This remains outside the async with session block, which might be fine.
                import gc

                gc.collect()

        return (False, "Max retries exceeded for server/network error")


class OpenAITranscriber(BaseTranscriber):
    """Handles audio transcription using the OpenAI API."""

    # OpenAI-specific configuration
    API_ENDPOINT = const.OPENAI_API_ENDPOINT

    def __init__(self, callback: Callable, model: str = const.DEFAULT_OPENAI_MODEL):
        """
        Initialize the OpenAI transcriber.

        Args:
            callback: Function to call with transcription results
            model: Name of the OpenAI model to use (default: DEFAULT_OPENAI_MODEL)
        """
        super().__init__(callback, "OPENAI_API_KEY", model)

    async def make_api_request(  # Changed to async def
        self, audio_data: io.BytesIO, language: str | None = None
    ) -> tuple[bool, dict | str]:
        """
        Make API request to OpenAI with retry mechanism. (Now asynchronous)

        Args:
            audio_data: BytesIO object containing audio WAV data
            language: Optional language code for transcription

        Returns:
            dict: JSON response from API if successful
            None: If all retries failed
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:  # Added aiohttp session
            for attempt in range(self.MAX_RETRIES):
                try:
                    audio_data.seek(0)
                    prompt = self.get_prompt(language)

                    form_data = aiohttp.FormData()
                    form_data.add_field("model", self.model)
                    form_data.add_field("prompt", prompt)
                    form_data.add_field("temperature", "0.0")

                    if language and isinstance(language, str):
                        form_data.add_field("language", language)
                        logger.info(f"Using language: {language}")

                    form_data.add_field(
                        "file",
                        audio_data,
                        filename="audio.wav",
                        content_type="audio/wav",
                    )

                    async with session.post(  # Changed to async session.post
                        self.API_ENDPOINT, headers=headers, data=form_data
                    ) as response:
                        if response.status == 200:
                            try:
                                result = await response.json()  # Added await
                                return (True, result)
                            except json.JSONDecodeError as e:
                                logger.error(
                                    f"Failed to decode JSON response: {str(e)}"
                                )
                                continue
                            except aiohttp.ContentTypeError as e:
                                logger.error(
                                    f"Unexpected content type: {str(e)}. Response text: {await response.text()}"
                                )
                                continue

                        elif response.status == 429:
                            retry_after = int(
                                response.headers.get(
                                    "Retry-After", str(self.INITIAL_RETRY_DELAY)
                                )
                            )
                            logger.warning(
                                f"Rate limited. Waiting {retry_after} seconds..."
                            )
                            await asyncio.sleep(retry_after)  # Changed to asyncio.sleep
                            continue
                        else:
                            response_text = await response.text()  # Added await
                            error_msg = (
                                f"API error: {response.status} - {response_text}"
                            )
                            logger.error(error_msg)

                            if response.status == 401:
                                error_msg = (
                                    "Invalid API key - please check your OPENAI_API_KEY"
                                )
                                logger.error(error_msg)
                                return (False, error_msg)
                            elif (
                                response.status == 413
                            ):  # OpenAI uses 413 for payload too large
                                error_msg = (
                                    "Audio file too large - must be less than 25MB"
                                )
                                logger.error(error_msg)
                                return (False, error_msg)

                            if attempt < self.MAX_RETRIES - 1:
                                wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                                logger.info(f"Retrying in {wait_time} seconds...")
                                await asyncio.sleep(
                                    wait_time
                                )  # Changed to asyncio.sleep

                except aiohttp.ClientError as e:  # Changed exception type
                    logger.error(f"Network error: {str(e)}")
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)  # Changed to asyncio.sleep
                except Exception as e:  # Catch other potential errors
                    logger.error(f"An unexpected error occurred: {str(e)}")
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.INITIAL_RETRY_DELAY * (2**attempt)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)  # Changed to asyncio.sleep
                    else:
                        return (False, f"An unexpected error occurred: {str(e)}")

            # Force garbage collection after each attempt
            if (
                attempt % 2 == 1
            ):  # This remains outside the async with session block, which might be fine.
                import gc

                gc.collect()

        return (False, "Max retries exceeded for server/network error")

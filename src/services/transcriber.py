import asyncio
import io
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import aiohttp
import numpy as np
import soundfile
from faster_whisper import WhisperModel

from ..core import constants as const

logger = logging.getLogger(__name__)


class Segment:
    """Represents a segment of transcribed text."""

    def __init__(self, text: str):
        self.text = text


class BaseTranscriber(ABC):
    """Base class for audio transcription services."""

    def __init__(self, callback: Callable, model: str):
        self.callback = callback
        self.model = model

    def get_prompt(self, language: str | None) -> str:
        """Get a transcription prompt, tailored for technical content."""
        if language == "th":
            return "ถอดข้อความเสียงนี้ให้ถูกต้อง ใส่เครื่องหมายวรรคตอนให้เหมาะสม"
        return (
            "Transcribe this audio accurately. It likely contains technical software "
            "development terms like Typescript, JavaScript, React, Next.js, "
            "Expo, Supabase, PostgreSQL, Tailwind CSS, and system design. "
            "Prioritize correct spelling of technical terms."
        )

    @abstractmethod
    async def transcribe(self, event: Any):
        """Transcribes audio from an event and calls the callback."""
        pass

    @abstractmethod
    async def close(self):
        """Clean up resources."""
        pass


class APITranscriber(BaseTranscriber):
    """Base class for transcribers that call a web API."""

    API_ENDPOINT = ""
    API_KEY_ENV_VAR = ""

    def __init__(self, callback: Callable, model: str):
        super().__init__(callback, model)
        self.api_key = os.environ.get(self.API_KEY_ENV_VAR)
        if not self.api_key:
            raise ValueError(f"{self.API_KEY_ENV_VAR} environment variable not set.")
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=const.API_REQUEST_TIMEOUT_SECS)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info(f"{self.__class__.__name__} aiohttp session closed.")

    async def transcribe(self, event: Any):
        audio_data = None
        try:
            audio_data = event.kwargs.get("audio_data")
            language = event.kwargs.get("language")
            success, result = await self._make_api_request(audio_data, language)
            if success:
                segments = [Segment(result.get("text", ""))]
                self.callback(segments=segments)
            else:
                self.callback(segments=[], error=result)
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            self.callback(segments=[], error=str(e))
        finally:
            if audio_data and not audio_data.closed:
                audio_data.close()

    async def _make_api_request(
        self, audio_data: io.BytesIO, language: str | None
    ) -> tuple[bool, dict | str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        session = await self._get_session()

        for attempt in range(const.API_MAX_RETRIES):
            try:
                audio_data.seek(0)
                form_data = aiohttp.FormData()
                form_data.add_field("model", self.model)
                form_data.add_field("prompt", self.get_prompt(language))
                if language:
                    form_data.add_field("language", language)
                form_data.add_field(
                    "file", audio_data, filename="audio.wav", content_type="audio/wav"
                )

                async with session.post(
                    self.API_ENDPOINT, headers=headers, data=form_data
                ) as response:
                    if response.ok:
                        return True, await response.json()

                    error_text = await response.text()
                    logger.error(f"API Error: {response.status} - {error_text}")
                    if response.status == 401:
                        return False, f"Invalid API key for {self.__class__.__name__}"
                    if response.status == 429:  # Rate limit
                        sleep_duration = None
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                sleep_duration = int(retry_after)
                                logger.info(
                                    f"Rate limited. Retrying after {sleep_duration}s (from Retry-After header)."
                                )
                            except ValueError:
                                logger.warning(
                                    f"Invalid Retry-After header: '{retry_after}'. Using exponential backoff."
                                )

                        if sleep_duration is None:
                            sleep_duration = const.API_INITIAL_RETRY_DELAY_SECS * (
                                2**attempt
                            )
                            logger.info(
                                f"Rate limited. Retrying in {sleep_duration:.2f}s (exponential backoff)."
                            )

                        await asyncio.sleep(sleep_duration)
                        continue
                    # Other client/server errors
                    return False, f"API Error: {response.status}"

            except aiohttp.ClientError as e:
                logger.error(f"Network error on attempt {attempt + 1}: {e}")
                if attempt < const.API_MAX_RETRIES - 1:
                    await asyncio.sleep(
                        const.API_INITIAL_RETRY_DELAY_SECS * (2**attempt)
                    )
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                return False, "An unexpected error occurred"

        return False, "Max retries exceeded"


class OpenAITranscriber(APITranscriber):
    API_ENDPOINT = const.OPENAI_API_ENDPOINT
    API_KEY_ENV_VAR = "OPENAI_API_KEY"


class GroqTranscriber(APITranscriber):
    API_ENDPOINT = const.GROQ_API_ENDPOINT
    API_KEY_ENV_VAR = "GROQ_API_KEY"


class LocalTranscriber(BaseTranscriber):
    """Handles audio transcription using a local faster-whisper model."""

    def __init__(self, callback: Callable, model: str):
        super().__init__(callback, model)
        try:
            logger.info(f"Loading faster-whisper model: '{self.model}'")
            self.whisper_model = WhisperModel(
                self.model, device="cpu", compute_type="int8"
            )
            logger.info("Faster-whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            raise

    async def transcribe(self, event: Any):
        audio_data = None
        try:
            audio_data = event.kwargs.get("audio_data")
            language = event.kwargs.get("language")

            # Run blocking transcription in a separate thread
            full_text = await asyncio.to_thread(
                self._do_transcription, audio_data, language
            )
            segments = [Segment(full_text)]
            self.callback(segments=segments)
        except Exception as e:
            logger.error(f"Error during local transcription: {e}")
            self.callback(segments=[], error=str(e))
        finally:
            if audio_data and not audio_data.closed:
                audio_data.close()

    def _do_transcription(self, audio_data: io.BytesIO, language: str | None) -> str:
        """Synchronous helper to run in a thread."""
        audio_data.seek(0)
        audio_np, _ = soundfile.read(audio_data, dtype="float32")
        if audio_np.ndim > 1:
            audio_np = np.mean(audio_np, axis=1)

        segments, info = self.whisper_model.transcribe(
            audio_np, language=language, initial_prompt=self.get_prompt(language)
        )
        logger.info(
            f"Detected language: {info.language} ({info.language_probability:.2f})"
        )
        return "".join(segment.text for segment in segments)

    async def close(self):
        logger.info("Unloading faster-whisper model.")
        del self.whisper_model
        import gc

        gc.collect()

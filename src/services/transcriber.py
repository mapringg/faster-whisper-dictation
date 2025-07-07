import asyncio
import gc
import io
import logging
import os
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import aiohttp
import numpy as np
import soundfile
from faster_whisper import WhisperModel

from ..core import constants as const

logger = logging.getLogger(__name__)

# Global model cache to avoid reloading models
_model_cache = {}
_model_cache_lock = threading.Lock()


def get_cached_model(
    model_name: str, device: str = "cpu", compute_type: str = "int8"
) -> WhisperModel:
    """Get a cached WhisperModel instance or create a new one if not cached."""
    cache_key = f"{model_name}_{device}_{compute_type}"
    with _model_cache_lock:
        if cache_key not in _model_cache:
            logger.info(
                f"Loading faster-whisper model: '{model_name}' (device: {device}, compute_type: {compute_type})"
            )
            _model_cache[cache_key] = WhisperModel(
                model_name, device=device, compute_type=compute_type
            )
            logger.info(
                f"Faster-whisper model '{model_name}' loaded and cached successfully."
            )
        else:
            logger.info(f"Using cached faster-whisper model: '{model_name}'")
        return _model_cache[cache_key]


def clear_model_cache():
    """Clear all cached models and free memory."""
    global _model_cache
    with _model_cache_lock:
        if _model_cache:
            logger.info("Clearing model cache...")
            # Create a copy of keys to avoid dictionary changed size during iteration
            cache_keys = list(_model_cache.keys())
            for cache_key in cache_keys:
                logger.info(f"Unloading cached model: {cache_key}")
                del _model_cache[cache_key]
            _model_cache.clear()
            gc.collect()
            logger.info("Model cache cleared successfully.")


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

    def __init__(
        self,
        callback: Callable,
        model: str,
        session: aiohttp.ClientSession | None = None,
    ):
        super().__init__(callback, model)
        self.api_key = os.environ.get(self.API_KEY_ENV_VAR)
        if not self.api_key:
            raise ValueError(f"{self.API_KEY_ENV_VAR} environment variable not set.")
        self._session = session
        # Track whether we own the session (for cleanup)
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=const.API_REQUEST_TIMEOUT_SECS)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        # Only close session if we created it ourselves (not shared)
        if self._session and not self._session.closed and self._owns_session:
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
            self.whisper_model = get_cached_model(
                self.model, device="cpu", compute_type="int8"
            )
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
        logger.info("LocalTranscriber closed (model remains cached).")
        # Don't delete the model here as it's cached and shared
        # Model cleanup is handled by clear_model_cache() on application exit

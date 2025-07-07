import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ErrorData:
    """Structured error information for consistent error handling."""

    source: str  # Component that generated the error (e.g., "recorder", "transcriber")
    message: str  # Human-readable error message
    code: str | None = None  # Optional error code for programmatic handling
    details: str | None = None  # Additional details for debugging


@dataclass
class AppConfig:
    """Thread-safe configuration container for the dictation application."""

    # Command line arguments
    trigger_key: str
    cancel_key: str
    language: str
    model_name: str
    transcriber: str
    enable_sounds: bool
    vad: bool
    vad_sensitivity: int
    max_time: float | None

    # Internal lock for thread-safe updates
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_language(self, lang_code: str) -> None:
        """Thread-safe language update."""
        with self._lock:
            if self.language != lang_code:
                old_lang = self.language
                self.language = lang_code
                logger.info(f"Language changed from {old_lang} to {lang_code}")

    def set_enable_sounds(self, enabled: bool) -> None:
        """Thread-safe sound toggle update."""
        with self._lock:
            if self.enable_sounds != enabled:
                self.enable_sounds = enabled
                logger.info(f"Sound effects {'enabled' if enabled else 'disabled'}")

    def set_transcriber(self, transcriber_id: str) -> None:
        """Thread-safe transcriber update."""
        with self._lock:
            if self.transcriber != transcriber_id:
                old_transcriber = self.transcriber
                self.transcriber = transcriber_id
                logger.info(
                    f"Transcriber changed from {old_transcriber} to {transcriber_id}"
                )

    def set_model_name(self, model_name: str) -> None:
        """Thread-safe model name update."""
        with self._lock:
            if self.model_name != model_name:
                old_model = self.model_name
                self.model_name = model_name
                logger.info(f"Model changed from {old_model} to {model_name}")

    def get_language(self) -> str:
        """Thread-safe language getter."""
        with self._lock:
            return self.language

    def get_enable_sounds(self) -> bool:
        """Thread-safe sounds setting getter."""
        with self._lock:
            return self.enable_sounds

    def get_transcriber(self) -> str:
        """Thread-safe transcriber getter."""
        with self._lock:
            return self.transcriber

    def get_model_name(self) -> str:
        """Thread-safe model name getter."""
        with self._lock:
            return self.model_name

    @classmethod
    def from_args(cls, args) -> "AppConfig":
        """Create AppConfig from argparse.Namespace."""
        return cls(
            trigger_key=args.trigger_key,
            cancel_key=args.cancel_key,
            language=args.language,
            model_name=args.model_name,
            transcriber=args.transcriber,
            enable_sounds=args.enable_sounds,
            vad=args.vad,
            vad_sensitivity=args.vad_sensitivity,
            max_time=args.max_time,
        )

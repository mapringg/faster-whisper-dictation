# Improvement Plan: Centralize Constants

**Goal:** Improve code maintainability and readability by defining constants (like API endpoints, default values, magic strings/numbers) in a central place instead of scattering them throughout the codebase.

**Affected Files:**

- `src/core/constants.py` (New File)
- `src/services/transcriber.py`
- `src/services/input_handler.py`
- `src/services/status_indicator.py`
- `src/core/app.py`

**Steps:**

1.  **Create `src/core/constants.py`:**

    - Create a new empty file `src/core/constants.py`.

2.  **Define Constants:**

    - Add constants to `src/core/constants.py`:

      ```python
      # src/core/constants.py

      # API Endpoints
      OPENAI_API_ENDPOINT = "[https://api.openai.com/v1/audio/transcriptions](https://api.openai.com/v1/audio/transcriptions)"
      GROQ_API_ENDPOINT = "[https://api.groq.com/openai/v1/audio/transcriptions](https://api.groq.com/openai/v1/audio/transcriptions)"

      # Default API Models
      DEFAULT_OPENAI_MODEL = "gpt-4o-transcribe"
      DEFAULT_GROQ_MODEL = "whisper-large-v3"

      # API Request Config
      API_MAX_RETRIES = 3
      API_INITIAL_RETRY_DELAY_SECS = 1
      API_REQUEST_TIMEOUT_SECS = 30

      # KeyboardReplayer Config
      DEFAULT_TYPING_DELAY_SECS = 0.0025
      DEFAULT_MAX_TYPING_RETRIES = 3
      DEFAULT_RETRY_DELAY_SECS = 0.1

      # DoubleKeyListener Config
      DEFAULT_DOUBLE_CLICK_THRESHOLD_SECS = 0.5
      DEFAULT_MIN_PRESS_DURATION_SECS = 0.1

      # StatusIcon Config
      ICON_WIDTH_PX = 22
      ICON_HEIGHT_PX = 22
      ICON_PADDING_PX = 4

      # StatusIcon State Descriptions (or keep in StatusIcon class if preferred)
      STATE_DESC_READY = "Ready - Double tap to start recording"
      STATE_DESC_RECORDING = "Recording... - Tap once to stop"
      # ... other descriptions ...

      # Sound File Paths (relative to project root for now)
      SOUND_PATH_START = "assets/107786__leviclaassen__beepbeep.wav"
      SOUND_PATH_FINISH = "assets/559318__alejo902__sonido-3-regulator.wav"
      SOUND_PATH_CANCEL = "assets/160909__racche__scratch-speed.wav"
      # Add SOUND_PATH_ERROR if implementing error sounds

      # Other constants...
      DEFAULT_LANGUAGE = "en"
      DEFAULT_TRANSCRIBER = "openai"
      AUDIO_SAMPLE_RATE_HZ = 16000
      AUDIO_CHANNELS = 1
      RECORDER_SLEEP_INTERVAL_MS = 100

      ```

3.  **Refactor Code to Use Constants:**

    - **`transcriber.py`:**
      - `import src.core.constants as const`
      - Replace endpoint strings with `const.OPENAI_API_ENDPOINT`, `const.GROQ_API_ENDPOINT`.
      - Replace default model names in `__init__` signatures with `const.DEFAULT_OPENAI_MODEL`, `const.DEFAULT_GROQ_MODEL`.
      - Replace retry/timeout literals with `const.API_MAX_RETRIES`, `const.API_INITIAL_RETRY_DELAY_SECS`, `const.API_REQUEST_TIMEOUT_SECS`.
    - **`input_handler.py`:**
      - `import src.core.constants as const`
      - Replace default literals in `KeyboardReplayer.__init__` with `const.DEFAULT_TYPING_DELAY_SECS`, etc.
      - Replace default literals in `DoubleKeyListener.__init__` with `const.DEFAULT_DOUBLE_CLICK_THRESHOLD_SECS`, etc.
    - **`status_indicator.py`:**
      - `import src.core.constants as const`
      - Replace icon dimension/padding literals with `const.ICON_WIDTH_PX`, etc.
      - Replace state description strings with `const.STATE_DESC_READY`, etc. (if moved to constants).
      - Replace default language/transcriber strings with `const.DEFAULT_LANGUAGE`, `const.DEFAULT_TRANSCRIBER`.
    - **`app.py`:**
      - `import src.core.constants as const`
      - Replace sound file path strings in `_load_sound_effects` with `const.SOUND_PATH_START`, etc.
      - Replace default language/transcriber values where used with `const.DEFAULT_LANGUAGE`, `const.DEFAULT_TRANSCRIBER`.
    - **`recorder.py`:**
      - `import src.core.constants as const`
      - Replace samplerate/channels literals with `const.AUDIO_SAMPLE_RATE_HZ`, `const.AUDIO_CHANNELS`.
      - Replace sleep interval literal with `const.RECORDER_SLEEP_INTERVAL_MS`.

4.  **Update Imports:**
    - Ensure the `constants` module can be imported correctly (e.g., adjust Python path if necessary, or use relative imports like `from ..core import constants`).

**Rationale:** Centralizing constants makes configuration easier to find and modify. It reduces the risk of typos or inconsistencies when the same value is used in multiple places. It improves code readability by giving meaningful names to magic numbers and strings.

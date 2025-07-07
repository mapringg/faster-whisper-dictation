# API Endpoints
OPENAI_API_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
GROQ_API_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"

# Default API Models
DEFAULT_OPENAI_MODEL = "gpt-4o-transcribe"
DEFAULT_GROQ_MODEL = "whisper-large-v3"
DEFAULT_LOCAL_MODEL = "base"  # e.g., "tiny", "base", "small"

# API Request Config
API_MAX_RETRIES = 3
API_INITIAL_RETRY_DELAY_SECS = 1
API_REQUEST_TIMEOUT_SECS = 30

# DoubleKeyListener Config
DEFAULT_DOUBLE_CLICK_THRESHOLD_SECS = 0.5
DEFAULT_MIN_PRESS_DURATION_SECS = 0.1

# StatusIcon Config
ICON_WIDTH_PX = 22
ICON_HEIGHT_PX = 22
ICON_PADDING_PX = 4

# StatusIcon State Descriptions
STATE_DESC_READY = "Ready - Double tap to start recording"
STATE_DESC_RECORDING = "Recording... - Tap once to stop"
STATE_DESC_TRANSCRIBING = "Transcribing... please wait"
STATE_DESC_REPLAYING = "Replaying text..."
STATE_DESC_ERROR = "Error occurred"

# Sound File Paths (relative to project root)
SOUND_PATH_START = "assets/107786__leviclaassen__beepbeep.wav"
SOUND_PATH_FINISH = "assets/559318__alejo902__sonido-3-regulator.wav"
SOUND_PATH_CANCEL = "assets/160909__racche__scratch-speed.wav"

# Other constants
DEFAULT_LANGUAGE = "en"
DEFAULT_TRANSCRIBER = "groq"
AUDIO_SAMPLE_RATE_HZ = 16000
AUDIO_CHANNELS = 1
RECORDER_SLEEP_INTERVAL_MS = 100

# App timing constants
STATE_CHANGE_DELAY_SECS = 0.5
ERROR_STATE_DISPLAY_DURATION_SECS = 1.5

# Recorder constants
RECORDER_LOOP_SLEEP_MS = 100
VAD_MIN_SILENCE_FRAMES_TO_STOP = 10
VAD_FRAME_DURATION_MS = 30
CLIPBOARD_PASTE_DELAY_SECS = 0.1

# Audio stream error handling
MAX_STREAM_ERRORS = 5
DEVICE_REFRESH_DELAY_SECS = 0.5

# Threading timeouts
TRANSCRIBER_CLOSE_TIMEOUT_SECS = 5
ASYNC_THREAD_JOIN_TIMEOUT_SECS = 2
TRANSCRIBER_CLEANUP_TIMEOUT_SECS = 2

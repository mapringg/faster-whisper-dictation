import argparse
import platform

from src.core import constants as const


def parse_args():
    # Set default trigger key based on platform
    if platform.system() == "Darwin":  # macOS
        default_trigger_key = "Key.cmd_r"
        default_trigger_desc = "Right Command key"
    else:  # Linux
        default_trigger_key = "Key.ctrl_r"
        default_trigger_desc = "Right Ctrl key"

    parser = argparse.ArgumentParser(
        description="Dictation app powered by local or cloud-based transcription."
    )
    parser.add_argument(
        "--transcriber",
        type=str,
        choices=["openai", "groq", "local"],
        default="openai",
        help="Transcription service to use. Default: openai.",
    )
    parser.add_argument(
        "-m",
        "--model-name",
        type=str,
        default=None,
        help=f"""Model to use for transcription.
If not set, uses default for selected transcriber:
- openai: {const.DEFAULT_OPENAI_MODEL}
- groq: {const.DEFAULT_GROQ_MODEL}
- local: {const.DEFAULT_LOCAL_MODEL}""",
    )
    parser.add_argument(
        "-d",
        "--trigger-key",
        type=str,
        default=default_trigger_key,
        help=f"""Key to use for triggering recording. Double tap to start, single tap to stop.
Default: {default_trigger_desc}.
Use pynput format, e.g., 'Key.alt_l', '<ctrl>+c'.""",
    )
    parser.add_argument(
        "-t",
        "--max-time",
        type=int,
        default=None,
        help="Maximum recording time in seconds. Recording stops automatically after this duration.",
    )
    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default="en",
        help="Language of the audio for transcription (e.g., 'en', 'fr', 'th'). Default: 'en'.",
    )
    parser.add_argument(
        "--enable-sounds",
        action="store_true",
        default=False,
        help="Enable sound effects for recording actions (start, stop, cancel).",
    )
    # VAD arguments
    parser.add_argument(
        "--vad",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable Voice Activity Detection (VAD). Default: --vad.",
    )
    parser.add_argument(
        "--vad-sensitivity",
        type=int,
        choices=[0, 1, 2, 3],
        default=1,
        help="Set VAD sensitivity (0=least aggressive, 3=most aggressive). Default: 1.",
    )

    args = parser.parse_args()

    # Set default model name if not provided
    if args.model_name is None:
        if args.transcriber == "openai":
            args.model_name = const.DEFAULT_OPENAI_MODEL
        elif args.transcriber == "groq":
            args.model_name = const.DEFAULT_GROQ_MODEL
        else:  # local
            args.model_name = const.DEFAULT_LOCAL_MODEL

    return args

import argparse
import platform


def parse_args():
    # Set default trigger key based on platform
    if platform.system() == "Darwin":  # macOS
        default_trigger_key = "Key.cmd_r"  # Right Command key
        default_trigger_desc = "Right Command key (Key.cmd_r)"
    else:  # Linux and other platforms
        default_trigger_key = "Key.alt_l"  # Left Alt key
        default_trigger_desc = "Left Alt key (Key.alt_l)"

    parser = argparse.ArgumentParser(
        description="Dictation app powered by OpenAI and Groq APIs"
    )
    parser.add_argument(
        "-m",
        "--model-name",
        type=str,
        default="gpt-4o-transcribe",
        help="""\
Model to use for transcription.
For OpenAI: gpt-4o-transcribe
For Groq: whisper-large-v3""",
    )
    parser.add_argument(
        "--transcriber",
        type=str,
        choices=["openai", "groq"],
        default="openai",
        help="""\
Transcription service to use (default: openai)""",
    )
    parser.add_argument(
        "-d",
        "--trigger-key",
        type=str,
        default=default_trigger_key,
        help=f"""\
Key to use for triggering recording. Double tap to start, single tap to stop.
Default: {default_trigger_desc}

For special keys, use Key.name format: Key.cmd_r, Key.alt_r, etc.
See https://pynput.readthedocs.io/en/latest/keyboard.html#pynput.keyboard.Key for supported keys.""",
    )
    parser.add_argument(
        "-t",
        "--max-time",
        type=int,
        default=None,
        help="""\
Specify the maximum recording time in seconds.
The app will automatically stop recording after this duration.
If not specified, recording will continue until manually stopped or file size limit is reached.""",
    )
    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default="en",
        help="""\
Specify the language of the audio for better transcription accuracy.
If not specified, defaults to English ('en').
Example: 'en' for English, 'fr' for French, etc.

Supported languages: af, am, ar, as, az, ba, be, bg, bn, bo, br, bs, ca, cs, cy, da, de, el, en, es, et, eu, fa, fi, fo, fr, gl, gu, ha, haw, he, hi, hr, ht, hu, hy, id, is, it, ja, jv, ka, kk, km, kn, ko, la, lb, ln, lo, lt, lv, mg, mi, mk, ml, mn, mr, ms, mt, my, ne, nl, nn, no, oc, pa, pl, ps, pt, ro, ru, sa, sd, si, sk, sl, sn, so, sq, sr, su, sv, sw, ta, te, tg, th, tl, tr, tt, uk, ur, uz, vi, yi, yo, yue, zh""",
    )
    parser.add_argument(
        "--enable-sounds",
        action="store_true",
        default=False,
        help="""\
Enable sound effects for recording actions (start, stop, cancel).
By default, sound effects are disabled.""",
    )

    args = parser.parse_args()
    return args

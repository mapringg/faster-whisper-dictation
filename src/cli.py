import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Dictation app powered by Groq API")
    parser.add_argument(
        "-m",
        "--model-name",
        type=str,
        default="whisper-large-v3",
        help="""\
Groq model to use for transcription.
Default: whisper-large-v3.""",
    )
    parser.add_argument(
        "-d",
        "--trigger-key",
        type=str,
        default="<alt_l>",
        help="""\
Key to use for triggering recording. Double tap to start, single tap to stop.
Default: Left Alt (<alt_l>)

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

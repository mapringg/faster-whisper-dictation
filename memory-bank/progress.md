# Progress

## Completed Tasks

- [YYYY-MM-DD HH:MM:SS] - Initial population of Memory Bank documentation based on codebase analysis.
- [YYYY-MM-DD HH:MM:SS] - Implemented environment variable loading from `$HOME/.env` and `./.env` with correct priority (Shell > Project > Home) in both Python app (`src/services/transcriber.py`) and `run.sh`.
- [YYYY-MM-DD HH:MM:SS] - Ensured `BaseTranscriber` initialization respects environment variable priority.
- [YYYY-MM-DD HH:MM:SS] - Aligned Linux text output with macOS using copy/paste (`xsel` + `uinput` for Ctrl+V).

## Current Tasks

- [YYYY-MM-DD HH:MM:SS] - Verifying the effectiveness of using `xsel` instead of `xclip` to resolve Linux copy delays (see Active Context).

## Next Steps

- [YYYY-MM-DD HH:MM:SS] - Gather feedback/test results on the `xsel` fix.
- [YYYY-MM-DD HH:MM:SS] - Define further development tasks ("What's Left to Build").

## Known Issues/Bugs

- Linux functionality depends on `xsel` being installed manually (`setup.sh` only warns).
- Linux keyboard simulation requires user to be in the `input` group (handled by `setup.sh`, but may require logout/login).

_[YYYY-MM-DD HH:MM:SS] - Reformatted progress, removed integrated decision log (now in decisionLog.md)._

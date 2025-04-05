# Progress

## Completed Tasks / Milestones

- [Decision Log Ref] - Removed local `faster-whisper` transcription support to focus exclusively on cloud APIs.
- [Decision Log Ref] - Implemented project-level `.env` support alongside home `.env` and shell variables with correct priority (Shell > Project > Home).
- [Decision Log Ref] - Aligned Linux text output with macOS using copy/paste (initially `xclip`, later switched to `xsel` due to delays) combined with keyboard simulation (`uinput` for Ctrl+V).
- [Decision Log Ref] - Selected and implemented `python-uinput` for Linux keyboard simulation.
- [Decision Log Ref] - Selected and implemented `pynput` for macOS keyboard simulation.
- [Decision Log Ref] - Adopted script-based installation (`setup.sh`, `revert_setup.sh`) for simplified setup.
- [Decision Log Ref] - Implemented `pre-commit` hooks for automated code quality checks.
- [Previous Progress] - Initial population of Memory Bank documentation.
- [Previous Progress] - Ensured `BaseTranscriber` initialization respects environment variable priority.

## Current Tasks

- [YYYY-MM-DD HH:MM:SS] - Verifying the effectiveness of using `xsel` instead of `xclip` to resolve Linux copy delays (see Active Context).

## Next Steps

- [YYYY-MM-DD HH:MM:SS] - Gather feedback/test results on the `xsel` fix.
- [YYYY-MM-DD HH:MM:SS] - Define further development tasks ("What's Left to Build").

## Known Issues/Bugs

- Linux functionality depends on `xsel` being installed manually (`setup.sh` only warns).
- Linux keyboard simulation requires user to be in the `input` group (handled by `setup.sh`, but may require logout/login).

_[YYYY-MM-DD HH:MM:SS] - Reformatted progress, removed integrated decision log (now in decisionLog.md)._

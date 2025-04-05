# Active Context

## Current Focus

[YYYY-MM-DD HH:MM:SS] - Debugging and verifying the fix for Linux copy-paste functionality using `xsel`. The primary goal is to confirm that switching from `xclip` to `xsel` has resolved the previously observed copy delay.

## Recent Changes

[YYYY-MM-DD HH:MM:SS] - Switched Linux clipboard interaction from `xclip` to `xsel --clipboard --input`. - Modified `src/services/input_handler.py` to use `xsel`. - Modified `setup.sh` to check for `xsel`. - Updated `README.md`, `memory-bank/systemPatterns.md`, and `memory-bank/progress.md` to reflect the change. - This followed previous attempts to fix `xclip` delays by using `subprocess.Popen` + `communicate()` and adding delays to `uinput`, which were only partially successful (paste worked, delay remained).

## Next Steps

- Await user feedback/testing results to confirm if the `xsel` implementation resolves the copy delay issue on Linux.
- If issues persist, investigate further:
  - Potential interactions with specific clipboard managers.
  - Explore alternative clipboard libraries (e.g., `pyperclip`).

## Open Questions/Issues

- Is the copy delay fully resolved across different Linux environments with `xsel`?
- Are there any edge cases or specific desktop environments where `xsel` might behave differently?
- Does the `uinput` paste simulation remain reliable?

## Learnings/Insights

- `xclip` can exhibit unexpected delays in certain environments, even when invoked via `subprocess.Popen`.
- `xsel` provides a viable alternative command-line utility for clipboard interaction on Linux.
- Debugging platform-specific issues often requires isolating dependencies and testing alternatives (e.g., `xclip` vs `xsel`).

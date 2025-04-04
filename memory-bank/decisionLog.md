# Decision Log

[YYYY-MM-DD HH:MM:SS] - Removed local `faster-whisper` transcription support.

- **Rationale:** Focus exclusively on cloud APIs (OpenAI/Groq) for improved transcription accuracy and speed, simplifying the codebase and dependencies.
- **Implementation:** Removed local model loading and processing logic.

[YYYY-MM-DD HH:MM:SS] - Implemented project-level `.env` support alongside home `.env` and shell variables.

- **Rationale:** Allow project-specific configuration overrides while maintaining global defaults and respecting shell environment variables. Establish clear loading priority (Shell > Project > Home).
- **Implementation:** Modified `src/core/utils.py::load_env_from_file`, `src/services/transcriber.py`, and `run.sh`.

[YYYY-MM-DD HH:MM:SS] - Aligned Linux text output with macOS using copy/paste.

- **Rationale:** Replace character-by-character typing on Linux with a copy (`xclip` initially) and paste (Ctrl+V via `uinput`) mechanism for consistency with macOS (`pbcopy`/Cmd+V) and potential speed improvements.
- **Implementation:** Modified `src/services/input_handler.py`, `src/services/uinput_controller.py`, `setup.sh`, and documentation.

[YYYY-MM-DD HH:MM:SS] - Attempted to fix Linux copy-paste issues (with `xclip`).

- **Rationale:** Address reported `xclip` delay and paste unreliability.
- **Implementation:** Switched `xclip` call from `subprocess.run` to `subprocess.Popen` with `communicate()`. Added small delays to `uinput` key press/release events. Modified `src/services/input_handler.py` and `src/services/uinput_controller.py`.
- **Outcome:** Paste worked, but `xclip` delay persisted.

[YYYY-MM-DD HH:MM:SS] - Switched Linux clipboard utility from `xclip` to `xsel`.

- **Rationale:** Investigate if the persistent copy delay was specific to `xclip` interaction. `xsel` is a viable alternative.
- **Implementation:** Modified `setup.sh`, `README.md`, `memory-bank/tech-context.md` (now removed), `memory-bank/systemPatterns.md`, and `src/services/input_handler.py`.

[YYYY-MM-DD HH:MM:SS] - Selected `python-uinput` for Linux keyboard simulation.

- **Rationale:** Provides necessary functionality to interact with the kernel's uinput module for simulating keyboard events on Linux.
- **Implementation:** Added `python-uinput` to dependencies, implemented `UInputController` in `src/services/uinput_controller.py`. Requires user in `input` group.

[YYYY-MM-DD HH:MM:SS] - Selected `pynput` for macOS keyboard simulation.

- **Rationale:** Standard library for cross-platform keyboard/mouse control, suitable for macOS paste simulation.
- **Implementation:** Added `pynput` to dependencies, implemented macOS-specific logic in `KeyboardControllerFactory` and potentially a dedicated controller. Requires Accessibility permissions.

[YYYY-MM-DD HH:MM:SS] - Adopted script-based installation (`setup.sh`, `revert_setup.sh`).

- **Rationale:** Provide a straightforward method for users to set up dependencies, virtual environment, and system services (systemd/launchd) without requiring complex packaging knowledge.
- **Implementation:** Created `setup.sh` and `revert_setup.sh` scripts.

[YYYY-MM-DD HH:MM:SS] - Implemented `pre-commit` for code quality checks.

- **Rationale:** Enforce code style (formatting, linting) automatically before commits to maintain consistency and quality.
- **Implementation:** Configured `.pre-commit-config.yaml` with relevant hooks (e.g., black, flake8, isort).

# Improvement Plan: Separate Development/Debugging Dependencies

**Goal:** Move dependencies only required for debugging (like memory monitoring) into optional dependencies, keeping the core application's requirements minimal.

**Affected Files:**

- `pyproject.toml`
- `requirements.txt`
- `test_memory_fix.sh`
- `README.md` or `CONTRIBUTING.md`

**Steps:**

1.  **Define Optional Dependencies (`pyproject.toml`):**

    - Ensure you have a `[project]` section defined in `pyproject.toml` (needed for `optional-dependencies`). If not, add basic project metadata.
    - Add the `[project.optional-dependencies]` table:

      ```toml
      [project]
      name = "faster-whisper-dictation"
      version = "0.1.0" # Example version
      # Add other metadata like authors, description if missing
      requires-python = ">=3.8"
      dependencies = [
          # List core dependencies explicitly here OR rely on requirements.txt
          # Example:
          "pynput>=1.7.8; platform_system == 'Darwin'",
          "python-uinput>=0.11.2; platform_system == 'Linux'",
          "PyGObject==3.50.0; platform_system == 'Linux'",
          # "pyaudio", # Often problematic, might need separate install instructions
          "keyboard",
          "argparse",
          "transitions",
          "numpy",
          "requests",
          "sounddevice",
          "soundfile",
          "wave",
          "pystray",
          "Pillow"
      ]

      [project.optional-dependencies]
      dev = [
          "matplotlib",
          "psutil",
          # Add other dev tools if needed, e.g., "pytest"
      ]

      # Ensure build backend is specified (usually setuptools)
      [build-system]
      requires = ["setuptools>=42"]
      build-backend = "setuptools.build_meta"

      # Keep ruff configuration
      [tool.ruff]
      # ... ruff settings ...
      ```

    - _Note:_ Managing dependencies _both_ here and in `requirements.txt` can be redundant. Choose one primary source. If using `pyproject.toml`, `requirements.txt` might only be needed for specific platform markers if `pyproject.toml` doesn't handle them well, or for `pip install -r`. Let's assume `pyproject.toml` becomes the primary source.

2.  **Clean `requirements.txt`:**

    - Remove `matplotlib` and `psutil` from `requirements.txt`.
    - _Either_ remove all other dependencies if `pyproject.toml` lists them _or_ keep `requirements.txt` for `pip install -r` workflows but ensure it mirrors `pyproject.toml [project] dependencies`.

3.  **Modify `test_memory_fix.sh`:**

    - Remove the line `pip install -q psutil matplotlib`.
    - _Before_ running `python memory_monitor.py`, add a check:

      ```bash
      # Check if monitoring tools are installed
      if ! python -c "import matplotlib" 2>/dev/null || ! python -c "import psutil" 2>/dev/null; then
           log "Error: matplotlib or psutil not found."
           log "Please install development dependencies: pip install -e .[dev]"
           exit 1
      fi

      log "Starting memory monitoring..."
      python memory_monitor.py --pid $PROCESS_ID # ... rest of args ...
      ```

4.  **Update Documentation (`README.md` or `CONTRIBUTING.md`):**
    - Add a section explaining how to install dependencies for development or debugging.
    - Instruct users to run `pip install -e .[dev]` from the project root after cloning and setting up the virtual environment. Explain this installs the core app in editable mode plus the debugging tools.

**Rationale:** This separates runtime dependencies from development/debugging tools. Users installing the application only get what's needed to run it. Developers or users needing to debug memory issues can easily install the extra tools without bloating the core installation. Using `pyproject.toml` aligns with modern Python packaging standards.

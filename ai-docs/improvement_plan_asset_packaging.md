# Improvement Plan: Ensure Sound Asset Packaging (for Distribution)

**Goal:** Modify the application to correctly locate sound asset files (`.wav`) when installed as a package, rather than relying on a relative `assets` directory path. (Note: Only relevant if distributing as an installable package).

**Affected Files:**

- `src/core/app.py`
- `pyproject.toml` (or `setup.py`/`setup.cfg`)
- Potentially requires restructuring `assets` directory.

**Steps:**

_(These steps assume packaging using `setuptools` and `pyproject.toml`)_

1.  **Configure Package Data (`pyproject.toml`):**

    - Ensure the build system is configured (`[build-system]`).
    - Add configuration to include the `.wav` files from the `assets` directory. The method depends slightly on project structure. Assuming `assets` is _inside_ the `src` directory (`src/assets`):

      ```toml
      [tool.setuptools]
      # Include package data specified in MANIFEST.in (alternative)
      # include-package-data = true

      [tool.setuptools.package-data]
      # If 'src' is the package root directory containing your 'core', 'services' modules
      "src" = ["assets/*.wav"]
      # OR if your package is named 'faster_whisper_dictation' and assets is inside it:
      # "faster_whisper_dictation" = ["assets/*.wav"]
      ```

    - _Alternative: `MANIFEST.in`_ Create a `MANIFEST.in` file in the project root:
      ```
      recursive-include src/assets *.wav
      ```
      And ensure `include-package-data = true` is set in `pyproject.toml` or `setup.cfg`.

2.  **Modify Asset Loading (`app.py`):**

    - Import the necessary resource handling library:
      ```python
      try:
          # Python 3.7+
          from importlib import resources
      except ImportError:
          # Fallback for older setuptools/Python (might need setup dependency)
          import pkg_resources
      ```
    - Modify `App._load_sound_effects`: Use the resource library to get paths to the packaged assets.

      ```python
      def _load_sound_effects(self) -> dict[str, np.ndarray | None]:
          sounds = {}
          sound_files = {
              "start_recording": "beepbeep.wav",
              "finish_recording": "sonido-3-regulator.wav",
              "cancel_recording": "scratch-speed.wav",
          }
          package_name = "src" # The package/directory containing 'assets'

          for name, filename in sound_files.items():
              try:
                  if 'resources' in locals(): # Use importlib.resources if available
                      # Need to adjust 'package_name.assets' based on actual structure
                      with resources.path(f"{package_name}.assets", filename) as wav_path:
                           sounds[name] = loadwav(str(wav_path))
                  elif 'pkg_resources' in locals(): # Fallback
                       resource_path = pkg_resources.resource_filename(package_name, f"assets/{filename}")
                       sounds[name] = loadwav(resource_path)
                  else:
                       raise RuntimeError("Cannot load package resources.")
              except Exception as e:
                  logger.error(f"Failed to load sound effect '{filename}': {e}")
                  sounds[name] = None
          return sounds

      ```

    - **Important:** Adjust `package_name` and the path string (`f"{package_name}.assets"`) based on how your project is structured and named as a Python package (e.g., is `src` the package root, or is there a specific package name inside `src`?).

**Rationale:** When a user installs the package (e.g., via `pip install .`), the code might run from a system-wide `site-packages` directory. Relative paths like `"assets/..."` will fail because the `assets` directory isn't there. Using `importlib.resources` or `pkg_resources` provides a standard way to access data files that were included with the installed package, regardless of where the package is installed. This is essential for creating a distributable version of the application.

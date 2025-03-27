# Improvement Plan: Make Typing Delay Configurable

**Goal:** Allow users to adjust the delay between typed characters via a command-line argument, accommodating systems with different responsiveness.

**Affected Files:**

- `src/cli.py`
- `src/core/app.py`
- `src/services/input_handler.py`
- `src/core/constants.py` (Optional, for default value)

**Steps:**

1.  **Add Command-Line Argument (`cli.py`):**
    _ Import `DEFAULT_TYPING_DELAY_SECS` from `constants` (if defined there, see Plan 13).
    `python
        # At top of cli.py (or where constants are imported)
        # from .core.constants import DEFAULT_TYPING_DELAY_SECS # Adjust import path
        # Or define the default directly here if not using constants file yet
        DEFAULT_TYPING_DELAY_SECS = 0.0025
        `
    _ Add a new argument to the `ArgumentParser`:
    `python
        parser.add_argument(
            "--typing-delay",
            type=float,
            default=DEFAULT_TYPING_DELAY_SECS,
            help=f"""\
Delay between typed characters in seconds.
Increase if characters are missed, decrease for faster typing.
Default: {DEFAULT_TYPING_DELAY_SECS}""",
        )
        `

2.  **Pass Argument to `KeyboardReplayer` (`app.py`):**

    - In `App.__init__`, when creating the `KeyboardReplayer` instance, pass the value from `args`:
      ```python
      # Inside App.__init__
      self.replayer = KeyboardReplayer(
          self.m.finish_replaying,
          typing_delay=args.typing_delay # Pass the argument value
      )
      ```

3.  **Update `KeyboardReplayer` (`input_handler.py`):**

    - Modify `KeyboardReplayer.__init__` to accept and store the `typing_delay`:

      ```python
      # Import the constant for the default value in the signature
      # from ..core.constants import DEFAULT_TYPING_DELAY_SECS # Adjust path

      class KeyboardReplayer:
          # Define class constant for default if not using constants file
          # DEFAULT_TYPING_DELAY = 0.0025

          def __init__(
              self,
              callback: KeyboardCallback,
              keyboard_controller: Any | None = None,
              typing_delay: float = DEFAULT_TYPING_DELAY_SECS, # Use constant/default
              max_retries: int = ..., # Keep other args
              retry_delay: float = ...,
          ):
              self.callback = callback
              self.kb = (...)
              self.typing_delay = typing_delay # Store the passed value
              self.max_retries = max_retries
              self.retry_delay = retry_delay
              self.lock = threading.Lock()
      ```

    - Ensure the `replay` method uses `self.typing_delay` in `time.sleep(self.typing_delay)`. (It already seems to do this).

4.  **Update Documentation (`README.md`):**
    - Add the new `--typing-delay` option to the "Options" section, explaining its purpose and default value.

**Rationale:** Typing speed can be system-dependent. A fixed delay might be too fast for some systems (missing characters) or unnecessarily slow for others. Making it configurable provides flexibility for the user to fine-tune the performance based on their experience.

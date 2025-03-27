# Improvement Plan: Simplify or Remove PlatformHandler

**Goal:** Remove the `PlatformHandler` class hierarchy as its primary distinction (cancel key) can be handled more simply, and the common task (`run_main_tasks`) doesn't require the abstraction.

**Affected Files:**

- `src/core/app.py`

**Steps:**

1.  **Determine Platform-Specific Keys in `App.__init__`:**

    - Add `import platform` and `from pynput import keyboard` at the top of `src/core/app.py`.
    - Inside `App.__init__`, determine and store the cancel key and its name directly:

      ```python
      # Inside App.__init__
      self.args = args
      self.language = args.language
      # ... other initializations ...

      # Determine platform-specific cancel key
      if platform.system() == "Darwin":
          self.cancel_key = keyboard.Key.alt_r  # Right Option
          self.cancel_key_name = "right option"
      else: # Linux, Windows (assuming Left Ctrl)
          self.cancel_key = keyboard.Key.ctrl_l # Left Control
          self.cancel_key_name = "left control"

      # ... rest of __init__ (state machine, components, etc.)
      ```

2.  **Update Key Listener Setup:**

    - In `App._setup_key_listener`:

      - Use `self.cancel_key` directly when creating the `cancel_listener`:

        ```python
        # ... get trigger_key ...
        # Use stored platform-specific key
        cancel_key = self.cancel_key

        key_listener = DoubleKeyListener(self.start, self.stop, trigger_key)
        cancel_listener = DoubleKeyListener(
            self.cancel_recording, lambda: None, cancel_key
        )
        return key_listener, cancel_listener
        ```

3.  **Update Log Message:**

    - In `App._on_enter_ready`:
      - Use `self.cancel_key_name` directly in the log message:
        ```python
        # ... inside _on_enter_ready, within status_icon_lock
        cancel_key_name = self.cancel_key_name # Get stored name
        logger.info(
            f"Double tap {self.args.trigger_key} to start recording. "
            f"Tap once to stop recording. "
            f"Double tap {cancel_key_name} to cancel recording."
        )
        # ... update status icon ...
        ```

4.  **Inline `run_main_tasks` Logic:**

    - In `App.run`:

      - Move the logic previously in `PlatformHandler.run_main_tasks` directly into this method, after setting up listeners and before the `finally` block.

      ```python
      # Inside App.run, after setting up keylistener, cancel_listener
      key_listener_thread = threading.Thread(target=keylistener.run, daemon=True)
      cancel_listener_thread = threading.Thread(
          target=cancel_listener.run, daemon=True
      )

      logger.info("Starting key listener threads...")
      key_listener_thread.start()
      cancel_listener_thread.start()

      logger.info("Handing control to status icon main loop...")
      # Assuming run_icon_on_main_thread takes the icon instance (from Plan 2)
      run_icon_on_main_thread(self.status_icon._icon)

      logger.info("Status icon loop finished. Waiting for listener threads...")
      # Optional join removed as per original code
      logger.info("Exiting application run method.")
      ```

5.  **Remove PlatformHandler Classes:**
    - Delete the `PlatformHandler`, `MacOSHandler`, and `DefaultHandler` class definitions from `src/core/app.py`.
    - Remove the call `platform_handler = PlatformHandler.get_handler()` in `App.run`.

**Rationale:** The abstraction provided by `PlatformHandler` was minimal, primarily differentiating the cancel key. Handling this difference directly in `__init__` based on `platform.system()` is simpler, reduces boilerplate code, and makes the platform-specific logic more direct and easier to locate.

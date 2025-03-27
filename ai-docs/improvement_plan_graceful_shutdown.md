# Improvement Plan: Implement Graceful Application Shutdown

**Goal:** Replace the current marker file and `os._exit(0)` shutdown mechanism with a cleaner approach using signals and thread coordination for graceful resource cleanup and termination.

**Affected Files:**

- `src/core/app.py`
- `src/services/status_indicator.py`
- `run.sh` (Remove marker check)

**Steps:**

1.  **Introduce Shutdown Event (`app.py`):**

    - Add `import signal` and `import threading` at the top.
    - In `App.__init__`, add `self.shutdown_event = threading.Event()`.

2.  **Define Signal Handler (`app.py`):**

    - Add a method to the `App` class:
      ```python
      def signal_handler(self, signum, frame):
          logger.warning(f"Received signal {signum}. Initiating shutdown...")
          self.shutdown_event.set()
      ```

3.  **Register Signal Handler (`app.py`):**

    - In `App.run`, _before_ starting threads or the icon loop:
      ```python
      signal.signal(signal.SIGINT, self.signal_handler)  # Handle Ctrl+C
      signal.signal(signal.SIGTERM, self.signal_handler) # Handle kill/systemd stop
      ```
    - _Note:_ Signal handlers typically need to run on the main thread. Ensure `App.run` is called from the main thread.

4.  **Modify `App._exit_app` (`app.py`):**

    - Simplify the method significantly:
      ```python
      def _exit_app(self):
          logger.info("Exit requested via menu. Initiating shutdown...")
          self.shutdown_event.set()
          # Return False for pystray menu item if it shouldn't close menu immediately
          # Return True if the menu action itself should trigger the stop (depends on pystray)
          # Let's assume returning False is better, letting the main loop handle stop.
          return False
      ```
    - Remove the marker file creation logic (`/tmp/dictation_user_exit`).
    - Remove the call to `os._exit(0)`.

5.  **Modify Main Loop (`status_indicator.py` / `app.py`):**

    - The main blocking call is `run_icon_on_main_thread(self.status_icon._icon)`. We need this loop to check `self.shutdown_event`.
    - **Integration with Plan 1 (Queue):** If using the queue approach, the main loop in `run_icon_on_main_thread` should check both the queue and the event:
      ```python
      # Inside the modified run_icon_on_main_thread loop
      # Assume 'app_instance' is available, holding the shutdown_event
      while not app_instance.shutdown_event.is_set():
          try:
              message = update_queue.get(block=True, timeout=0.1)
              # Process queue messages (set_state, update_menu)
              if message['action'] == 'shutdown': # Message from _exit_app via menu
                   app_instance.shutdown_event.set() # Ensure event is set too
                   break # Exit loop immediately
              # ... other actions
          except queue.Empty:
              pass # No message, loop continues
          # Check event again after timeout or processing
          if app_instance.shutdown_event.is_set():
               break
      # Loop exited, stop the icon
      logger.info("Shutdown detected in icon loop. Stopping icon.")
      icon_instance.stop()
      ```
    - **Without Explicit Queue:** If relying on `pystray`'s default `run()`, injecting the `shutdown_event` check is harder. The signal handler setting the event might work if `pystray` internally checks for signals or if the signal interrupts its blocking call, but it's less reliable. Calling `icon_instance.stop()` _from the signal handler_ is generally unsafe. _Revised Approach:_ The signal handler sets the event. `_exit_app` sets the event. The main responsibility falls on `App.run` _after_ `run_icon_on_main_thread` returns.

6.  **Modify Listener Threads (`app.py`):**

    - Ensure the `run` methods of `KeyListener` and `DoubleKeyListener` check the shutdown event. `pynput` listeners (`listener.join()`) might block. We might need to run `listener.start()` and then have the main thread `join()` them with a timeout or use a different structure where the listener loop checks the event.
    - **Simpler Approach:** Rely on `daemon=True`. When the main thread exits (after the icon loop finishes and `App.run` completes), daemon threads are terminated automatically. The key is ensuring `_cleanup_resources` runs _before_ the main thread exits.

7.  **Modify `App.run` (`app.py`):**

    - Structure it like this:
      ```python
      def run(self):
          self.exit_requested = False # Or use self.shutdown_event.is_set()
          try:
              # Register signal handlers
              # Start status icon instance
              # Start listener threads (daemon=True)
              # Run icon loop (blocking)
              # ---- Code here runs AFTER icon loop exits ----
              logger.info("Icon loop finished or interrupted.")
          except Exception as e:
              logger.error(f"Critical application error: {str(e)}", exc_info=True)
              self.shutdown_event.set() # Ensure cleanup happens on error too
          finally:
              logger.info("Entering final cleanup phase.")
              # Explicitly call cleanup AFTER the icon loop is done.
              self._cleanup_resources()
              logger.info("Application finished.")
      ```
    - Ensure `_cleanup_resources` correctly stops/cancels any remaining operations (like timers, recorder stream if somehow stuck).

8.  **Modify `run.sh`:**
    - Remove the check for the `/tmp/dictation_user_exit` marker file. The service manager (systemd/launchd) or manual execution will handle restarts.

**Rationale:** This uses standard process signaling (`SIGINT`, `SIGTERM`) for termination requests. It centralizes the shutdown trigger via `shutdown_event`, allowing different parts of the application (menu, signal handler) to initiate shutdown. It aims to have the main thread coordinate the shutdown and cleanup _after_ the blocking UI loop finishes, rather than forcefully exiting with `os._exit`.

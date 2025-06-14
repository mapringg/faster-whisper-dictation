## Relevant Files

- `setup.sh` - To add the Wayland session check and dependency installation instructions.
- `src/services/keyboard_controller_factory.py` - To remove the X11 controller and logic.
- `src/services/input_handler.py` - To replace `xsel` with `wl-clipboard` for pasting text.
- `README.md` - To update setup and usage instructions for the new Wayland-only implementation.

## Tasks

- [ ] 1.0 Update `setup.sh` for Wayland-only Environment
  - [ ] 1.1 Add a check to verify the session is Wayland using `XDG_SESSION_TYPE`.
  - [ ] 1.2 If the session is not Wayland, exit the script with a clear error message.
  - [ ] 1.3 Add checks or instructions for installing `wl-clipboard` and `ydotool`.
- [ ] 2.0 Integrate `wl-clipboard` for Clipboard Operations
  - [ ] 2.1 Modify the text pasting mechanism in `src/services/input_handler.py` to use `wl-copy` to send text to the clipboard.
  - [ ] 2.2 Ensure the transcribed text is correctly retrieved from the clipboard using `wl-paste`.
- [ ] 3.0 Implement `ydotool` for Global Hotkey Listening
  - [ ] 3.1 The application will be triggered via a user-defined script that calls the main application. The user is responsible for binding this script to a hotkey in their desktop environment.
- [ ] 4.0 Remove Legacy X11 Implementation
  - [ ] 4.1 Remove all code related to `xsel` from the application.
  - [ ] 4.2 Remove any X11-specific logic from the `keyboard_controller_factory.py` and other relevant files.
  - [ ] 4.3 Remove `xsel` from any dependency lists or setup instructions.
- [ ] 5.0 Update Project Documentation
  - [ ] 5.1 Update `README.md` to reflect the Wayland-only support for Linux.
  - [ ] 5.2 Add clear instructions on the new dependencies (`wl-clipboard`, `ydotool`).
  - [ ] 5.3 Document that the user is now responsible for creating their own global keybinding.

# PRD: Linux Wayland Support Migration

## 1. Introduction/Overview

This document outlines the requirements for migrating the application's Linux support from the X11 display server protocol to Wayland. The current implementation relies on X11-specific tools (`xsel`), which do not function in a Wayland environment. The primary goal is to provide a fully functional and native experience for users on modern Linux distributions that use Wayland, as the user is moving to a Wayland-only setup. This migration involves replacing X11-dependent components with Wayland-native alternatives and removing the now-obsolete X11 implementation.

## 2. Goals

*   Enable full application functionality on Linux systems running Wayland.
*   Replace the X11-specific dependency `xsel` with the Wayland-compatible `wl-clipboard`.
*   Utilize `ydotool` for global keyboard input listening.
*   Completely remove the existing X11 implementation to avoid maintenance overhead and confusion.
*   Ensure the setup process is robust and prevents installation on unsupported display servers (i.e., non-Wayland systems).

## 3. User Stories

*   **As a Linux user on a Wayland desktop**, I want to be able to trigger the dictation service with a keybinding so that I can transcribe my speech into text seamlessly.
*   **As a Linux user on Wayland**, I want the transcribed text to be automatically pasted into my active window so that I can use it immediately without manual copy-pasting.
*   **As a developer/user setting up the application**, I want the setup script to verify that I am running Wayland and provide a clear error message if I am not, so that I don't proceed with an incompatible installation.

## 4. Functional Requirements

1.  The system **must** use `wl-clipboard` to copy and paste text on Linux.
2.  The system **must** rely on `ydotool` (which generally requires uinput/root access) for listening to the user-defined global hotkey for starting and stopping dictation.  Installation instructions **must** cover the required permissions (e.g., `sudo setcap 'cap_uinput,cap_dac_read_search,cap_sys_nice+eip' $(which ydotool)`).
3.  The `setup.sh` script **must** check if the current session is a Wayland session.
4.  If the session is **not** Wayland, the `setup.sh` script **must** fail and output an error message informing the user that only Wayland is supported.
5.  The core application logic (start recording, stop recording, transcribe, paste) **must** function identically to the previous X11 implementation from a user's perspective.
6.  All code, dependencies, and documentation related to the X11 implementation (e.g., `xsel`) **must** be removed from the codebase.
7.  The documentation (`README.md` or a new setup guide) **must** be updated to reflect the new Wayland-only setup process for Linux, including the dependencies (`wl-clipboard`, `ydotool`) and the requirement for the user to configure their own keybinding.

## 5. Non-Goals (Out of Scope)

*   This feature will **not** support X11 or provide a fallback mechanism. The Linux implementation will be Wayland-only.
*   This feature will **not** automatically configure the system-wide keybinding for the user. The user is responsible for setting this up in their desktop environment.
*   No changes will be made to the existing macOS implementation.

## 6. Design Considerations (Optional)

*   N/A. The user-facing interface and experience remain unchanged.

## 7. Technical Considerations (Optional)

*   The application needs a reliable way to detect the display server type. This can typically be done by checking the `XDG_SESSION_TYPE` environment variable.
*   Dependencies: The setup script must ensure `wl-clipboard` and `ydotool` are installed on the user's system or provide instructions for the user to install them.

## 8. Success Metrics

*   The application successfully captures audio, transcribes it, and pastes the text on a fresh installation of a Wayland-based Linux distribution (e.g., Fedora, Ubuntu 24.04+ on Wayland).
*   The `setup.sh` script correctly identifies and blocks installation on an X11 session.
*   The updated documentation is clear enough for a new user to successfully set up the application on a Wayland system.

## 9. Open Questions

*   None at this time.

# Changelog

## v1.2.0

### Features
- Add double-click to connect setting (configurable in Preferences)
- Add session description field with multi-line textarea and Pango markup support
- Add hover popover to show session description with rich text rendering
- Add OS type per session (Windows, Ubuntu, Fedora, etc.) with colored badge
- Description field is searchable via the session filter

### UI
- Add bottom margin to session list
- Add "Behavior" section in Preferences

## v1.1.0

### Features
- Add SSH key unlock on startup with built-in passphrase dialog
- Add per-session terminal profile setting
- Add dark, light, and auto theme modes with toggle button in header bar
- Add collapsible session groups with persistent state
- Add PuTTY `.reg` file import
- Add session search/filter

### Fixes
- Fix SSH passphrase prompt not appearing on GNOME desktops
- Fix launch crash when startup notify ID is None on Wayland
- Fix launch crash and bring terminal to front via minimize/restore
- Fix notification spam caused by `--wait` and minimize/restore
- Suppress gnome-terminal 'ready' notification
- Remove blue background from group headers
- Remove header bar gradient for neutral look

## v1.0.0

- Initial release: PuTTY-like SSH/Telnet session manager for Linux
- Single-pane session list UI with colorful styling
- Session management (create, edit, delete, launch)
- Port forwarding support (local, remote, dynamic)
- Terminal emulator auto-detection

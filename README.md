# LiTTY

A PuTTY-like SSH/Telnet session manager for Linux, built with GTK4 and libadwaita.

## Features

- **Session management** - Create, edit, delete, and launch SSH/Telnet sessions
- **Session groups** - Organize sessions into collapsible groups
- **Search/filter** - Quickly find sessions by name
- **PuTTY import** - Import sessions from PuTTY `.reg` export files
- **Port forwarding** - Local (-L), remote (-R), and dynamic (-D) SSH tunnels
- **Terminal profiles** - Assign terminal emulator profiles per session
- **SSH key unlock** - Optionally prompt for your SSH key passphrase on startup
- **Themes** - Dark, light, and auto theme modes

## Supported Terminal Emulators

gnome-terminal, konsole, xfce4-terminal, kitty, alacritty, wezterm, xterm

LiTTY auto-detects your installed terminal emulator on first launch.

## Dependencies

- Python 3
- GTK 4
- libadwaita 1
- PyGObject (`gi`)

### Install on Ubuntu/Debian

```bash
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

### Install on Fedora

```bash
sudo dnf install python3 python3-gobject gtk4 libadwaita
```

### Install on Arch

```bash
sudo pacman -S python python-gobject gtk4 libadwaita
```

## Usage

```bash
python3 litty.py
```

Or install the desktop file to launch from your application menu:

```bash
cp data/com.github.litty.desktop ~/.local/share/applications/
cp data/litty.svg ~/.local/share/icons/hicolor/scalable/apps/
update-desktop-database ~/.local/share/applications/
```

## Configuration

Sessions and settings are stored in `~/.config/litty/sessions.json`.

## Importing PuTTY Sessions

1. On Windows, export your PuTTY sessions: `regedit /e putty.reg "HKEY_CURRENT_USER\Software\SimonTatham\PuTTY\Sessions"`
2. In LiTTY, go to the menu and select **Import .reg file**
3. Select your exported `.reg` file

An example `.reg` file is included in the `example/` directory.

## License

MIT

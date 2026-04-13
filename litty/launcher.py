from __future__ import annotations

import shlex
import shutil
import subprocess

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio

from .models import Session


def build_ssh_command(session: Session) -> list[str]:
    cmd = ["ssh"]

    if session.port != 22:
        cmd.extend(["-p", str(session.port)])

    for fwd in session.port_forwardings:
        if fwd.direction == "D":
            cmd.extend(["-D", str(fwd.listen_port)])
        elif fwd.direction in ("L", "R"):
            cmd.extend([f"-{fwd.direction}", f"{fwd.listen_port}:{fwd.destination}"])

    target = f"{session.username}@{session.hostname}" if session.username else session.hostname
    cmd.append(target)
    return cmd


def build_telnet_command(session: Session) -> list[str]:
    cmd = ["telnet", session.hostname]
    if session.port != 23:
        cmd.append(str(session.port))
    return cmd


def build_command(session: Session) -> list[str]:
    if session.protocol == "telnet":
        return build_telnet_command(session)
    return build_ssh_command(session)


def launch_session(session: Session, terminal: str = "gnome-terminal") -> None:
    cmd = build_command(session)

    # Terminal-specific argument formats
    terminal_base = terminal.split("/")[-1].split()[0]  # handle full paths

    if terminal_base == "gnome-terminal":
        title = session.display_name
        argv = [terminal, "--title", title, "--wait"]
        if session.terminal_profile:
            argv.extend(["--profile", session.terminal_profile])
        argv.extend(["--", *cmd])
    elif terminal_base in ("konsole",):
        argv = [terminal]
        if session.terminal_profile:
            argv.extend(["--profile", session.terminal_profile])
        argv.extend(["-e", *cmd])
    elif terminal_base in ("xfce4-terminal", "xterm"):
        argv = [terminal, "-e", shlex.join(cmd)]
    elif terminal_base in ("alacritty", "kitty"):
        argv = [terminal, "-e", *cmd]
    elif terminal_base == "wezterm":
        argv = [terminal, "start", "--", *cmd]
    else:
        # Generic fallback
        argv = [terminal, "-e", *cmd]

    display = Gdk.Display.get_default()
    context = display.get_app_launch_context()
    launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.NONE)
    launcher.setenv("DESKTOP_STARTUP_ID", context.get_startup_notify_id(None, []), True)
    launcher.spawnv(argv)


def detect_terminal() -> str:
    """Try to find an available terminal emulator."""
    preferred = [
        "gnome-terminal", "konsole", "xfce4-terminal",
        "kitty", "alacritty", "wezterm", "xterm",
    ]
    for term in preferred:
        if shutil.which(term):
            return term
    return "xterm"

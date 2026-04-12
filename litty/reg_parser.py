from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from .models import PortForward, Session


def parse_reg_file(path: str | Path) -> list[Session]:
    """Parse a PuTTY .reg export file and return Session objects."""
    raw = Path(path).read_bytes()

    # Try UTF-16 first (handles BOM), fall back to UTF-8
    try:
        text = raw.decode("utf-16")
    except (UnicodeDecodeError, UnicodeError):
        text = raw.decode("utf-8-sig")

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split into session blocks
    session_pattern = re.compile(
        r"\[HKEY_CURRENT_USER\\Software\\SimonTatham\\PuTTY\\Sessions\\([^\]]+)\]"
    )

    sessions: list[Session] = []
    matches = list(session_pattern.finditer(text))

    for i, match in enumerate(matches):
        raw_name = unquote(match.group(1))

        # Skip Default Settings
        if raw_name.lower() == "default settings":
            continue

        # Extract the block of key-value pairs until the next section
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]

        props = _parse_block(block)

        hostname = props.get("HostName", "")
        if not hostname:
            continue

        protocol = props.get("Protocol", "ssh").lower()
        port = _parse_dword(props.get("PortNumber", ""), default=22 if protocol == "ssh" else 23)
        username = props.get("UserName", "")
        port_forwardings = _parse_port_forwardings(props.get("PortForwardings", ""))

        # Derive group and display name
        if " | " in raw_name:
            group, name = raw_name.split(" | ", 1)
        else:
            group, name = "", raw_name

        sessions.append(Session(
            name=name.strip(),
            hostname=hostname,
            group=group.strip(),
            port=port,
            protocol=protocol,
            username=username,
            port_forwardings=port_forwardings,
        ))

    return sessions


def _parse_block(block: str) -> dict[str, str]:
    """Extract key-value pairs from a .reg file block."""
    props: dict[str, str] = {}
    for line in block.split("\n"):
        line = line.strip()
        if line.startswith("["):
            break
        if not line:
            continue
        # Match "Key"="value" or "Key"=dword:XXXXXXXX
        m = re.match(r'^"([^"]+)"=(.+)$', line)
        if not m:
            continue
        key = m.group(1)
        value = m.group(2)
        # Store raw value — caller decides how to interpret
        if value.startswith('"') and value.endswith('"'):
            props[key] = value[1:-1]
        else:
            props[key] = value
    return props


def _parse_dword(value: str, default: int = 0) -> int:
    """Parse a dword:XXXXXXXX value to int."""
    if value.startswith("dword:"):
        try:
            return int(value[6:], 16)
        except ValueError:
            return default
    return default


def _parse_port_forwardings(value: str) -> list[PortForward]:
    """Parse PuTTY port forwarding string like 'L2121=192.168.1.1:22,L8446=10.35.200.151:443'."""
    if not value:
        return []

    forwards: list[PortForward] = []
    for entry in value.split(","):
        entry = entry.strip()
        if not entry or len(entry) < 2:
            continue
        direction = entry[0].upper()
        if direction not in ("L", "R", "D"):
            continue
        rest = entry[1:]
        if "=" in rest:
            listen_str, _, destination = rest.partition("=")
        else:
            listen_str, destination = rest, ""
        try:
            listen_port = int(listen_str)
        except ValueError:
            continue
        forwards.append(PortForward(direction, listen_port, destination))

    return forwards

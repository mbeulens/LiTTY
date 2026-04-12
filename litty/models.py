from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class PortForward:
    direction: str  # "L" (local), "R" (remote), "D" (dynamic)
    listen_port: int
    destination: str = ""  # "host:port" or empty for dynamic

    def to_ssh_arg(self) -> str:
        if self.direction == "D":
            return f"-D {self.listen_port}"
        flag = f"-{self.direction}"
        return f"{flag} {self.listen_port}:{self.destination}"


@dataclass
class Session:
    name: str
    hostname: str
    group: str = ""
    port: int = 22
    protocol: str = "ssh"
    username: str = ""
    port_forwardings: list[PortForward] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def display_name(self) -> str:
        return self.name or self.hostname


@dataclass
class AppConfig:
    terminal: str = "gnome-terminal"
    sessions: list[Session] = field(default_factory=list)


def config_dir() -> Path:
    path = Path.home() / ".config" / "litty"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "sessions.json"


def load_config(path: Path | None = None) -> AppConfig:
    p = path or config_path()
    if not p.exists():
        return AppConfig()
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        # Corrupt file — back up and start fresh
        backup = p.with_suffix(".json.bak")
        p.rename(backup)
        return AppConfig()

    sessions = []
    for s in data.get("sessions", []):
        fwds = [PortForward(**f) for f in s.pop("port_forwardings", [])]
        sessions.append(Session(**s, port_forwardings=fwds))

    return AppConfig(
        terminal=data.get("terminal", "gnome-terminal"),
        sessions=sessions,
    )


def save_config(config: AppConfig, path: Path | None = None) -> None:
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "terminal": config.terminal,
        "sessions": [asdict(s) for s in config.sessions],
    }
    p.write_text(json.dumps(data, indent=2))

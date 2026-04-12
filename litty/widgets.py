from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, GObject

from .models import Session


class SessionRow(Gtk.ListBoxRow):
    __gtype_name__ = "SessionRow"

    def __init__(self, session: Session):
        super().__init__()
        self.session = session

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(8)
        box.set_margin_end(8)

        name_label = Gtk.Label(label=session.display_name, xalign=0)
        name_label.add_css_class("heading")

        detail = f"{session.hostname}:{session.port}"
        if session.username:
            detail = f"{session.username}@{detail}"
        detail_label = Gtk.Label(label=detail, xalign=0)
        detail_label.add_css_class("dim-label")
        detail_label.add_css_class("caption")

        box.append(name_label)
        box.append(detail_label)
        self.set_child(box)

    def matches_filter(self, query: str) -> bool:
        q = query.lower()
        return (
            q in self.session.name.lower()
            or q in self.session.hostname.lower()
            or q in self.session.username.lower()
            or q in self.session.group.lower()
        )

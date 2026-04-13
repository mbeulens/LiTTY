from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, GObject

from .models import Session


class SessionRow(Gtk.ListBoxRow):
    __gtype_name__ = "SessionRow"

    __gsignals__ = {
        "edit-clicked": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.add_css_class("session-row")

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)
        outer.set_margin_start(12)
        outer.set_margin_end(8)

        # Protocol icon with color (clickable for description popover)
        icon_name = "network-server-symbolic" if session.protocol == "ssh" else "network-transmit-symbolic"

        icon = Gtk.Image(icon_name=icon_name)
        icon.set_pixel_size(28)
        icon.add_css_class(f"icon-{session.protocol}")
        outer.append(icon)

        if session.description:
            self._desc_popover = Gtk.Popover()
            self._desc_popover.set_parent(icon)
            label = Gtk.Label(wrap=True, max_width_chars=40, use_markup=True)
            label.set_markup(session.description)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            label.set_margin_start(8)
            label.set_margin_end(8)
            self._desc_popover.set_child(label)

            click = Gtk.GestureClick(button=1)
            click.connect("pressed", self._on_icon_clicked)
            icon.add_controller(click)

        # Session info (name + detail)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)

        name_label = Gtk.Label(label=session.display_name, xalign=0)
        name_label.add_css_class("session-name")
        name_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END

        # Detail line with connection info
        detail = f"{session.hostname}:{session.port}"
        if session.username:
            detail = f"{session.username}@{detail}"
        detail_label = Gtk.Label(label=detail, xalign=0)
        detail_label.add_css_class("dim-label")
        detail_label.add_css_class("caption")
        detail_label.add_css_class("session-detail")
        detail_label.set_ellipsize(3)

        info_box.append(name_label)
        info_box.append(detail_label)
        outer.append(info_box)

        # Badge: OS if set, otherwise protocol
        if session.os_type:
            _OS_LABELS = {
                "windows": "Windows", "ubuntu": "Ubuntu", "debian": "Debian",
                "fedora": "Fedora", "centos": "CentOS", "rhel": "RHEL",
                "arch": "Arch", "opensuse": "openSUSE", "macos": "macOS",
            }
            badge = Gtk.Label(label=_OS_LABELS.get(session.os_type, session.os_type.title()))
            badge.add_css_class("protocol-badge")
            badge.add_css_class(f"os-{session.os_type}")
            badge.set_valign(Gtk.Align.CENTER)
        else:
            badge = Gtk.Label(label=session.protocol.upper())
            badge.add_css_class("protocol-badge")
            badge.add_css_class(f"protocol-{session.protocol}")
            badge.set_valign(Gtk.Align.CENTER)
        outer.append(badge)

        # Edit button
        edit_btn = Gtk.Button(icon_name="document-edit-symbolic", valign=Gtk.Align.CENTER)
        edit_btn.add_css_class("flat")
        edit_btn.add_css_class("edit-button")
        edit_btn.set_tooltip_text("Edit session")
        edit_btn.connect("clicked", self._on_edit_clicked)
        outer.append(edit_btn)

        self.set_child(outer)

    def _on_icon_clicked(self, gesture, n_press, x, y):
        self._desc_popover.popup()

    def _on_edit_clicked(self, button):
        self.emit("edit-clicked", self.session)

    def matches_filter(self, query: str) -> bool:
        q = query.lower()
        return (
            q in self.session.name.lower()
            or q in self.session.hostname.lower()
            or q in self.session.username.lower()
            or q in self.session.group.lower()
            or q in self.session.description.lower()
        )

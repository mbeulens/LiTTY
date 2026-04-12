from __future__ import annotations

import uuid

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GObject, Gio

from .models import Session, PortForward


class SessionDialog(Adw.Dialog):
    __gtype_name__ = "SessionDialog"
    __gsignals__ = {
        "saved": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "deleted": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self, parent_window, session: Session | None = None, **kwargs):
        super().__init__(**kwargs)
        self._session = session
        self._editing = session is not None

        self.set_title("Edit Session" if self._editing else "New Session")
        self.set_content_width(450)
        self.set_content_height(500)

        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        # Header bar
        header = Adw.HeaderBar()
        header.set_show_title(True)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)

        toolbar_view.add_top_bar(header)

        # Bottom bar with delete button (only when editing)
        if self._editing:
            bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            bottom_bar.set_margin_top(12)
            bottom_bar.set_margin_bottom(12)
            bottom_bar.set_margin_start(12)
            bottom_bar.set_margin_end(12)
            delete_btn = Gtk.Button(label="Delete Session", hexpand=True)
            delete_btn.add_css_class("destructive-action")
            delete_btn.add_css_class("pill")
            delete_btn.connect("clicked", self._on_delete)
            bottom_bar.append(delete_btn)
            toolbar_view.add_bottom_bar(bottom_bar)

        # Content
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        page = Adw.PreferencesPage()
        scrolled.set_child(page)
        toolbar_view.set_content(scrolled)

        # Connection group
        conn_group = Adw.PreferencesGroup(title="Connection")
        page.add(conn_group)

        self._name_row = Adw.EntryRow(title="Session Name")
        conn_group.add(self._name_row)

        self._group_row = Adw.EntryRow(title="Group")
        conn_group.add(self._group_row)

        self._hostname_row = Adw.EntryRow(title="Hostname")
        conn_group.add(self._hostname_row)

        self._username_row = Adw.EntryRow(title="Username")
        conn_group.add(self._username_row)

        # Protocol combo
        self._protocol_row = Adw.ComboRow(title="Protocol")
        protocol_model = Gtk.StringList.new(["SSH", "Telnet"])
        self._protocol_row.set_model(protocol_model)
        self._protocol_row.connect("notify::selected", self._on_protocol_changed)
        conn_group.add(self._protocol_row)

        # Port
        port_adj = Gtk.Adjustment(lower=1, upper=65535, step_increment=1, page_increment=10)
        self._port_row = Adw.SpinRow(title="Port", adjustment=port_adj)
        conn_group.add(self._port_row)

        # Port forwardings
        fwd_group = Adw.PreferencesGroup(title="Port Forwardings")
        fwd_group.set_description("Format: L8080=localhost:80 (Local), R9090=host:90 (Remote), D1080 (Dynamic)")
        page.add(fwd_group)

        self._fwd_entry = Adw.EntryRow(title="Forwardings (comma-separated)")
        fwd_group.add(self._fwd_entry)

        # Populate if editing
        if session:
            self._name_row.set_text(session.name)
            self._group_row.set_text(session.group)
            self._hostname_row.set_text(session.hostname)
            self._username_row.set_text(session.username)
            self._protocol_row.set_selected(0 if session.protocol == "ssh" else 1)
            self._port_row.set_value(session.port)
            if session.port_forwardings:
                fwd_str = ",".join(
                    f"{f.direction}{f.listen_port}={f.destination}" if f.destination
                    else f"{f.direction}{f.listen_port}"
                    for f in session.port_forwardings
                )
                self._fwd_entry.set_text(fwd_str)
        else:
            self._port_row.set_value(22)

    def _on_protocol_changed(self, row, _pspec):
        selected = row.get_selected()
        current_port = int(self._port_row.get_value())
        # Auto-switch port if it's still the default
        if selected == 0 and current_port == 23:
            self._port_row.set_value(22)
        elif selected == 1 and current_port == 22:
            self._port_row.set_value(23)

    def _on_save(self, button):
        hostname = self._hostname_row.get_text().strip()
        if not hostname:
            self._hostname_row.add_css_class("error")
            return

        name = self._name_row.get_text().strip() or hostname
        group = self._group_row.get_text().strip()
        username = self._username_row.get_text().strip()
        protocol = "ssh" if self._protocol_row.get_selected() == 0 else "telnet"
        port = int(self._port_row.get_value())

        # Parse port forwardings
        fwd_text = self._fwd_entry.get_text().strip()
        port_forwardings = self._parse_forwardings(fwd_text)

        session = Session(
            id=self._session.id if self._editing else str(uuid.uuid4()),
            name=name,
            group=group,
            hostname=hostname,
            port=port,
            protocol=protocol,
            username=username,
            port_forwardings=port_forwardings,
        )

        self.emit("saved", session)
        self.close()

    def _on_delete(self, button):
        parent = self
        dialog = Adw.AlertDialog(
            heading="Delete Session?",
            body=f"Are you sure you want to delete \"{self._session.display_name}\"?",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_confirmed)
        dialog.present(self)

    def _on_delete_confirmed(self, dialog, response):
        if response == "delete":
            self.emit("deleted", self._session)
            self.close()

    def _parse_forwardings(self, text: str) -> list[PortForward]:
        if not text:
            return []
        forwards = []
        for entry in text.split(","):
            entry = entry.strip()
            if not entry or len(entry) < 2:
                continue
            direction = entry[0].upper()
            if direction not in ("L", "R", "D"):
                continue
            rest = entry[1:]
            if "=" in rest:
                listen_str, _, dest = rest.partition("=")
            else:
                listen_str, dest = rest, ""
            try:
                listen_port = int(listen_str)
            except ValueError:
                continue
            forwards.append(PortForward(direction, listen_port, dest))
        return forwards


class PreferencesDialog(Adw.Dialog):
    __gtype_name__ = "PreferencesDialog"
    __gsignals__ = {
        "terminal-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "theme-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    _THEME_OPTIONS = ["Auto", "Light", "Dark"]

    def __init__(self, current_terminal: str = "gnome-terminal", current_theme: str = "auto", **kwargs):
        super().__init__(**kwargs)
        self._initial_theme = current_theme

        self.set_title("Preferences")
        self.set_content_width(400)
        self.set_content_height(400)

        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        page = Adw.PreferencesPage()
        toolbar_view.set_content(page)

        # Appearance group
        appearance_group = Adw.PreferencesGroup(title="Appearance")
        page.add(appearance_group)

        self._theme_row = Adw.ComboRow(title="Theme")
        theme_model = Gtk.StringList.new(self._THEME_OPTIONS)
        self._theme_row.set_model(theme_model)
        theme_index = {"auto": 0, "light": 1, "dark": 2}.get(current_theme, 0)
        self._theme_row.set_selected(theme_index)
        appearance_group.add(self._theme_row)

        # Terminal group
        group = Adw.PreferencesGroup(title="Terminal")
        page.add(group)

        self._terminal_row = Adw.EntryRow(title="Terminal command")
        self._terminal_row.set_text(current_terminal)
        group.add(self._terminal_row)

        terminals = ["gnome-terminal", "konsole", "xfce4-terminal", "kitty", "alacritty", "wezterm", "xterm"]
        presets_group = Adw.PreferencesGroup(title="Quick Select")
        page.add(presets_group)

        for term in terminals:
            row = Adw.ActionRow(title=term, activatable=True)
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", self._on_preset_selected, term)
            presets_group.add(row)

        self.connect("closed", self._on_closed)

    def _on_preset_selected(self, row, term):
        self._terminal_row.set_text(term)

    def _on_closed(self, dialog):
        terminal = self._terminal_row.get_text().strip()
        if terminal:
            self.emit("terminal-changed", terminal)

        theme = self._THEME_OPTIONS[self._theme_row.get_selected()].lower()
        if theme != self._initial_theme:
            self.emit("theme-changed", theme)

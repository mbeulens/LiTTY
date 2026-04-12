from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, Gdk, Gio, GLib

from pathlib import Path

from . import __version__, __app_id__
from .models import AppConfig, load_config, save_config
from .launcher import detect_terminal
from .window import LittyWindow


class LittyApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.config: AppConfig | None = None
        self.win: LittyWindow | None = None

    def do_startup(self):
        Adw.Application.do_startup(self)

        # Load custom CSS
        css_provider = Gtk.CssProvider()
        css_path = Path(__file__).parent.parent / "data" / "style.css"
        css_provider.load_from_path(str(css_path))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.config = load_config()

        # Auto-detect terminal if not configured
        if not self.config.terminal:
            self.config.terminal = detect_terminal()
            save_config(self.config)

        self._setup_actions()

    def do_activate(self):
        if not self.win:
            self.win = LittyWindow(config=self.config, application=self)
        self.win.present()

    def _setup_actions(self):
        actions = [
            ("import-reg", self._on_import_reg),
            ("preferences", self._on_preferences),
            ("about", self._on_about),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    def _on_import_reg(self, action, param):
        dialog = Gtk.FileDialog()
        dialog.set_title("Import PuTTY Sessions")

        filter_reg = Gtk.FileFilter()
        filter_reg.set_name("Registry files (*.reg)")
        filter_reg.add_pattern("*.reg")

        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_reg)
        filters.append(filter_all)
        dialog.set_filters(filters)

        dialog.open(self.win, None, self._on_import_file_chosen)

    def _on_import_file_chosen(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return  # User cancelled

        path = file.get_path()
        if not path:
            return

        from .reg_parser import parse_reg_file

        try:
            sessions = parse_reg_file(path)
        except Exception as e:
            self.win.show_toast(f"Failed to parse file: {e}")
            return

        if not sessions:
            self.win.show_toast("No sessions found in file")
            return

        added, skipped = self.win.add_imported_sessions(sessions)
        msg = f"Imported {added} session(s)"
        if skipped:
            msg += f", {skipped} duplicate(s) skipped"
        self.win.show_toast(msg)

    def _on_preferences(self, action, param):
        from .dialogs import PreferencesDialog

        dialog = PreferencesDialog(current_terminal=self.config.terminal)
        dialog.connect("terminal-changed", self._on_terminal_changed)
        dialog.present(self.win)

    def _on_terminal_changed(self, dialog, terminal):
        self.config.terminal = terminal
        save_config(self.config)
        self.win.show_toast(f"Terminal set to: {terminal}")

    def _on_about(self, action, param):
        about = Adw.AboutDialog(
            application_name="LiTTY",
            application_icon="litty",
            developer_name="LiTTY",
            version=__version__,
            comments="A PuTTY-like SSH/Telnet session manager for Linux",
            license_type=Gtk.License.MIT_X11,
        )
        about.present(self.win)

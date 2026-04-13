from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, Gdk, Gio, GLib

import subprocess
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

        self._apply_theme(self.config.theme)
        self._setup_actions()

    def do_activate(self):
        if not self.win:
            self.win = LittyWindow(config=self.config, application=self)
            if self.config.ssh_unlock_on_start:
                self._try_ssh_unlock()
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

    def _try_ssh_unlock(self):
        """Prompt for SSH key passphrase if no keys are loaded in the agent."""
        try:
            result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return  # Keys already loaded
        except FileNotFoundError:
            return  # ssh-add not available

        self._show_passphrase_dialog()

    def _show_passphrase_dialog(self):
        """Show an Adw dialog to collect the SSH key passphrase."""
        dialog = Adw.AlertDialog(
            heading="Unlock SSH Key",
            body="Enter your SSH key passphrase to load your key into the agent.",
        )
        entry = Gtk.PasswordEntry(show_peek_icon=True)
        entry.set_size_request(300, -1)
        entry.add_css_class("card")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("unlock", "Unlock")
        dialog.set_response_appearance("unlock", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("unlock")
        dialog.set_close_response("cancel")
        entry.connect("activate", lambda e: dialog.response("unlock"))
        dialog.choose(self.win, None, self._on_passphrase_response, entry)

    def _on_passphrase_response(self, dialog, result, entry):
        response = dialog.choose_finish(result)
        if response != "unlock":
            return
        passphrase = entry.get_text()
        if not passphrase:
            return
        try:
            proc = subprocess.run(
                ["ssh-add"],
                input=passphrase + "\n",
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                self.win.show_toast("SSH key unlocked")
            else:
                self.win.show_toast("Failed to unlock SSH key")
        except FileNotFoundError:
            self.win.show_toast("ssh-add not found")

    def _apply_theme(self, theme: str):
        style_manager = Adw.StyleManager.get_default()
        schemes = {
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
            "auto": Adw.ColorScheme.DEFAULT,
        }
        style_manager.set_color_scheme(schemes.get(theme, Adw.ColorScheme.DEFAULT))

    def _on_preferences(self, action, param):
        from .dialogs import PreferencesDialog

        dialog = PreferencesDialog(
            current_terminal=self.config.terminal,
            current_theme=self.config.theme,
            ssh_unlock_on_start=self.config.ssh_unlock_on_start,
        )
        dialog.connect("terminal-changed", self._on_terminal_changed)
        dialog.connect("theme-changed", self._on_theme_changed)
        dialog.connect("ssh-unlock-changed", self._on_ssh_unlock_changed)
        dialog.present(self.win)

    def _on_terminal_changed(self, dialog, terminal):
        self.config.terminal = terminal
        save_config(self.config)
        self.win.show_toast(f"Terminal set to: {terminal}")

    def _on_theme_changed(self, dialog, theme):
        self.config.theme = theme
        self._apply_theme(theme)
        save_config(self.config)

    def _on_ssh_unlock_changed(self, dialog, enabled):
        self.config.ssh_unlock_on_start = enabled
        save_config(self.config)

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

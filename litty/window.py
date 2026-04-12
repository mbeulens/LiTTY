from __future__ import annotations

from collections import defaultdict

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, Gio, GLib

from . import __version__
from .models import AppConfig, Session, save_config
from .launcher import launch_session
from .widgets import SessionRow


class LittyWindow(Adw.ApplicationWindow):
    def __init__(self, config: AppConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self._filter_query = ""

        self.set_title(f"LiTTY v{__version__}")
        self.set_default_size(550, 650)

        # Toast overlay wraps everything
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # Main toolbar view
        toolbar_view = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar_view)

        # ── Header bar ───────────────────────────────────────
        header = Adw.HeaderBar()

        header.add_css_class("litty-header")

        new_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="New Session")
        new_btn.add_css_class("new-session-btn")
        new_btn.connect("clicked", self._on_new_session)
        header.pack_start(new_btn)

        self._search_toggle = Gtk.ToggleButton(icon_name="system-search-symbolic")
        self._search_toggle.connect("toggled", self._on_search_toggled)
        header.pack_end(self._search_toggle)

        # Menu
        menu = Gio.Menu()
        menu.append("Import PuTTY Sessions...", "app.import-reg")
        menu.append("Preferences", "app.preferences")
        menu.append("About LiTTY", "app.about")

        menu_btn = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=menu,
            primary=True,
        )
        header.pack_end(menu_btn)

        toolbar_view.add_top_bar(header)

        # ── Search bar ───────────────────────────────────────
        self._search_entry = Gtk.SearchEntry(placeholder_text="Filter sessions...")
        self._search_entry.connect("search-changed", self._on_search_changed)

        self._search_bar = Gtk.SearchBar()
        self._search_bar.set_child(self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        toolbar_view.add_top_bar(self._search_bar)

        # ── Content: stack for empty state vs session list ───
        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        toolbar_view.set_content(self._content_stack)

        # Empty state
        empty = Adw.StatusPage(
            title="No Sessions",
            description="Add a session or import from PuTTY",
            icon_name="litty",
        )
        self._content_stack.add_named(empty, "empty")

        # Session list
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        clamp = Adw.Clamp(maximum_size=600)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.add_css_class("boxed-list")
        self._listbox.connect("row-activated", self._on_row_activated)

        clamp.set_child(self._listbox)
        scrolled.set_child(clamp)
        self._content_stack.add_named(scrolled, "list")

        # Populate
        self._populate_list()

    # ── List population ──────────────────────────────────────

    def _populate_list(self):
        while True:
            child = self._listbox.get_first_child()
            if child is None:
                break
            self._listbox.remove(child)

        if not self.config.sessions:
            self._content_stack.set_visible_child_name("empty")
            return

        self._content_stack.set_visible_child_name("list")

        groups: dict[str, list[Session]] = defaultdict(list)
        for session in self.config.sessions:
            groups[session.group or "Ungrouped"].append(session)

        for group_name in sorted(groups.keys()):
            # Group header with color
            header_row = Gtk.ListBoxRow(selectable=False, activatable=False)
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            header_box.add_css_class("group-header-bar")
            header_box.set_margin_top(8)
            header_box.set_margin_bottom(2)

            group_icon = Gtk.Image(icon_name="folder-symbolic")
            group_icon.add_css_class("group-header")
            header_box.append(group_icon)

            header_label = Gtk.Label(label=group_name, xalign=0)
            header_label.add_css_class("group-header")
            header_box.append(header_label)

            count_label = Gtk.Label(label=str(len(groups[group_name])))
            count_label.add_css_class("dim-label")
            count_label.add_css_class("caption")
            count_label.set_hexpand(True)
            count_label.set_halign(Gtk.Align.END)
            header_box.append(count_label)

            header_row.set_child(header_box)
            self._listbox.append(header_row)

            for session in sorted(groups[group_name], key=lambda s: s.name.lower()):
                row = SessionRow(session)
                row.connect("edit-clicked", self._on_edit_clicked)
                self._listbox.append(row)

        self._listbox.set_filter_func(self._filter_func)

    def _filter_func(self, row: Gtk.ListBoxRow) -> bool:
        if not self._filter_query:
            return True
        if isinstance(row, SessionRow):
            return row.matches_filter(self._filter_query)
        return True

    # ── Signal handlers ──────────────────────────────────────

    def _on_row_activated(self, listbox, row):
        if isinstance(row, SessionRow):
            self._do_connect(row.session)

    def _do_connect(self, session: Session):
        try:
            launch_session(session, self.config.terminal)
            self.show_toast(f"Connecting to {session.display_name}...")
        except Exception as e:
            self.show_toast(f"Failed to connect: {e}")

    def _on_new_session(self, button):
        from .dialogs import SessionDialog
        dialog = SessionDialog(self)
        dialog.connect("saved", self._on_session_saved)
        dialog.present(self)

    def _on_edit_clicked(self, row, session):
        from .dialogs import SessionDialog
        dialog = SessionDialog(self, session=session)
        dialog.connect("saved", self._on_session_saved)
        dialog.connect("deleted", self._on_session_deleted)
        dialog.present(self)

    def _on_session_deleted(self, dialog, session):
        self.config.sessions = [s for s in self.config.sessions if s.id != session.id]
        save_config(self.config)
        self._populate_list()
        self.show_toast(f"Deleted {session.display_name}")

    def _on_session_saved(self, dialog, session):
        existing = next((s for s in self.config.sessions if s.id == session.id), None)
        if existing:
            idx = self.config.sessions.index(existing)
            self.config.sessions[idx] = session
        else:
            self.config.sessions.append(session)
        save_config(self.config)
        self._populate_list()

    def _on_search_toggled(self, button):
        active = button.get_active()
        self._search_bar.set_search_mode(active)
        if not active:
            self._search_entry.set_text("")
            self._filter_query = ""
            self._listbox.invalidate_filter()

    def _on_search_changed(self, entry):
        self._filter_query = entry.get_text()
        self._listbox.invalidate_filter()

    def show_toast(self, message: str):
        toast = Adw.Toast(title=message)
        self.toast_overlay.add_toast(toast)

    def add_imported_sessions(self, sessions: list[Session]):
        """Add imported sessions, skipping duplicates."""
        existing_keys = {
            (s.hostname, s.port, s.username, s.group, s.name)
            for s in self.config.sessions
        }
        added = 0
        for session in sessions:
            key = (session.hostname, session.port, session.username, session.group, session.name)
            if key not in existing_keys:
                self.config.sessions.append(session)
                existing_keys.add(key)
                added += 1

        if added:
            save_config(self.config)
            self._populate_list()

        return added, len(sessions) - added

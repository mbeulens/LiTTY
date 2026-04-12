from __future__ import annotations

from collections import defaultdict

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, Gio, GLib

from .models import AppConfig, Session, save_config
from .launcher import launch_session
from .widgets import SessionRow


class LittyWindow(Adw.ApplicationWindow):
    def __init__(self, config: AppConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self._selected_session: Session | None = None
        self._filter_query = ""

        self.set_title("LiTTY")
        self.set_default_size(900, 600)

        # Toast overlay wraps everything
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # Main split view
        self.split_view = Adw.NavigationSplitView()
        self.toast_overlay.set_child(self.split_view)

        # --- Sidebar ---
        self._build_sidebar()

        # --- Content pane ---
        self._build_content()

        # Populate sidebar
        self._populate_sidebar()

    # ── Sidebar ──────────────────────────────────────────────

    def _build_sidebar(self):
        sidebar_page = Adw.NavigationPage(title="Sessions")

        toolbar_view = Adw.ToolbarView()
        sidebar_page.set_child(toolbar_view)

        # Header bar with new-session button and search
        header = Adw.HeaderBar()
        header.set_show_title(True)

        new_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="New Session")
        new_btn.connect("clicked", self._on_new_session)
        header.pack_start(new_btn)

        self._search_toggle = Gtk.ToggleButton(icon_name="system-search-symbolic")
        self._search_toggle.connect("toggled", self._on_search_toggled)
        header.pack_end(self._search_toggle)

        toolbar_view.add_top_bar(header)

        # Search bar
        self._search_entry = Gtk.SearchEntry(placeholder_text="Filter sessions...")
        self._search_entry.connect("search-changed", self._on_search_changed)

        self._search_bar = Gtk.SearchBar()
        self._search_bar.set_child(self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        toolbar_view.add_top_bar(self._search_bar)

        # Session list
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        self.sidebar_listbox = Gtk.ListBox()
        self.sidebar_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar_listbox.add_css_class("navigation-sidebar")
        self.sidebar_listbox.connect("row-selected", self._on_row_selected)
        self.sidebar_listbox.connect("row-activated", self._on_row_activated)
        scrolled.set_child(self.sidebar_listbox)

        toolbar_view.set_content(scrolled)

        self.split_view.set_sidebar(sidebar_page)

    def _build_content(self):
        content_page = Adw.NavigationPage(title="Session Details")

        toolbar_view = Adw.ToolbarView()
        content_page.set_child(toolbar_view)

        # Content header
        content_header = Adw.HeaderBar()
        toolbar_view.add_top_bar(content_header)

        # Menu button
        menu = Gio.Menu()
        menu.append("Import PuTTY Sessions...", "app.import-reg")
        menu.append("Preferences", "app.preferences")
        menu.append("About LiTTY", "app.about")

        menu_btn = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=menu,
            primary=True,
        )
        content_header.pack_end(menu_btn)

        # Stack for empty state vs detail view
        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        toolbar_view.set_content(self._content_stack)

        # Empty state
        empty = Adw.StatusPage(
            title="LiTTY",
            description="Select a session or import from PuTTY",
            icon_name="litty",
        )
        self._content_stack.add_named(empty, "empty")

        # Detail view
        detail_scroll = Gtk.ScrolledWindow()
        self._detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._detail_box.set_margin_top(24)
        self._detail_box.set_margin_bottom(24)
        self._detail_box.set_margin_start(24)
        self._detail_box.set_margin_end(24)

        clamp = Adw.Clamp(maximum_size=600)
        clamp.set_child(self._detail_box)
        detail_scroll.set_child(clamp)
        self._content_stack.add_named(detail_scroll, "detail")

        # Connection info group
        self._conn_group = Adw.PreferencesGroup(title="Connection")
        self._detail_box.append(self._conn_group)

        self._row_hostname = Adw.ActionRow(title="Hostname")
        self._row_port = Adw.ActionRow(title="Port")
        self._row_protocol = Adw.ActionRow(title="Protocol")
        self._row_username = Adw.ActionRow(title="Username")
        self._conn_group.add(self._row_hostname)
        self._conn_group.add(self._row_port)
        self._conn_group.add(self._row_protocol)
        self._conn_group.add(self._row_username)

        # Port forwardings group
        self._fwd_group = Adw.PreferencesGroup(title="Port Forwardings")
        self._fwd_rows: list[Adw.ActionRow] = []
        self._detail_box.append(self._fwd_group)

        # Action buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.CENTER)
        btn_box.set_margin_top(12)

        self._connect_btn = Gtk.Button(label="Connect")
        self._connect_btn.add_css_class("suggested-action")
        self._connect_btn.add_css_class("pill")
        self._connect_btn.connect("clicked", self._on_connect)

        self._edit_btn = Gtk.Button(label="Edit")
        self._edit_btn.add_css_class("pill")
        self._edit_btn.connect("clicked", self._on_edit_session)

        self._delete_btn = Gtk.Button(label="Delete")
        self._delete_btn.add_css_class("destructive-action")
        self._delete_btn.add_css_class("pill")
        self._delete_btn.connect("clicked", self._on_delete_session)

        btn_box.append(self._connect_btn)
        btn_box.append(self._edit_btn)
        btn_box.append(self._delete_btn)
        self._detail_box.append(btn_box)

        self._content_stack.set_visible_child_name("empty")

        self.split_view.set_content(content_page)

    # ── Sidebar population ───────────────────────────────────

    def _populate_sidebar(self):
        # Remove all children
        while True:
            child = self.sidebar_listbox.get_first_child()
            if child is None:
                break
            self.sidebar_listbox.remove(child)

        groups: dict[str, list[Session]] = defaultdict(list)
        for session in self.config.sessions:
            groups[session.group or "Ungrouped"].append(session)

        for group_name in sorted(groups.keys()):
            # Group header row (not selectable)
            header_row = Gtk.ListBoxRow(selectable=False, activatable=False)
            header_label = Gtk.Label(label=group_name, xalign=0)
            header_label.add_css_class("heading")
            header_label.set_margin_top(12)
            header_label.set_margin_bottom(4)
            header_label.set_margin_start(8)
            header_row.set_child(header_label)
            self.sidebar_listbox.append(header_row)

            for session in sorted(groups[group_name], key=lambda s: s.name.lower()):
                row = SessionRow(session)
                self.sidebar_listbox.append(row)

        self.sidebar_listbox.set_filter_func(self._filter_func)

    def _filter_func(self, row: Gtk.ListBoxRow) -> bool:
        if not self._filter_query:
            return True
        if isinstance(row, SessionRow):
            return row.matches_filter(self._filter_query)
        # Group headers: show if any child session matches
        # For simplicity, always show group headers when filtering
        return True

    # ── Detail view ──────────────────────────────────────────

    def _show_session_detail(self, session: Session):
        self._selected_session = session

        self._row_hostname.set_subtitle(session.hostname)
        self._row_port.set_subtitle(str(session.port))
        self._row_protocol.set_subtitle(session.protocol.upper())
        self._row_username.set_subtitle(session.username or "(none)")

        # Clear old forwarding rows
        for row in self._fwd_rows:
            self._fwd_group.remove(row)
        self._fwd_rows.clear()

        if session.port_forwardings:
            self._fwd_group.set_visible(True)
            for fwd in session.port_forwardings:
                direction_name = {"L": "Local", "R": "Remote", "D": "Dynamic"}.get(fwd.direction, fwd.direction)
                if fwd.destination:
                    row = Adw.ActionRow(title=f"{direction_name} :{fwd.listen_port}", subtitle=fwd.destination)
                else:
                    row = Adw.ActionRow(title=f"{direction_name} :{fwd.listen_port}")
                self._fwd_group.add(row)
                self._fwd_rows.append(row)
        else:
            self._fwd_group.set_visible(False)

        self._content_stack.set_visible_child_name("detail")

    # ── Signal handlers ──────────────────────────────────────

    def _on_row_selected(self, listbox, row):
        if isinstance(row, SessionRow):
            self._show_session_detail(row.session)

    def _on_row_activated(self, listbox, row):
        if isinstance(row, SessionRow):
            self._show_session_detail(row.session)
            self._do_connect(row.session)

    def _on_connect(self, button):
        if self._selected_session:
            self._do_connect(self._selected_session)

    def _do_connect(self, session: Session):
        try:
            launch_session(session, self.config.terminal)
            toast = Adw.Toast(title=f"Connecting to {session.display_name}...")
            self.toast_overlay.add_toast(toast)
        except Exception as e:
            toast = Adw.Toast(title=f"Failed to connect: {e}")
            self.toast_overlay.add_toast(toast)

    def _on_new_session(self, button):
        from .dialogs import SessionDialog
        dialog = SessionDialog(self)
        dialog.connect("saved", self._on_session_saved)
        dialog.present(self)

    def _on_edit_session(self, button):
        if not self._selected_session:
            return
        from .dialogs import SessionDialog
        dialog = SessionDialog(self, session=self._selected_session)
        dialog.connect("saved", self._on_session_saved)
        dialog.present(self)

    def _on_delete_session(self, button):
        if not self._selected_session:
            return
        dialog = Adw.AlertDialog(
            heading="Delete Session?",
            body=f"Are you sure you want to delete \"{self._selected_session.display_name}\"?",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_response)
        dialog.present(self)

    def _on_delete_response(self, dialog, response):
        if response != "delete" or not self._selected_session:
            return
        self.config.sessions = [s for s in self.config.sessions if s.id != self._selected_session.id]
        self._selected_session = None
        save_config(self.config)
        self._populate_sidebar()
        self._content_stack.set_visible_child_name("empty")

    def _on_session_saved(self, dialog, session):
        # Update or add
        existing = next((s for s in self.config.sessions if s.id == session.id), None)
        if existing:
            idx = self.config.sessions.index(existing)
            self.config.sessions[idx] = session
        else:
            self.config.sessions.append(session)
        save_config(self.config)
        self._populate_sidebar()
        self._show_session_detail(session)

    def _on_search_toggled(self, button):
        active = button.get_active()
        self._search_bar.set_search_mode(active)
        if not active:
            self._search_entry.set_text("")
            self._filter_query = ""
            self.sidebar_listbox.invalidate_filter()

    def _on_search_changed(self, entry):
        self._filter_query = entry.get_text()
        self.sidebar_listbox.invalidate_filter()

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
            self._populate_sidebar()

        return added, len(sessions) - added

"""The user-facing libadwaita settings application."""

from __future__ import annotations

import threading

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gio, GLib, Gtk

from . import feature
from .paths import APP_ID


class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application) -> None:
        super().__init__(application=application, title="Dolphin Clean Title")
        self._busy = False
        self._status_ready = False

        header_bar = Adw.HeaderBar()

        preferences = Adw.PreferencesPage()
        preferences_group = Adw.PreferencesGroup()
        self._switch_row = Adw.SwitchRow(
            title='Remove “— Dolphin” from titles',
            subtitle="Applies to newly opened Dolphin windows",
        )
        self._switch_row.set_visible(False)
        self._switch_row.connect("notify::active", self._on_switch_changed)
        preferences_group.add(self._switch_row)

        self._report_row = Adw.ActionRow(title="Report a problem")
        self._report_row.add_suffix(
            Gtk.Image.new_from_icon_name("external-link-symbolic")
        )
        self._report_row.set_activatable(True)
        self._report_row.connect("activated", self._on_report_problem)
        preferences_group.add(self._report_row)
        preferences.add(preferences_group)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header_bar)
        toolbar_view.set_content(preferences)
        self.set_content(toolbar_view)

        self.refresh_status()

    def refresh_status(self) -> None:
        self._status_ready = False
        self._busy = True
        self._switch_row.set_visible(False)
        self._switch_row.set_sensitive(False)

        def load() -> None:
            try:
                result = (feature.status(), None)
            except feature.FeatureError as exc:
                result = (None, str(exc))
            GLib.idle_add(self._finish_status_load, result)

        threading.Thread(target=load, name="dolphin-clean-title-status", daemon=True).start()

    def _finish_status_load(
        self, result: tuple[feature.FeatureStatus | None, str | None]
    ) -> bool:
        status, error = result
        self._busy = False
        if error is not None or status is None:
            self._switch_row.set_sensitive(False)
            self._show_error(
                "Could not read Dolphin Clean Title state",
                error or "The managed feature state is unavailable.",
            )
            return GLib.SOURCE_REMOVE

        self._status_ready = True
        self._busy = True
        self._switch_row.set_active(status.enabled)
        self._busy = False
        self._switch_row.set_visible(True)
        self._switch_row.set_sensitive(True)
        return GLib.SOURCE_REMOVE

    def _on_switch_changed(self, row: Adw.SwitchRow, _param: object) -> None:
        if not self._status_ready or self._busy:
            return

        requested = row.get_active()
        previous = not requested
        self._busy = True
        row.set_sensitive(False)
        operation = feature.enable if requested else feature.disable

        def change_state() -> None:
            try:
                result = (operation(), None)
            except feature.FeatureError as exc:
                result = (None, str(exc))
            GLib.idle_add(
                self._finish_state_change,
                requested,
                previous,
                result,
            )

        threading.Thread(
            target=change_state,
            name="dolphin-clean-title-state-change",
            daemon=True,
        ).start()

    def _finish_state_change(
        self,
        requested: bool,
        previous: bool,
        result: tuple[feature.FeatureStatus | None, str | None],
    ) -> bool:
        status, error = result
        if error is not None or status is None:
            self._busy = True
            self._switch_row.set_active(previous)
            self._busy = False
            self._switch_row.set_sensitive(True)
            self._show_error(
                "Could not change Dolphin Clean Title",
                error or "The requested state could not be applied.",
            )
            return GLib.SOURCE_REMOVE

        self._switch_row.set_active(requested)
        self._busy = False
        self._switch_row.set_sensitive(True)
        return GLib.SOURCE_REMOVE

    def _on_report_problem(self, _row: Adw.ActionRow) -> None:
        try:
            launched = Gio.AppInfo.launch_default_for_uri(feature.REPORT_URL, None)
            if not launched:
                raise RuntimeError("the default browser did not accept the URL")
        except GLib.Error as exc:
            self._show_error(
                "Could not open the issue reporter",
                f"Open this address in a browser: {feature.REPORT_URL}\n{exc}",
            )
        except RuntimeError as exc:
            self._show_error(
                "Could not open the issue reporter",
                f"Open this address in a browser: {feature.REPORT_URL}\n{exc}",
            )

    def _show_error(self, title: str, body: str) -> None:
        dialog = Adw.AlertDialog.new(title, body)
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.present(self)


class SettingsApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=0)

    def do_activate(self) -> None:
        window = self.get_active_window()
        if window is None:
            window = SettingsWindow(self)
        else:
            window.refresh_status()
        window.present()


def main() -> int:
    return SettingsApplication().run()

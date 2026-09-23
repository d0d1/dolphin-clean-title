"""Small, dependency-free Xlib adapter and event-driven title monitor."""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import select
from dataclasses import dataclass
from typing import Callable

from .title import split_supported_suffix

LOGGER = logging.getLogger(__name__)

ATOM_NONE = 0
ANY_PROPERTY_TYPE = 0
PROP_MODE_REPLACE = 0

PROPERTY_CHANGE_MASK = 1 << 22
SUBSTRUCTURE_NOTIFY_MASK = 1 << 19
STRUCTURE_NOTIFY_MASK = 1 << 17

CREATE_NOTIFY = 16
DESTROY_NOTIFY = 17
UNMAP_NOTIFY = 18
MAP_NOTIFY = 19
REPARENT_NOTIFY = 21
PROPERTY_NOTIFY = 28

EVENT_BUFFER_SIZE = 192

DisplayPtr = ctypes.c_void_p
Window = ctypes.c_ulong
Atom = ctypes.c_ulong


class XPropertyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("atom", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("state", ctypes.c_int),
    ]


class XErrorEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("resourceid", ctypes.c_ulong),
        ("serial", ctypes.c_ulong),
        ("error_code", ctypes.c_ubyte),
        ("request_code", ctypes.c_ubyte),
        ("minor_code", ctypes.c_ubyte),
    ]


XErrorHandler = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)


def find_x11_library() -> str | None:
    """Return a loadable libX11 name for diagnostics, if one is available."""

    library_name = ctypes.util.find_library("X11") or "libX11.so.6"
    try:
        ctypes.CDLL(library_name)
    except OSError:
        return None
    return library_name


@dataclass(frozen=True)
class WindowInfo:
    window: int
    instance: str
    window_class: str
    title: str | None

    @property
    def is_dolphin(self) -> bool:
        return self.instance.casefold() == "dolphin" or (
            self.window_class.casefold() == "dolphin"
        )


@dataclass(frozen=True)
class CleanResult:
    window: int
    original: str
    cleaned: str


@dataclass
class OwnedTitle:
    original_net_title: str | None
    restore_base: str
    restore_suffix: str
    cleaned_title: str


class X11Unavailable(RuntimeError):
    """Raised when libX11 or an X11 display cannot be used."""


class X11Connection:
    """Own one Xlib connection and expose the required EWMH operations."""

    def __init__(self, display_name: str | None = None) -> None:
        library_name = ctypes.util.find_library("X11") or "libX11.so.6"
        try:
            self.lib = ctypes.CDLL(library_name)
        except OSError as exc:
            raise X11Unavailable(
                "libX11.so.6 is unavailable; install the distro's X11 client "
                "runtime libraries"
            ) from exc

        self._configure_functions()
        encoded_display = display_name.encode() if display_name else None
        self.display = self.lib.XOpenDisplay(encoded_display)
        if not self.display:
            target = display_name or "$DISPLAY"
            raise X11Unavailable(
                f"cannot open X11 display {target}; check DISPLAY and X11 access"
            )

        self._last_x_error: int | None = None
        self._ignored_property_events: dict[tuple[int, int], int] = {}
        self._owned_titles: dict[int, OwnedTitle] = {}
        self._error_handler = XErrorHandler(self._handle_x_error)
        self.lib.XSetErrorHandler(self._error_handler)
        screen = self.lib.XDefaultScreen(self.display)
        self.root = int(self.lib.XRootWindow(self.display, screen))
        self.net_client_list = self._intern("_NET_CLIENT_LIST")
        self.net_wm_name = self._intern("_NET_WM_NAME")
        self.wm_name = self._intern("WM_NAME")
        self.wm_class = self._intern("WM_CLASS")
        self.utf8_string = self._intern("UTF8_STRING")
        self.string_atom = self._intern("STRING")
        self.lib.XSelectInput(
            self.display,
            self.root,
            PROPERTY_CHANGE_MASK | SUBSTRUCTURE_NOTIFY_MASK,
        )
        self._sync_checked("selecting root events")

    def _configure_functions(self) -> None:
        lib = self.lib
        lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        lib.XOpenDisplay.restype = DisplayPtr
        lib.XServerVendor.argtypes = [DisplayPtr]
        lib.XServerVendor.restype = ctypes.c_char_p
        lib.XVendorRelease.argtypes = [DisplayPtr]
        lib.XVendorRelease.restype = ctypes.c_int
        lib.XProtocolVersion.argtypes = [DisplayPtr]
        lib.XProtocolVersion.restype = ctypes.c_int
        lib.XProtocolRevision.argtypes = [DisplayPtr]
        lib.XProtocolRevision.restype = ctypes.c_int
        lib.XQueryExtension.argtypes = [
            DisplayPtr,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.XQueryExtension.restype = ctypes.c_int
        lib.XCloseDisplay.argtypes = [DisplayPtr]
        lib.XCloseDisplay.restype = ctypes.c_int
        lib.XDefaultScreen.argtypes = [DisplayPtr]
        lib.XDefaultScreen.restype = ctypes.c_int
        lib.XRootWindow.argtypes = [DisplayPtr, ctypes.c_int]
        lib.XRootWindow.restype = Window
        lib.XInternAtom.argtypes = [DisplayPtr, ctypes.c_char_p, ctypes.c_int]
        lib.XInternAtom.restype = Atom
        lib.XSetErrorHandler.argtypes = [XErrorHandler]
        lib.XSetErrorHandler.restype = XErrorHandler
        lib.XSelectInput.argtypes = [DisplayPtr, Window, ctypes.c_long]
        lib.XSelectInput.restype = ctypes.c_int
        lib.XGetWindowProperty.argtypes = [
            DisplayPtr,
            Window,
            Atom,
            ctypes.c_long,
            ctypes.c_long,
            ctypes.c_int,
            Atom,
            ctypes.POINTER(Atom),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ]
        lib.XGetWindowProperty.restype = ctypes.c_int
        lib.XFree.argtypes = [ctypes.c_void_p]
        lib.XFree.restype = ctypes.c_int
        lib.XChangeProperty.argtypes = [
            DisplayPtr,
            Window,
            Atom,
            Atom,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
        ]
        lib.XChangeProperty.restype = ctypes.c_int
        lib.XDeleteProperty.argtypes = [DisplayPtr, Window, Atom]
        lib.XDeleteProperty.restype = ctypes.c_int
        lib.XFlush.argtypes = [DisplayPtr]
        lib.XFlush.restype = ctypes.c_int
        lib.XSync.argtypes = [DisplayPtr, ctypes.c_int]
        lib.XSync.restype = ctypes.c_int
        lib.XPending.argtypes = [DisplayPtr]
        lib.XPending.restype = ctypes.c_int
        lib.XNextEvent.argtypes = [DisplayPtr, ctypes.c_void_p]
        lib.XNextEvent.restype = ctypes.c_int
        lib.XConnectionNumber.argtypes = [DisplayPtr]
        lib.XConnectionNumber.restype = ctypes.c_int
        lib.XQueryTree.argtypes = [
            DisplayPtr,
            Window,
            ctypes.POINTER(Window),
            ctypes.POINTER(Window),
            ctypes.POINTER(ctypes.POINTER(Window)),
            ctypes.POINTER(ctypes.c_uint),
        ]
        lib.XQueryTree.restype = ctypes.c_int

    def _handle_x_error(self, _display: int, error_event: int) -> int:
        if error_event:
            event = ctypes.cast(error_event, ctypes.POINTER(XErrorEvent)).contents
            self._last_x_error = int(event.error_code)
        return 0

    def _sync_checked(self, operation: str) -> None:
        self._last_x_error = None
        self.lib.XSync(self.display, 0)
        if self._last_x_error is not None:
            raise X11Unavailable(
                f"X11 error {self._last_x_error} while {operation}; "
                "the display or target window may have disappeared"
            )

    def _intern(self, name: str) -> int:
        atom = int(self.lib.XInternAtom(self.display, name.encode("ascii"), 0))
        if atom == ATOM_NONE:
            raise X11Unavailable(f"X11 server rejected required atom {name}")
        return atom

    def close(self) -> None:
        display = getattr(self, "display", None)
        if display:
            self.restore_owned_titles()
            self.lib.XCloseDisplay(display)
            self.display = None

    def __enter__(self) -> "X11Connection":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()

    @property
    def fileno(self) -> int:
        return int(self.lib.XConnectionNumber(self.display))

    def server_description(self) -> str:
        """Return stable X-server identity details for local diagnostics."""
        raw_vendor = self.lib.XServerVendor(self.display)
        vendor = (
            raw_vendor.decode("utf-8", errors="replace")
            if raw_vendor
            else "<unknown>"
        )
        major_opcode = ctypes.c_int()
        first_event = ctypes.c_int()
        first_error = ctypes.c_int()
        is_xwayland = bool(
            self.lib.XQueryExtension(
                self.display,
                b"XWAYLAND",
                ctypes.byref(major_opcode),
                ctypes.byref(first_event),
                ctypes.byref(first_error),
            )
        )
        server_kind = "Xwayland" if is_xwayland else "X11 server"
        return (
            f"{server_kind}: {vendor} "
            f"release {int(self.lib.XVendorRelease(self.display))} "
            f"(protocol {int(self.lib.XProtocolVersion(self.display))}."
            f"{int(self.lib.XProtocolRevision(self.display))})"
        )

    def _get_property(
        self, window: int, property_atom: int
    ) -> tuple[int, int, bytes] | None:
        actual_type = Atom()
        actual_format = ctypes.c_int()
        item_count = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        self._last_x_error = None
        status = self.lib.XGetWindowProperty(
            self.display,
            Window(window),
            Atom(property_atom),
            0,
            262144,
            0,
            Atom(ANY_PROPERTY_TYPE),
            ctypes.byref(actual_type),
            ctypes.byref(actual_format),
            ctypes.byref(item_count),
            ctypes.byref(bytes_after),
            ctypes.byref(data),
        )
        if self._last_x_error is not None:
            raise X11Unavailable(
                f"X11 error {self._last_x_error} while reading window "
                f"0x{window:x}; it may have been destroyed"
            )
        if status != 0 or not data or actual_format.value not in (8, 16, 32):
            if data:
                self.lib.XFree(data)
            return None

        element_size = (
            ctypes.sizeof(ctypes.c_ulong)
            if actual_format.value == 32
            else actual_format.value // 8
        )
        raw = ctypes.string_at(data, item_count.value * element_size)
        self.lib.XFree(data)
        return int(actual_type.value), int(actual_format.value), raw

    def _get_text(self, window: int, atom: int) -> str | None:
        property_value = self._get_property(window, atom)
        if property_value is None:
            return None
        actual_type, actual_format, raw = property_value
        if actual_format != 8:
            return None
        raw = raw.rstrip(b"\0")
        if actual_type == self.utf8_string:
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                LOGGER.debug(
                    "ignoring window 0x%x property %s with invalid UTF-8",
                    window,
                    atom,
                )
                return None
        if actual_type == self.string_atom and atom == self.wm_name:
            return raw.decode("latin-1")
        LOGGER.debug(
            "ignoring window 0x%x property %s with unsupported text type %s",
            window,
            atom,
            actual_type,
        )
        return None

    def _query_tree_ids(self) -> list[int]:
        root_return = Window()
        parent_return = Window()
        children_return = ctypes.POINTER(Window)()
        child_count = ctypes.c_uint()
        self._last_x_error = None
        status = self.lib.XQueryTree(
            self.display,
            Window(self.root),
            ctypes.byref(root_return),
            ctypes.byref(parent_return),
            ctypes.byref(children_return),
            ctypes.byref(child_count),
        )
        if self._last_x_error is not None or status == 0:
            return []
        try:
            return [int(children_return[index]) for index in range(child_count.value)]
        finally:
            if children_return:
                self.lib.XFree(children_return)

    def _get_window_ids(self) -> list[int]:
        client_windows: list[int] = []
        property_value = self._get_property(self.root, self.net_client_list)
        if property_value is not None:
            actual_type, actual_format, raw = property_value
            if actual_format == 32 and len(raw) % ctypes.sizeof(ctypes.c_ulong) == 0:
                values = (
                    ctypes.c_ulong * (len(raw) // ctypes.sizeof(ctypes.c_ulong))
                ).from_buffer_copy(raw)
                client_windows = [int(value) for value in values]
            elif actual_type != ATOM_NONE:
                LOGGER.debug("root _NET_CLIENT_LIST has an unsupported format")
        return sorted(set(client_windows) | set(self._query_tree_ids()))

    def _subscribe(self, window: int) -> None:
        self._last_x_error = None
        self.lib.XSelectInput(
            self.display,
            Window(window),
            PROPERTY_CHANGE_MASK | STRUCTURE_NOTIFY_MASK,
        )
        self._sync_checked(f"subscribing to window 0x{window:x}")

    def window_info(
        self, window: int, title_atom: int | None = None
    ) -> WindowInfo | None:
        class_property = self._get_property(window, self.wm_class)
        if class_property is None or class_property[1] != 8:
            return None
        class_parts = class_property[2].rstrip(b"\0").split(b"\0")
        if len(class_parts) < 2:
            return None
        instance = class_parts[0].decode("utf-8", errors="replace")
        window_class = class_parts[1].decode("utf-8", errors="replace")
        if title_atom == self.wm_name:
            title = self._get_text(window, self.wm_name)
        elif title_atom == self.net_wm_name:
            title = self._get_text(window, self.net_wm_name)
        else:
            title = self._get_text(window, self.net_wm_name)
            if title is None:
                title = self._get_text(window, self.wm_name)
        return WindowInfo(window, instance, window_class, title)

    def set_net_title(self, window: int, title: str) -> None:
        data = title.encode("utf-8")
        buffer_type = ctypes.c_ubyte * max(len(data), 1)
        buffer = buffer_type()
        if data:
            buffer[: len(data)] = data
        self._last_x_error = None
        self.lib.XChangeProperty(
            self.display,
            Window(window),
            Atom(self.net_wm_name),
            Atom(self.utf8_string),
            8,
            PROP_MODE_REPLACE,
            buffer,
            len(data),
        )
        self.lib.XFlush(self.display)
        self._sync_checked(f"rewriting window 0x{window:x}")
        key = (window, self.net_wm_name)
        self._ignored_property_events[key] = (
            self._ignored_property_events.get(key, 0) + 1
        )

    def _consume_ignored_property_event(self, window: int, atom: int) -> bool:
        key = (window, atom)
        ignored = self._ignored_property_events.get(key, 0)
        if not ignored:
            return False

        remaining = ignored - 1
        if remaining:
            self._ignored_property_events[key] = remaining
        else:
            del self._ignored_property_events[key]

        property_name = {
            self.net_wm_name: "_NET_WM_NAME",
            self.wm_name: "WM_NAME",
            self.wm_class: "WM_CLASS",
        }.get(atom, "unknown")
        LOGGER.debug(
            "ignored self-generated property event for window 0x%x: "
            "property=%s atom=%d remaining_ignore_count=%d",
            window,
            property_name,
            atom,
            remaining,
        )
        return True

    def delete_net_title(self, window: int) -> None:
        self._last_x_error = None
        self.lib.XDeleteProperty(
            self.display,
            Window(window),
            Atom(self.net_wm_name),
        )
        self.lib.XFlush(self.display)
        self._sync_checked(f"restoring window 0x{window:x}")

    def restore_owned_titles(self) -> None:
        """Restore titles changed by this connection when they are still owned."""

        for window, owned in list(self._owned_titles.items()):
            try:
                current = self._get_text(window, self.net_wm_name)
                if current != owned.cleaned_title:
                    LOGGER.info(
                        "skipped title restoration for window 0x%x because "
                        "its current title is no longer owned",
                        window,
                    )
                    continue
                restore_title = owned.restore_base + owned.restore_suffix
                if (
                    owned.original_net_title is None
                    and self._get_text(window, self.wm_name) == restore_title
                ):
                    self.delete_net_title(window)
                else:
                    self.set_net_title(window, restore_title)
                LOGGER.info("restored title for window 0x%x", window)
            except (X11Unavailable, OSError) as exc:
                LOGGER.info(
                    "skipped title restoration for window 0x%x because "
                    "the window became unavailable",
                    window,
                )
                LOGGER.debug("window 0x%x restoration detail: %s", window, exc)
        self._owned_titles.clear()

    def refresh(
        self,
        windows: set[int],
        on_cleaned: Callable[[CleanResult], None] | None = None,
    ) -> set[int]:
        current = set(self._get_window_ids())
        for window in current - windows:
            try:
                self._subscribe(window)
                info = self.window_info(window)
                if info and info.is_dolphin:
                    cleaned = self.rewrite_if_needed(info)
                    if cleaned and on_cleaned:
                        on_cleaned(cleaned)
            except X11Unavailable as exc:
                LOGGER.debug("window 0x%x disappeared during refresh: %s", window, exc)
        return current

    def rewrite_if_needed(self, info: WindowInfo) -> CleanResult | None:
        if not info.is_dolphin or info.title is None:
            return None
        return self._apply_title(info)

    def _apply_title(
        self, info: WindowInfo, source_atom: int | None = None
    ) -> CleanResult | None:
        if not info.is_dolphin or info.title is None:
            return None
        title_parts = split_supported_suffix(info.title)
        cleaned = title_parts[0] if title_parts is not None else info.title
        current_net_title = self._get_text(info.window, self.net_wm_name)
        owned = self._owned_titles.get(info.window)
        source_name = (
            "_NET_WM_NAME"
            if source_atom == self.net_wm_name
            else "WM_NAME"
            if source_atom == self.wm_name
            else "WM_CLASS"
            if source_atom == self.wm_class
            else "window refresh"
        )
        title_class = (
            "suffix-bearing" if title_parts is not None else "suffix-free"
        )
        LOGGER.debug(
            "observed Dolphin title property for window 0x%x: source=%s "
            "classification=%s ownership=%s",
            info.window,
            source_name,
            title_class,
            "owned" if owned is not None else "unowned",
        )

        # WM_NAME can be the only property an application updates. Do not
        # replace an unrelated EWMH title, but do follow a title this service
        # already owns or create one when the EWMH property is absent.
        if source_atom == self.wm_name and owned is None:
            if current_net_title is not None or cleaned == info.title:
                LOGGER.debug(
                    "ignored WM_NAME update for unowned window 0x%x: "
                    "an EWMH title already exists or no suffix matched",
                    info.window,
                )
                return None
        if source_atom == self.net_wm_name and cleaned == info.title:
            self._drop_title_ownership(
                info.window, "application published a suffix-free EWMH title"
            )
            return None
        if current_net_title == cleaned:
            if owned is not None and source_atom == self.wm_name:
                base_changed, suffix_changed = self._update_restore_title(
                    owned, info.title, title_parts
                )
                self._log_restoration_update(
                    info.window,
                    source_name,
                    title_class,
                    base_changed,
                    suffix_changed,
                    False,
                )
            return None

        if owned is None:
            restore_base, restore_suffix = (
                title_parts if title_parts is not None else (info.title, "")
            )
            owned = OwnedTitle(
                current_net_title,
                restore_base,
                restore_suffix,
                cleaned,
            )
            self._owned_titles[info.window] = owned
            LOGGER.info("acquired title ownership for window 0x%x", info.window)
        else:
            base_changed, suffix_changed = self._update_restore_title(
                owned, info.title, title_parts
            )
            cleaned_changed = owned.cleaned_title != cleaned
            owned.cleaned_title = cleaned
            self._log_restoration_update(
                info.window,
                source_name,
                title_class,
                base_changed,
                suffix_changed,
                cleaned_changed,
            )
        self.set_net_title(info.window, cleaned)
        return CleanResult(info.window, info.title, cleaned)

    def _drop_title_ownership(self, window: int, reason: str) -> None:
        if self._owned_titles.pop(window, None) is not None:
            LOGGER.info(
                "dropped title ownership for window 0x%x: %s", window, reason
            )

    @staticmethod
    def _update_restore_title(
        owned: OwnedTitle,
        title: str,
        title_parts: tuple[str, str] | None,
    ) -> tuple[bool, bool]:
        old_base = owned.restore_base
        old_suffix = owned.restore_suffix
        if title_parts is None:
            owned.restore_base = title
        else:
            owned.restore_base, owned.restore_suffix = title_parts
        return (
            owned.restore_base != old_base,
            owned.restore_suffix != old_suffix,
        )

    @staticmethod
    def _log_restoration_update(
        window: int,
        source: str,
        title_class: str,
        base_changed: bool,
        suffix_changed: bool,
        cleaned_changed: bool,
    ) -> None:
        LOGGER.debug(
            "updated restoration state for window 0x%x: source=%s "
            "classification=%s restore_base_changed=%s "
            "restore_suffix_changed=%s cleaned_title_changed=%s",
            window,
            source,
            title_class,
            "yes" if base_changed else "no",
            "yes" if suffix_changed else "no",
            "yes" if cleaned_changed else "no",
        )

    def matching_windows(self) -> list[WindowInfo]:
        result: list[WindowInfo] = []
        windows = self._get_window_ids()
        for window in windows:
            try:
                info = self.window_info(window)
            except X11Unavailable:
                continue
            if info and info.is_dolphin:
                result.append(info)
        return result

    def run(
        self,
        stop_requested: Callable[[], bool],
        on_cleaned: Callable[[CleanResult], None] | None = None,
    ) -> None:
        windows: set[int] = set()
        windows = self.refresh(windows, on_cleaned)
        while not stop_requested():
            if self.lib.XPending(self.display) == 0:
                try:
                    select.select([self.fileno], [], [], 1.0)
                except InterruptedError:
                    continue
                if stop_requested():
                    break
            while self.lib.XPending(self.display) > 0:
                event_buffer = (ctypes.c_ubyte * EVENT_BUFFER_SIZE)()
                self.lib.XNextEvent(self.display, ctypes.byref(event_buffer))
                event_type = ctypes.cast(
                    ctypes.byref(event_buffer), ctypes.POINTER(ctypes.c_int)
                ).contents.value
                if event_type == PROPERTY_NOTIFY:
                    event = XPropertyEvent.from_buffer(event_buffer)
                    if event.atom in (self.net_wm_name, self.wm_name, self.wm_class):
                        if self._consume_ignored_property_event(
                            int(event.window), int(event.atom)
                        ):
                            continue
                        try:
                            info = self.window_info(
                                int(event.window), int(event.atom)
                            )
                            if info:
                                cleaned = self._apply_title(
                                    info, int(event.atom)
                                )
                                if cleaned and on_cleaned:
                                    on_cleaned(cleaned)
                        except X11Unavailable as exc:
                            LOGGER.debug(
                                "window 0x%x disappeared during property event: %s",
                                int(event.window),
                                exc,
                            )
                elif event_type in (
                    CREATE_NOTIFY,
                    DESTROY_NOTIFY,
                    UNMAP_NOTIFY,
                    MAP_NOTIFY,
                    REPARENT_NOTIFY,
                ):
                    windows = self.refresh(windows, on_cleaned)
                    for window in set(self._owned_titles) - windows:
                        self._drop_title_ownership(
                            window, "window is no longer present"
                        )
                    self._owned_titles = {
                        window: owned
                        for window, owned in self._owned_titles.items()
                        if window in windows
                    }
            windows = self.refresh(windows, on_cleaned)

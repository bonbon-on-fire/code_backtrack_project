"""v4 test cases from PLANNING.md: system-tray front-end."""

import io
import itertools

from pynput import keyboard

from code_backtrack.app import App
from code_backtrack.tray import ICON_SIZE, TrayController, make_icon_image

Key = keyboard.Key
KeyCode = keyboard.KeyCode


def test_icon_image_size_and_mode():
    for recording in (True, False):
        img = make_icon_image(recording)
        assert img.size == (ICON_SIZE, ICON_SIZE)
        assert img.mode == "RGBA"


def test_icon_differs_between_idle_and_recording():
    # The recording (red) icon must be visually distinct from the idle (grey) one.
    assert make_icon_image(True).tobytes() != make_icon_image(False).tobytes()


# --- tray controller ---


class FakeIcon:
    """Stand-in for a pystray Icon, capturing what the controller pushes."""

    def __init__(self) -> None:
        self.title = None
        self.icon = None
        self.notifications: list[tuple] = []
        self.menu_updates = 0
        self.stopped = False

    def update_menu(self) -> None:
        self.menu_updates += 1

    def notify(self, message, title=None) -> None:
        self.notifications.append((title, message))

    def stop(self) -> None:
        self.stopped = True


def make_app() -> App:
    return App(
        out=io.StringIO(),
        clock=itertools.count(0.0, 1.0).__next__,
        probe=lambda: "TestApp.exe",
    )


def type_char(app, ch):
    k = KeyCode.from_char(ch)
    app.on_press(k)
    app.on_release(k)


def test_toggle_label_flips_with_recording():
    c = TrayController(make_app())
    assert c.toggle_label() == "Start recording"
    c.app.toggle()
    assert c.toggle_label() == "Stop recording"


def test_on_toggle_starts_then_stops_the_app():
    c = TrayController(make_app())
    icon = FakeIcon()
    c.on_toggle(icon)
    assert c.app.recording
    c.on_toggle(icon)
    assert not c.app.recording


def test_refresh_reflects_live_stats_and_sets_icon():
    app = make_app()
    c = TrayController(app)
    icon = FakeIcon()
    c.on_toggle(icon)  # start
    for _ in range(10):
        type_char(app, "a")
    c.refresh(icon)
    assert "typed 10" in icon.title
    assert icon.icon is not None
    assert icon.menu_updates > 0


def test_stop_fires_one_summary_notification():
    app = make_app()
    c = TrayController(app)
    icon = FakeIcon()
    c.on_toggle(icon)  # start (arms transition detection)
    type_char(app, "a")
    type_char(app, "a")
    app.on_press(Key.backspace)
    app.on_release(Key.backspace)
    c.on_toggle(icon)  # stop -> transition -> notify
    assert len(icon.notifications) == 1
    _title, msg = icon.notifications[0]
    assert "typed 2" in msg
    assert "deleted 1" in msg


def test_quit_finalizes_and_stops_icon():
    app = make_app()
    quit_called = []
    c = TrayController(app, on_quit=lambda: quit_called.append(True))
    icon = FakeIcon()
    c.on_toggle(icon)  # start
    c.on_quit(icon)
    assert not app.recording  # finalized
    assert quit_called == [True]
    assert icon.stopped


def test_idle_tooltip_has_no_counts():
    c = TrayController(make_app())
    assert "idle" in c.tooltip()

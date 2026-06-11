"""v4 test cases from PLANNING.md: system-tray front-end."""

from code_backtrack.tray import ICON_SIZE, make_icon_image


def test_icon_image_size_and_mode():
    for recording in (True, False):
        img = make_icon_image(recording)
        assert img.size == (ICON_SIZE, ICON_SIZE)
        assert img.mode == "RGBA"


def test_icon_differs_between_idle_and_recording():
    # The recording (red) icon must be visually distinct from the idle (grey) one.
    assert make_icon_image(True).tobytes() != make_icon_image(False).tobytes()

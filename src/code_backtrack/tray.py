"""System-tray front-end (v4): run the tracker alongside work, no terminal.

Storage-free by decision - sessions are live-only and discarded on stop. The
tracking logic lives in App; this module only adds the tray view and controls.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

ICON_SIZE = 64
_MARGIN = 8
_IDLE_COLOR = (130, 130, 130, 255)  # grey dot
_RECORDING_COLOR = (220, 50, 47, 255)  # red dot


def make_icon_image(recording: bool) -> Image.Image:
    """A small circle icon drawn at runtime - grey when idle, red when recording.

    Generated in code so there are no image assets to ship.
    """
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = _RECORDING_COLOR if recording else _IDLE_COLOR
    draw.ellipse([_MARGIN, _MARGIN, ICON_SIZE - _MARGIN, ICON_SIZE - _MARGIN], fill=color)
    return img

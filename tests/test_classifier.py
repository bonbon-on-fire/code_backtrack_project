"""Step 3 test cases from PLANNING.md: event classification."""

import pytest
from pynput import keyboard

from backspace_tracker.counter import Category
from backspace_tracker.listener import EventClassifier, Signal

Key = keyboard.Key
KeyCode = keyboard.KeyCode


@pytest.fixture
def classifier():
    return EventClassifier()


def press_chord(classifier, *modifiers):
    for mod in modifiers:
        assert classifier.on_press(mod) is None  # modifiers are never counted


def test_plain_backspace(classifier):
    assert classifier.on_press(Key.backspace) is Category.BACKSPACE


def test_plain_delete(classifier):
    assert classifier.on_press(Key.delete) is Category.DELETE


def test_letter_is_other(classifier):
    assert classifier.on_press(KeyCode.from_char("a")) is Category.OTHER


def test_ctrl_backspace(classifier):
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(Key.backspace) is Category.CTRL_BACKSPACE


def test_ctrl_delete(classifier):
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(Key.delete) is Category.CTRL_DELETE


def test_ctrl_z(classifier):
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("z")) is Category.CTRL_Z


def test_ctrl_z_arrives_as_control_char_on_windows(classifier):
    # With Ctrl held, Windows reports 'z' as the SUB control char '\x1a'.
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("\x1a")) is Category.CTRL_Z


def test_ctrl_z_arrives_as_vk(classifier):
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_vk(0x5A)) is Category.CTRL_Z


def test_ctrl_shift_backspace_is_toggle_never_counted(classifier):
    press_chord(classifier, Key.ctrl_l, Key.shift)
    result = classifier.on_press(Key.backspace)
    assert result is Signal.TOGGLE
    assert not isinstance(result, Category)


def test_ctrl_shift_z_redo_is_other(classifier):
    press_chord(classifier, Key.ctrl_l, Key.shift)
    assert classifier.on_press(KeyCode.from_char("z")) is Category.OTHER


@pytest.mark.parametrize("ctrl", [Key.ctrl_l, Key.ctrl_r, Key.ctrl])
def test_left_right_and_generic_ctrl_all_register(classifier, ctrl):
    press_chord(classifier, ctrl)
    assert classifier.on_press(Key.backspace) is Category.CTRL_BACKSPACE


def test_backspace_after_ctrl_released_is_plain(classifier):
    press_chord(classifier, Key.ctrl_l)
    classifier.on_release(Key.ctrl_l)
    assert classifier.on_press(Key.backspace) is Category.BACKSPACE


def test_one_ctrl_released_other_still_held(classifier):
    press_chord(classifier, Key.ctrl_l, Key.ctrl_r)
    classifier.on_release(Key.ctrl_l)
    assert classifier.on_press(Key.backspace) is Category.CTRL_BACKSPACE


def test_key_repeat_counts_each_event(classifier):
    # Holding Backspace delivers repeated press events with no release between.
    results = [classifier.on_press(Key.backspace) for _ in range(5)]
    assert results == [Category.BACKSPACE] * 5


def test_shift_backspace_still_deletes_a_char(classifier):
    press_chord(classifier, Key.shift)
    assert classifier.on_press(Key.backspace) is Category.BACKSPACE


def test_ctrl_shift_delete_is_other(classifier):
    # Opens dialogs (browser clear-history); does not delete text.
    press_chord(classifier, Key.ctrl_l, Key.shift)
    assert classifier.on_press(Key.delete) is Category.OTHER


def test_release_of_unseen_key_is_harmless(classifier):
    classifier.on_release(Key.ctrl_l)
    assert classifier.on_press(Key.backspace) is Category.BACKSPACE

"""Step 3 test cases from PLANNING.md: event classification."""

import pytest
from pynput import keyboard

from code_backtrack.counter import Category
from code_backtrack.listener import EventClassifier, Signal

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


def test_letter_is_char(classifier):
    assert classifier.on_press(KeyCode.from_char("a")) is Category.CHAR


@pytest.mark.parametrize("ch", ["a", "Z", "5", "$", ";"])
def test_printable_content_keys_are_char(classifier, ch):
    # Letters, digits, and symbols are typed content -> added characters (v3).
    assert classifier.on_press(KeyCode.from_char(ch)) is Category.CHAR


@pytest.mark.parametrize("key", [Key.space, Key.enter, Key.tab])
def test_space_enter_tab_are_other_not_char(classifier, key):
    # Structure, not content: excluded from "added" by decision (v3).
    assert classifier.on_press(key) is Category.OTHER


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


def test_ctrl_alt_b_is_toggle_never_counted(classifier):
    press_chord(classifier, Key.ctrl_l, Key.alt_l)
    result = classifier.on_press(KeyCode.from_char("b"))
    assert result is Signal.TOGGLE
    assert not isinstance(result, Category)


def test_ctrl_alt_b_as_control_char(classifier):
    # With Ctrl held, Windows reports 'b' as the STX control char '\x02'.
    press_chord(classifier, Key.ctrl_l, Key.alt_l)
    assert classifier.on_press(KeyCode.from_char("\x02")) is Signal.TOGGLE


def test_ctrl_alt_b_as_vk(classifier):
    press_chord(classifier, Key.ctrl_l, Key.alt_l)
    assert classifier.on_press(KeyCode.from_vk(0x42)) is Signal.TOGGLE


def test_ctrl_b_without_alt_is_other(classifier):
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("b")) is Category.OTHER


def test_alt_b_without_ctrl_is_other(classifier):
    press_chord(classifier, Key.alt_l)
    assert classifier.on_press(KeyCode.from_char("b")) is Category.OTHER


def test_plain_b_is_char(classifier):
    assert classifier.on_press(KeyCode.from_char("b")) is Category.CHAR


def test_ctrl_shift_backspace_is_word_correction_not_toggle(classifier):
    # Shift doesn't change Backspace in editors; this deletes a word.
    press_chord(classifier, Key.ctrl_l, Key.shift)
    assert classifier.on_press(Key.backspace) is Category.CTRL_BACKSPACE


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


# --- v2.5 test cases from PLANNING.md: selection / overtype / cut ---


def release(classifier, *keys):
    for key in keys:
        classifier.on_release(key)


def test_shift_arrow_then_letter_is_overtype(classifier):
    press_chord(classifier, Key.shift)
    assert classifier.on_press(Key.right) is Category.OTHER  # extends selection
    release(classifier, Key.shift)
    assert classifier.on_press(KeyCode.from_char("a")) is Category.OVERTYPE


def test_ctrl_a_then_letter_is_overtype(classifier):
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("a")) is Category.OTHER  # select-all
    release(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("x")) is Category.OVERTYPE


def test_shift_then_enter_over_selection_is_overtype(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    assert classifier.on_press(Key.enter) is Category.OVERTYPE


def test_shift_then_space_over_selection_is_overtype(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    assert classifier.on_press(Key.space) is Category.OVERTYPE


def test_tab_over_selection_is_other_not_overtype(classifier):
    # Decision: printable + Enter only. Tab-over-selection is usually indent.
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    assert classifier.on_press(Key.tab) is Category.OTHER


def test_plain_arrow_collapses_selection_no_overtype(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)  # select
    release(classifier, Key.shift)
    assert classifier.on_press(Key.right) is Category.OTHER  # plain arrow collapses
    assert classifier.on_press(KeyCode.from_char("a")) is Category.CHAR  # typed, not overtype


def test_escape_collapses_selection_no_overtype(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    assert classifier.on_press(Key.esc) is Category.OTHER
    assert classifier.on_press(KeyCode.from_char("a")) is Category.CHAR  # typed, not overtype


def test_copy_keeps_selection_then_letter_is_overtype(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("c")) is Category.OTHER  # copy
    release(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("a")) is Category.OVERTYPE


def test_overtype_clears_selection_next_letter_is_char(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    assert classifier.on_press(KeyCode.from_char("a")) is Category.OVERTYPE
    assert classifier.on_press(KeyCode.from_char("b")) is Category.CHAR  # flag cleared


def test_paste_over_selection_is_overtype(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("v")) is Category.OVERTYPE


def test_paste_without_selection_is_other(classifier):
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("v")) is Category.OTHER


def test_delete_over_selection_counts_as_delete_not_overtype(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    assert classifier.on_press(Key.delete) is Category.DELETE
    # selection consumed: a following letter is not an overtype
    assert classifier.on_press(KeyCode.from_char("a")) is Category.CHAR


def test_backspace_over_selection_counts_as_backspace_not_overtype(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    assert classifier.on_press(Key.backspace) is Category.BACKSPACE
    assert classifier.on_press(KeyCode.from_char("a")) is Category.CHAR


def test_ctrl_x_is_cut(classifier):
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("x")) is Category.CUT


def test_ctrl_x_as_control_char_is_cut(classifier):
    # With Ctrl held, Windows reports 'x' as the CAN control char '\x18'.
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("\x18")) is Category.CUT


def test_ctrl_shift_x_is_other(classifier):
    press_chord(classifier, Key.ctrl_l, Key.shift)
    assert classifier.on_press(KeyCode.from_char("x")) is Category.OTHER


def test_cut_clears_selection(classifier):
    press_chord(classifier, Key.shift)
    classifier.on_press(Key.right)
    release(classifier, Key.shift)
    press_chord(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("x")) is Category.CUT
    release(classifier, Key.ctrl_l)
    assert classifier.on_press(KeyCode.from_char("a")) is Category.CHAR


def test_held_ctrl_z_counts_each_repeat(classifier):
    # Same policy as held Backspace: one CTRL_Z per repeat event.
    press_chord(classifier, Key.ctrl_l)
    results = [classifier.on_press(KeyCode.from_char("z")) for _ in range(4)]
    assert results == [Category.CTRL_Z] * 4


def test_printable_without_selection_is_char(classifier):
    assert classifier.on_press(KeyCode.from_char("a")) is Category.CHAR


def test_ctrl_a_with_shift_is_other_no_selection(classifier):
    # Ctrl+Shift+A is an editor command, not select-all; must not arm overtype.
    press_chord(classifier, Key.ctrl_l, Key.shift)
    assert classifier.on_press(KeyCode.from_char("a")) is Category.OTHER
    release(classifier, Key.ctrl_l, Key.shift)
    assert classifier.on_press(KeyCode.from_char("b")) is Category.CHAR  # plain, after release

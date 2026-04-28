# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.domain.domain_types module.

Tests for the .opposite property implementations which are not exercised
by other tests in the suite.
"""

import pytest

from skim.domain.domain_types import (
    Alignment,
    KeyboardSide,
    KeyDirection,
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardMacroActionKind,
    SvalboardTapDance,
    SvalboardTargetKey,
)


class TestAlignmentOpposite:
    """Tests for Alignment.opposite property."""

    def test_opposite_start_returns_end(self):
        assert Alignment.START.opposite == Alignment.END

    def test_opposite_end_returns_start(self):
        assert Alignment.END.opposite == Alignment.START

    def test_opposite_center_returns_center(self):
        assert Alignment.CENTER.opposite == Alignment.CENTER


class TestKeyboardSideOpposite:
    """Tests for KeyboardSide.opposite property."""

    def test_opposite_left_returns_right(self):
        assert KeyboardSide.LEFT.opposite == KeyboardSide.RIGHT

    def test_opposite_right_returns_left(self):
        assert KeyboardSide.RIGHT.opposite == KeyboardSide.LEFT


class TestKeyDirectionOpposite:
    """Tests for KeyDirection.opposite property."""

    def test_opposite_north_returns_south(self):
        assert KeyDirection.NORTH.opposite == KeyDirection.SOUTH

    def test_opposite_south_returns_north(self):
        assert KeyDirection.SOUTH.opposite == KeyDirection.NORTH

    def test_opposite_east_returns_west(self):
        assert KeyDirection.EAST.opposite == KeyDirection.WEST

    def test_opposite_west_returns_east(self):
        assert KeyDirection.WEST.opposite == KeyDirection.EAST


class TestSvalboardTargetKey:
    """Tests for SvalboardTargetKey domain type."""

    def test_default_is_transparent_is_false(self):
        """is_transparent defaults to False."""
        key = SvalboardTargetKey()
        assert key.is_transparent is False

    def test_is_transparent_can_be_set(self):
        """is_transparent accepts True."""
        key = SvalboardTargetKey(label="A", is_transparent=True)
        assert key.is_transparent is True
        assert key.label == "A"


class TestSvalboardTapDance:
    def test_defaults_are_none_or_zero(self):
        td = SvalboardTapDance[str](id="0")
        assert td.id == "0"
        assert td.tap is None
        assert td.hold is None
        assert td.double_tap is None
        assert td.tap_then_hold is None
        assert td.tapping_term == 200
        assert td.name is None

    def test_holds_string_values(self):
        td = SvalboardTapDance[str](
            id="3",
            tap="KC_A",
            hold="KC_LSHIFT",
            double_tap="KC_NO",
            tap_then_hold=None,
            tapping_term=350,
            name="Caps mod",
        )
        assert td.tap == "KC_A"
        assert td.hold == "KC_LSHIFT"
        assert td.tapping_term == 350
        assert td.name == "Caps mod"

    def test_holds_target_key_values(self):
        target = SvalboardTargetKey(label="A")
        td = SvalboardTapDance[SvalboardTargetKey](id="0", tap=target)
        assert td.tap is target

    def test_is_frozen(self):
        td = SvalboardTapDance[str](id="0")
        with pytest.raises((AttributeError, Exception)):
            td.id = "1"  # type: ignore[misc]

    def test_is_hashable(self):
        td = SvalboardTapDance[str](id="0", tap="KC_A")
        assert hash(td) == hash(SvalboardTapDance[str](id="0", tap="KC_A"))


class TestSvalboardMacroActionKind:
    def test_has_five_kinds(self):
        assert {k.value for k in SvalboardMacroActionKind} == {
            "tap",
            "down",
            "up",
            "text",
            "delay",
        }


class TestSvalboardMacroAction:
    def test_tap_action_with_one_key(self):
        action = SvalboardMacroAction[str](kind=SvalboardMacroActionKind.TAP, keys=("KC_A",))
        assert action.kind is SvalboardMacroActionKind.TAP
        assert action.keys == ("KC_A",)
        assert action.text == ""
        assert action.duration_ms == 0

    def test_down_action_with_multiple_keys(self):
        action = SvalboardMacroAction[str](
            kind=SvalboardMacroActionKind.DOWN, keys=("KC_E", "KC_2")
        )
        assert action.keys == ("KC_E", "KC_2")

    def test_text_action(self):
        action = SvalboardMacroAction[str](kind=SvalboardMacroActionKind.TEXT, text=";qj")
        assert action.text == ";qj"
        assert action.keys == ()

    def test_delay_action(self):
        action = SvalboardMacroAction[str](kind=SvalboardMacroActionKind.DELAY, duration_ms=30)
        assert action.duration_ms == 30
        assert action.keys == ()

    def test_is_frozen(self):
        action = SvalboardMacroAction[str](kind=SvalboardMacroActionKind.TAP)
        with pytest.raises((AttributeError, Exception)):
            action.text = "nope"  # type: ignore[misc]


class TestSvalboardMacro:
    def test_defaults_to_empty_actions(self):
        macro = SvalboardMacro[str](id="0")
        assert macro.id == "0"
        assert macro.actions == ()
        assert macro.name is None

    def test_holds_action_sequence(self):
        actions = (
            SvalboardMacroAction[str](kind=SvalboardMacroActionKind.DOWN, keys=("KC_E",)),
            SvalboardMacroAction[str](kind=SvalboardMacroActionKind.DELAY, duration_ms=30),
            SvalboardMacroAction[str](kind=SvalboardMacroActionKind.UP, keys=("KC_E",)),
        )
        macro = SvalboardMacro[str](id="6", actions=actions, name="Em-dash")
        assert macro.actions == actions
        assert macro.name == "Em-dash"

    def test_is_frozen(self):
        macro = SvalboardMacro[str](id="0")
        with pytest.raises((AttributeError, Exception)):
            macro.id = "1"  # type: ignore[misc]


def test_target_key_carries_macro_id():
    key = SvalboardTargetKey(label="M3", macro_id="3")
    assert key.macro_id == "3"
    assert key.tap_dance_id is None


def test_target_key_carries_tap_dance_id():
    key = SvalboardTargetKey(label="TD0", tap_dance_id="0")
    assert key.tap_dance_id == "0"
    assert key.macro_id is None


def test_target_key_defaults_special_ids_to_none():
    key = SvalboardTargetKey(label="A")
    assert key.macro_id is None
    assert key.tap_dance_id is None


def test_target_key_remains_hashable_with_special_ids():
    a = SvalboardTargetKey(label="M3", macro_id="3")
    b = SvalboardTargetKey(label="M3", macro_id="3")
    assert hash(a) == hash(b)
    assert a == b

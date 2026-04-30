# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from unittest.mock import MagicMock

from skim.data.keyboard import (
    FingerCluster,
    SplitSide,
    SvalboardKeymap,
    SvalboardLayout,
    ThumbCluster,
)
from skim.domain.adapters.keymap_target_adapter import KeymapTargetAdapter, _detect_special_ids
from skim.domain.domain_types import (
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardMacroActionKind,
    SvalboardTapDance,
    SvalboardTargetKey,
)


def make_split_side(prefix: str) -> SplitSide[str]:
    return SplitSide(
        index=FingerCluster(f"{prefix}_I"),
        middle=FingerCluster(f"{prefix}_M"),
        ring=FingerCluster(f"{prefix}_R"),
        pinky=FingerCluster(f"{prefix}_P"),
        thumb=ThumbCluster(f"{prefix}_T"),
    )


def make_layout(prefix: str) -> SvalboardLayout[str]:
    return SvalboardLayout(
        left=make_split_side(f"{prefix}_L"),
        right=make_split_side(f"{prefix}_R"),
    )


def make_keymap(num_layers: int = 1) -> SvalboardKeymap[str]:
    return SvalboardKeymap({i: make_layout(f"L{i}") for i in range(num_layers)})


class MockLabelAdapter:
    def __init__(self, label_map: dict[str, SvalboardTargetKey] | None = None):
        self._label_map = label_map or {}

    def transform(self, keycode: str) -> SvalboardTargetKey:
        if keycode in self._label_map:
            return self._label_map[keycode]
        return SvalboardTargetKey(label=keycode.replace("_", " "))


class TestKeymapTargetAdapterInit:
    def test_initializes_with_config_and_label_adapter(self):
        label_adapter = MockLabelAdapter()
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        assert adapter._label_adapter is label_adapter


class TestKeymapTargetAdapterTransform:
    def test_transforms_single_layer_keymap(self):
        label_adapter = MockLabelAdapter()
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        keymap = make_keymap(1)
        result = adapter.transform(keymap)
        assert len(result.layers) == 1

    def test_transforms_multiple_layer_keymap(self):
        label_adapter = MockLabelAdapter()
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        keymap = make_keymap(3)
        result = adapter.transform(keymap)
        assert len(result.layers) == 3

    def test_result_contains_target_keys(self):
        label_adapter = MockLabelAdapter()
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        keymap = make_keymap(1)
        result = adapter.transform(keymap)
        first_key = result.layers[0].left.index.center_key
        assert isinstance(first_key, SvalboardTargetKey)

    def test_label_adapter_called_for_each_key(self):
        label_adapter = MagicMock()
        label_adapter.transform.return_value = SvalboardTargetKey(label="Label")
        adapter = KeymapTargetAdapter(label_adapter)
        keymap = make_keymap(1)
        adapter.transform(keymap)
        assert label_adapter.transform.call_count == 60

    def test_layer_switch_propagated(self):
        label_adapter = MockLabelAdapter({"L0_L_I": SvalboardTargetKey(layer_switch=1)})
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        keymap = make_keymap(1)
        result = adapter.transform(keymap)
        first_key = result.layers[0].left.index.center_key
        assert first_key.layer_switch == 1


class TestKeymapTargetAdapterTransparentFallthrough:
    """Tests that transparent keys borrow labels from layer 0."""

    def _label_map(self) -> dict[str, SvalboardTargetKey]:
        # Names follow make_split_side: "<L#>_<L|R>_<finger>"
        # We override only the keys we care about.
        return {
            "L0_L_I": SvalboardTargetKey(label="A"),
            "L0_L_M": SvalboardTargetKey(label="B"),
            "L1_L_I": SvalboardTargetKey(label="", is_transparent=True),
            "L1_L_M": SvalboardTargetKey(label="C"),
            "L1_L_R": SvalboardTargetKey(label="", is_transparent=True),
            # L0_L_R unset on layer 0 → MockLabelAdapter returns generic label
        }

    def _adapter(self) -> KeymapTargetAdapter:
        label_adapter = MockLabelAdapter(self._label_map())
        return KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]

    def test_transparent_borrows_layer_zero_label(self):
        keymap = make_keymap(2)
        result = self._adapter().transform(keymap)
        ghost = result.layers[1].left.index.center_key
        assert ghost.label == "A"
        assert ghost.is_transparent is True

    def test_non_transparent_unchanged(self):
        keymap = make_keymap(2)
        result = self._adapter().transform(keymap)
        regular = result.layers[1].left.middle.center_key
        assert regular.label == "C"
        assert regular.is_transparent is False

    def test_layer_zero_itself_untouched(self):
        keymap = make_keymap(2)
        result = self._adapter().transform(keymap)
        layer_zero_key = result.layers[0].left.index.center_key
        assert layer_zero_key.label == "A"
        assert layer_zero_key.is_transparent is False

    def test_substitution_disabled_leaves_label_blank(self):
        label_adapter = MockLabelAdapter(self._label_map())
        adapter = KeymapTargetAdapter(label_adapter, fallthrough_to_layer_zero=False)  # type: ignore[arg-type]
        result = adapter.transform(make_keymap(2))
        ghost = result.layers[1].left.index.center_key
        assert ghost.label == ""
        assert ghost.is_transparent is True

    def test_no_layer_zero_skips_substitution(self):
        keymap = SvalboardKeymap({1: make_layout("L1"), 2: make_layout("L2")})
        result = self._adapter().transform(keymap)
        ghost = result.layers[1].left.index.center_key
        # Layer 0 missing → label stays empty.
        assert ghost.label == ""
        assert ghost.is_transparent is True

    def test_inherits_layer_switch_from_layer_zero(self):
        """A transparent key inherits the layer_switch of its layer-0 source."""
        label_map = {
            "L0_L_I": SvalboardTargetKey(label="L2", layer_switch=2),
            "L1_L_I": SvalboardTargetKey(label="", is_transparent=True),
        }
        adapter = KeymapTargetAdapter(MockLabelAdapter(label_map))  # type: ignore[arg-type]
        result = adapter.transform(make_keymap(2))
        ghost = result.layers[1].left.index.center_key
        assert ghost.label == "L2"
        assert ghost.layer_switch == 2
        assert ghost.is_transparent is True

    def test_suppresses_self_referential_ghost(self):
        """Layer-0 source pointing at the layer being rendered → blank ghost."""
        label_map = {
            "L0_L_I": SvalboardTargetKey(label="L1", layer_switch=1),
            "L1_L_I": SvalboardTargetKey(label="", is_transparent=True),
        }
        adapter = KeymapTargetAdapter(MockLabelAdapter(label_map))  # type: ignore[arg-type]
        result = adapter.transform(make_keymap(2))
        ghost = result.layers[1].left.index.center_key
        assert ghost.label == ""
        assert ghost.layer_switch is None

    def test_does_not_inherit_layer_switch_when_disabled(self):
        """Fallthrough disabled → ghost keeps its original (None) layer_switch."""
        label_map = {
            "L0_L_I": SvalboardTargetKey(label="L2", layer_switch=2),
            "L1_L_I": SvalboardTargetKey(label="", is_transparent=True),
        }
        adapter = KeymapTargetAdapter(MockLabelAdapter(label_map), fallthrough_to_layer_zero=False)  # type: ignore[arg-type]
        result = adapter.transform(make_keymap(2))
        ghost = result.layers[1].left.index.center_key
        assert ghost.layer_switch is None

    def test_layer_zero_empty_at_position_keeps_blank(self):
        # L0_L_R is not in the label_map, so MockLabelAdapter returns the
        # generic label "L0 L R" — but here we explicitly set layer 0 to empty
        # to simulate KC_NO/KC_TRNS at base position.
        label_map = self._label_map()
        label_map["L0_L_R"] = SvalboardTargetKey(label="")
        adapter = KeymapTargetAdapter(MockLabelAdapter(label_map))  # type: ignore[arg-type]
        keymap = make_keymap(2)
        result = adapter.transform(keymap)
        ghost = result.layers[1].left.ring.center_key
        assert ghost.label == ""
        assert ghost.is_transparent is True

    def test_fallthrough_propagates_macro_id(self):
        """A transparent layer-1 slot whose layer-0 source carries macro_id
        must inherit it after fallthrough."""
        label_map = {
            "L0_L_I": SvalboardTargetKey(label="M3", macro_id="3"),
            "L1_L_I": SvalboardTargetKey(label="", is_transparent=True),
        }
        adapter = KeymapTargetAdapter(MockLabelAdapter(label_map))  # type: ignore[arg-type]
        keymap = make_keymap(2)
        result = adapter.transform(keymap)
        higher_key = result.layers[1].left.index.center_key
        assert higher_key.is_transparent is True
        assert higher_key.macro_id == "3"
        assert higher_key.label == "M3"

    def test_fallthrough_propagates_tap_dance_id(self):
        """A transparent layer-1 slot whose layer-0 source carries tap_dance_id
        must inherit it after fallthrough."""
        label_map = {
            "L0_L_I": SvalboardTargetKey(label="TD7", tap_dance_id="7"),
            "L1_L_I": SvalboardTargetKey(label="", is_transparent=True),
        }
        adapter = KeymapTargetAdapter(MockLabelAdapter(label_map))  # type: ignore[arg-type]
        keymap = make_keymap(2)
        result = adapter.transform(keymap)
        higher_key = result.layers[1].left.index.center_key
        assert higher_key.is_transparent is True
        assert higher_key.tap_dance_id == "7"
        assert higher_key.label == "TD7"

    def test_self_referential_suppression_wins_over_macro_id(self):
        """When layer-0 source has layer_switch == current_layer_index and
        carries macro_id, suppression must still win — slot stays blank."""
        label_map = {
            "L0_L_I": SvalboardTargetKey(label="L1", layer_switch=1, macro_id="3"),
            "L1_L_I": SvalboardTargetKey(label="", is_transparent=True),
        }
        adapter = KeymapTargetAdapter(MockLabelAdapter(label_map))  # type: ignore[arg-type]
        keymap = make_keymap(2)
        result = adapter.transform(keymap)
        higher_key = result.layers[1].left.index.center_key
        assert higher_key.is_transparent is True
        assert higher_key.label == ""
        assert higher_key.macro_id is None


class TestTransformLayer:
    def test_transforms_all_keys_in_layer(self):
        label_adapter = MockLabelAdapter()
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        layout = make_layout("L0")
        result = adapter._transform_layer(layout, (), ())
        keys = list(result)
        assert len(keys) == 60
        assert all(isinstance(k, SvalboardTargetKey) for k in keys)

    def test_preserves_key_positions(self):
        def transform_with_position(keycode: str) -> SvalboardTargetKey:
            return SvalboardTargetKey(label=f"LABEL_{keycode}")

        label_adapter = MagicMock()
        label_adapter.transform.side_effect = transform_with_position
        adapter = KeymapTargetAdapter(label_adapter)
        layout = make_layout("L0")
        result = adapter._transform_layer(layout, (), ())
        first_key = result.left.index.center_key
        assert "L0_L_I" in first_key.label


class TestKeymapTargetAdapterTapDances:
    """Tests that transform rewrites tap-dance keycodes into target keys."""

    def test_keycodes_are_label_transformed(self):
        label_adapter = MockLabelAdapter(
            {
                "KC_Q": SvalboardTargetKey(label="Q"),
                "KC_LSHIFT": SvalboardTargetKey(label="LShift"),
            }
        )
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        keymap = SvalboardKeymap[str](
            layers=make_keymap(1).layers,
            tap_dances=(
                SvalboardTapDance[str](
                    id="0",
                    tap="KC_Q",
                    hold="KC_LSHIFT",
                    double_tap=None,
                    tap_then_hold=None,
                    tapping_term=250,
                    name="Quick shift",
                ),
            ),
        )
        result = adapter.transform(keymap)
        td = result.tap_dances[0]
        assert td.id == "0"
        assert td.name == "Quick shift"
        assert td.tapping_term == 250
        assert td.tap == SvalboardTargetKey(label="Q")
        assert td.hold == SvalboardTargetKey(label="LShift")
        assert td.double_tap is None
        assert td.tap_then_hold is None

    def test_no_tap_dances_yields_empty_tuple(self):
        label_adapter = MockLabelAdapter()
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        result = adapter.transform(make_keymap(1))
        assert result.tap_dances == ()


class TestKeymapTargetAdapterMacros:
    """Tests that transform rewrites macro action keycodes."""

    def test_action_keys_are_label_transformed(self):
        label_adapter = MockLabelAdapter(
            {
                "KC_E": SvalboardTargetKey(label="E"),
                "KC_1": SvalboardTargetKey(label="1"),
            }
        )
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        keymap = SvalboardKeymap[str](
            layers=make_keymap(1).layers,
            macros=(
                SvalboardMacro[str](
                    id="6",
                    actions=(
                        SvalboardMacroAction[str](
                            kind=SvalboardMacroActionKind.DOWN, keys=("KC_E",)
                        ),
                        SvalboardMacroAction[str](
                            kind=SvalboardMacroActionKind.DELAY, duration_ms=30
                        ),
                        SvalboardMacroAction[str](
                            kind=SvalboardMacroActionKind.UP, keys=("KC_E", "KC_1")
                        ),
                        SvalboardMacroAction[str](kind=SvalboardMacroActionKind.TEXT, text=";qj"),
                    ),
                    name="E1",
                ),
            ),
        )
        result = adapter.transform(keymap)
        macro = result.macros[0]
        assert macro.id == "6"
        assert macro.name == "E1"
        assert macro.actions[0].keys == (SvalboardTargetKey(label="E"),)
        assert macro.actions[1].duration_ms == 30
        assert macro.actions[1].keys == ()
        assert macro.actions[2].keys == (
            SvalboardTargetKey(label="E"),
            SvalboardTargetKey(label="1"),
        )
        assert macro.actions[3].kind is SvalboardMacroActionKind.TEXT
        assert macro.actions[3].text == ";qj"
        assert macro.actions[3].keys == ()

    def test_no_macros_yields_empty_tuple(self):
        label_adapter = MockLabelAdapter()
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        result = adapter.transform(make_keymap(1))
        assert result.macros == ()


def _make_macro(id_: str) -> SvalboardMacro[str]:
    return SvalboardMacro[str](
        id=id_,
        actions=(SvalboardMacroAction[str](kind=SvalboardMacroActionKind.TEXT, text="x"),),
    )


def _make_tap_dance(id_: str) -> SvalboardTapDance[str]:
    return SvalboardTapDance[str](
        id=id_,
        tap="KC_A",
        hold=None,
        double_tap=None,
        tap_then_hold=None,
        tapping_term=200,
    )


class TestDetectSpecialIds:
    """Unit tests for the module-level _detect_special_ids helper."""

    def _macros(self, *ids: str) -> tuple[SvalboardMacro[str], ...]:
        return tuple(_make_macro(i) for i in ids)

    def _tap_dances(self, *ids: str) -> tuple[SvalboardTapDance[str], ...]:
        return tuple(_make_tap_dance(i) for i in ids)

    def test_vial_m0_matches_macro_id_0(self):
        macro_id, td_id = _detect_special_ids("M0", self._macros("0", "1"), ())
        assert macro_id == "0"
        assert td_id is None

    def test_qmk_macro3_matches_macro_id_3(self):
        macro_id, td_id = _detect_special_ids("MACRO_3", self._macros("3"), ())
        assert macro_id == "3"
        assert td_id is None

    def test_vial_m99_unknown_leaves_both_none(self):
        macro_id, td_id = _detect_special_ids("M99", self._macros("0", "1"), ())
        assert macro_id is None
        assert td_id is None

    def test_td5_matches_tap_dance_id_5(self):
        macro_id, td_id = _detect_special_ids("TD(5)", (), self._tap_dances("5"))
        assert macro_id is None
        assert td_id == "5"

    def test_td99_unknown_leaves_both_none(self):
        macro_id, td_id = _detect_special_ids("TD(99)", (), self._tap_dances("0", "1"))
        assert macro_id is None
        assert td_id is None

    def test_plain_kc_a_leaves_both_none(self):
        macro_id, td_id = _detect_special_ids("KC_A", self._macros("0"), self._tap_dances("0"))
        assert macro_id is None
        assert td_id is None

    def test_empty_definitions_leaves_both_none(self):
        macro_id, td_id = _detect_special_ids("M0", (), ())
        assert macro_id is None
        assert td_id is None


class TestSpecialIdStampingViaTransformLayer:
    """Integration tests: _transform_layer stamps macro_id / tap_dance_id
    via lookup, and fallthrough propagates them."""

    def _make_keymap_with_macros_tds(self) -> SvalboardKeymap[str]:
        """Single-layer keymap where one key is M0 and another is TD(5)."""
        # Use a custom layout so a known position has the special keycodes.
        from skim.data.keyboard import FingerCluster, SplitSide, ThumbCluster

        def _side(prefix: str, special_key: str) -> SplitSide[str]:
            return SplitSide(
                index=FingerCluster(special_key),  # center = special
                middle=FingerCluster(f"{prefix}_M"),
                ring=FingerCluster(f"{prefix}_R"),
                pinky=FingerCluster(f"{prefix}_P"),
                thumb=ThumbCluster(f"{prefix}_T"),
            )

        layout = SvalboardLayout(
            left=_side("L0_L", "M0"),
            right=_side("L0_R", "TD(5)"),
        )
        return SvalboardKeymap(
            layers={0: layout},
            macros=(_make_macro("0"),),
            tap_dances=(_make_tap_dance("5"),),
        )

    def test_vial_macro_keycode_gets_macro_id(self):
        adapter = KeymapTargetAdapter(MockLabelAdapter())  # type: ignore[arg-type]
        keymap = self._make_keymap_with_macros_tds()
        result = adapter.transform(keymap)
        key = result.layers[0].left.index.center_key
        assert key.macro_id == "0"
        assert key.tap_dance_id is None

    def test_td_keycode_gets_tap_dance_id(self):
        adapter = KeymapTargetAdapter(MockLabelAdapter())  # type: ignore[arg-type]
        keymap = self._make_keymap_with_macros_tds()
        result = adapter.transform(keymap)
        key = result.layers[0].right.index.center_key
        assert key.tap_dance_id == "5"
        assert key.macro_id is None

    def test_plain_key_has_no_special_ids(self):
        adapter = KeymapTargetAdapter(MockLabelAdapter())  # type: ignore[arg-type]
        keymap = self._make_keymap_with_macros_tds()
        result = adapter.transform(keymap)
        key = result.layers[0].left.middle.center_key
        assert key.macro_id is None
        assert key.tap_dance_id is None

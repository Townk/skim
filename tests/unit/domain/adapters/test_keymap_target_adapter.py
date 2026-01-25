from unittest.mock import MagicMock

from skim.data.keyboard import (
    FingerCluster,
    SplitSide,
    SvalboardKeymap,
    SvalboardLayout,
    ThumbCluster,
)
from skim.domain.adapters.keymap_target_adapter import KeymapTargetAdapter
from skim.domain.domain_types import SvalboardTargetKey


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
    return SvalboardKeymap([make_layout(f"L{i}") for i in range(num_layers)])


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
        label_adapter = MockLabelAdapter(
            {"L0_L_I": SvalboardTargetKey(label="Layer 1", layer_switch=1)}
        )
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        keymap = make_keymap(1)
        result = adapter.transform(keymap)
        first_key = result.layers[0].left.index.center_key
        assert first_key.layer_switch == 1


class TestTransformLayer:
    def test_transforms_all_keys_in_layer(self):
        label_adapter = MockLabelAdapter()
        adapter = KeymapTargetAdapter(label_adapter)  # type: ignore[arg-type]
        layout = make_layout("L0")
        result = adapter._transform_layer(layout)
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
        result = adapter._transform_layer(layout)
        first_key = result.left.index.center_key
        assert "L0_L_I" in first_key.label

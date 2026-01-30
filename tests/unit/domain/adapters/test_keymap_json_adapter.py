# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from skim.domain.adapters.keymap_json_adapter import (
    CONFIG_UI_LEFT_FINGER_CLUSTERS_KEYS,
    CONFIG_UI_LEFT_THUMB_CLUSTER_KEYS,
    CONFIG_UI_RIGHT_FINGER_CLUSTERS_KEYS,
    CONFIG_UI_RIGHT_THUMB_CLUSTER_KEYS,
    KeymapJsonAdapter,
)
from skim.domain.domain_types import KeymapType


class TestSliceConstants:
    def test_right_finger_clusters_slice(self):
        assert slice(36, 60) == CONFIG_UI_RIGHT_FINGER_CLUSTERS_KEYS

    def test_left_finger_clusters_slice(self):
        assert slice(6, 30) == CONFIG_UI_LEFT_FINGER_CLUSTERS_KEYS

    def test_right_thumb_cluster_slice(self):
        assert slice(30, 36) == CONFIG_UI_RIGHT_THUMB_CLUSTER_KEYS

    def test_left_thumb_cluster_slice(self):
        assert slice(0, 6) == CONFIG_UI_LEFT_THUMB_CLUSTER_KEYS


class TestKeymapJsonAdapterC2Json:
    def test_c2json_returns_unchanged(self):
        layers = [["KC_A"] * 60, ["KC_B"] * 60]
        result = KeymapJsonAdapter.transform(layers, KeymapType.C2JSON)
        assert result == layers

    def test_c2json_preserves_structure(self):
        layer = [f"KC_{i}" for i in range(60)]
        result = KeymapJsonAdapter.transform([layer], KeymapType.C2JSON)
        assert result[0] == layer


class TestKeymapJsonAdapterKeybard:
    def test_keybard_transforms_single_layer(self):
        layer = [f"K{i:02d}" for i in range(60)]
        result = KeymapJsonAdapter.transform([layer], KeymapType.KEYBARD)
        assert len(result) == 1
        assert len(result[0]) == 60

    def test_keybard_transforms_multiple_layers(self):
        layers = [[f"L{layer}K{k:02d}" for k in range(60)] for layer in range(3)]
        result = KeymapJsonAdapter.transform(layers, KeymapType.KEYBARD)
        assert len(result) == 3

    def test_keybard_reorders_keys(self):
        layer = [f"K{i:02d}" for i in range(60)]
        result = KeymapJsonAdapter.transform([layer], KeymapType.KEYBARD)
        assert result[0] != layer


class TestKeymapJsonAdapterVial:
    def test_vial_flattens_and_transforms(self):
        cluster = ["KC_A", "KC_B", "KC_C", "KC_D", "KC_E", "KC_F"]
        layer = [cluster] * 10
        result = KeymapJsonAdapter.transform([layer], KeymapType.VIAL)
        assert len(result) == 1
        assert len(result[0]) == 60

    def test_vial_transforms_multiple_layers(self):
        cluster = ["KC_A"] * 6
        layer = [cluster] * 10
        layers = [layer, layer]
        result = KeymapJsonAdapter.transform(layers, KeymapType.VIAL)
        assert len(result) == 2


class TestSingleLayerAdaptor:
    def test_output_has_60_keys(self):
        layer = [f"K{i:02d}" for i in range(60)]
        result = KeymapJsonAdapter._single_layer_adaptor(layer)
        assert len(result) == 60

    def test_no_empty_keys(self):
        layer = [f"K{i:02d}" for i in range(60)]
        result = KeymapJsonAdapter._single_layer_adaptor(layer)
        assert all(k != "" for k in result)

    def test_all_input_keys_present_in_output(self):
        layer = [f"K{i:02d}" for i in range(60)]
        result = KeymapJsonAdapter._single_layer_adaptor(layer)
        assert set(result) == set(layer)

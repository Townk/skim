# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.loaders.keymap_loader module.

Tests cover keymap loading from various formats (Vial, Keybard, C2JSON),
format detection, and error handling.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from skim.application.loaders.keymap_loader import (
    ParsedKeymap,
    _detect_format_from_path,
    _detect_keymap_from_json,
    _parse_c2json,
    _parse_keybard,
    _parse_vial,
    load_keymap,
    load_keymap_file,
    load_keymap_from_stdin,
    load_keymap_json,
)
from skim.domain.domain_types import (
    KeymapType,
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardMacroActionKind,
    SvalboardTapDance,
)


class TestDetectKeymapFromJson:
    """Tests for _detect_keymap_from_json function."""

    def test_detect_vial_format(self):
        """Detect Vial format from JSON structure."""
        data = {"layout": [[]], "version": 1}
        assert _detect_keymap_from_json(data) == KeymapType.VIAL

    def test_detect_keybard_format(self):
        """Detect Keybard format from JSON structure."""
        data = {"keymap": [[]]}
        assert _detect_keymap_from_json(data) == KeymapType.KEYBARD

    def test_detect_c2json_format(self):
        """Detect C2JSON format from JSON structure."""
        data = {"layers": [[]]}
        assert _detect_keymap_from_json(data) == KeymapType.C2JSON

    def test_vial_takes_precedence(self):
        """Vial detection takes precedence over others."""
        data = {"layout": [[]], "version": 1, "keymap": [[]], "layers": [[]]}
        assert _detect_keymap_from_json(data) == KeymapType.VIAL

    def test_unknown_format_raises(self):
        """Unknown format raises ValueError."""
        data = {"unknown_key": "value"}
        with pytest.raises(ValueError, match="Unknown keymap format"):
            _detect_keymap_from_json(data)

    def test_empty_dict_raises(self):
        """Empty dictionary raises ValueError."""
        with pytest.raises(ValueError, match="Unknown keymap format"):
            _detect_keymap_from_json({})

    def test_keymap_not_list_not_detected(self):
        """Keybard format requires 'keymap' to be a list."""
        data = {"keymap": "not a list"}
        with pytest.raises(ValueError, match="Unknown keymap format"):
            _detect_keymap_from_json(data)

    def test_layers_not_list_not_detected(self):
        """C2JSON format requires 'layers' to be a list."""
        data = {"layers": "not a list"}
        with pytest.raises(ValueError, match="Unknown keymap format"):
            _detect_keymap_from_json(data)


class TestDetectFormatFromPath:
    """Tests for _detect_format_from_path function."""

    def test_detect_vial_extension(self):
        """Detect Vial format from .vil extension."""
        path = Path("/some/path/keymap.vil")
        assert _detect_format_from_path(path) == KeymapType.VIAL

    def test_detect_keybard_extension(self):
        """Detect Keybard format from .kbi extension."""
        path = Path("/some/path/keymap.kbi")
        assert _detect_format_from_path(path) == KeymapType.KEYBARD

    def test_json_extension_returns_none(self):
        """JSON extension returns None (auto-detect from content)."""
        path = Path("/some/path/keymap.json")
        assert _detect_format_from_path(path) is None

    def test_unknown_extension_returns_none(self):
        """Unknown extension returns None."""
        path = Path("/some/path/keymap.txt")
        assert _detect_format_from_path(path) is None


class TestParseVial:
    """Tests for _parse_vial function."""

    def test_missing_layout_key_raises(self):
        """Missing 'layout' key raises ValueError."""
        with pytest.raises(ValueError, match="Missing 'layout' key"):
            _parse_vial({"other": "data"})

    def test_layout_not_list_raises(self):
        """Non-list 'layout' raises ValueError."""
        with pytest.raises(ValueError, match="'layout' must be a list"):
            _parse_vial({"layout": "not a list"})


class TestParseKeybard:
    """Tests for _parse_keybard function."""

    def test_missing_keymap_key_raises(self):
        """Missing 'keymap' key raises ValueError."""
        with pytest.raises(ValueError, match="Missing 'keymap' key"):
            _parse_keybard({"other": "data"})

    def test_keymap_not_list_raises(self):
        """Non-list 'keymap' raises ValueError."""
        with pytest.raises(ValueError, match="'keymap' must be a list"):
            _parse_keybard({"keymap": "not a list"})


class TestParseC2json:
    """Tests for _parse_c2json function."""

    def test_missing_layers_key_raises(self):
        """Missing 'layers' key raises ValueError."""
        with pytest.raises(ValueError, match="Missing 'layers' key"):
            _parse_c2json({"other": "data"})

    def test_layers_not_list_raises(self):
        """Non-list 'layers' raises ValueError."""
        with pytest.raises(ValueError, match="'layers' must be a list"):
            _parse_c2json({"layers": "not a list"})

    def test_layer_item_not_list_raises(self):
        """Non-list layer item raises ValueError."""
        with pytest.raises(ValueError, match="Layer 0 must be a list"):
            _parse_c2json({"layers": ["not a list"]})

    def test_multiple_invalid_layers_reports_first(self):
        """Reports first invalid layer."""
        with pytest.raises(ValueError, match="Layer 1 must be a list"):
            _parse_c2json({"layers": [[], "not a list"]})


class TestLoadKeymapJson:
    """Tests for load_keymap_json function."""

    def test_invalid_json_raises(self):
        """Invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_keymap_json("not valid json")

    def test_empty_json_object_raises(self):
        """Empty JSON object raises ValueError."""
        with pytest.raises(ValueError, match="Unknown keymap format"):
            load_keymap_json("{}")

    def test_explicit_keymap_type_used(self):
        """Explicit keymap type is used instead of auto-detection."""
        # Data has 'layers' key but we force KEYBARD format
        data = {"layers": [[]], "keymap": [["KC_A"] * 60]}
        content = json.dumps(data)
        # This should not raise because we're forcing KEYBARD type
        # and data has 'keymap' key
        result = load_keymap_json(content, KeymapType.KEYBARD)
        assert result is not None


class TestLoadKeymapFile:
    """Tests for load_keymap_file function."""

    def test_file_not_found_raises(self, tmp_path):
        """Non-existent file raises FileNotFoundError."""
        path = tmp_path / "nonexistent.kbi"
        with pytest.raises(FileNotFoundError):
            load_keymap_file(path)

    def test_reads_file_content(self, tmp_path):
        """Reads and parses file content."""
        # Create a minimal Keybard file
        keymap_data = {"keymap": [["KC_A"] * 60]}
        path = tmp_path / "test.kbi"
        path.write_text(json.dumps(keymap_data))

        result = load_keymap_file(path)
        assert result is not None
        assert len(result.layers) == 1  # One layer

    def test_detects_format_from_extension(self, tmp_path):
        """Format is detected from file extension."""
        # Vial format with .vil extension
        vial_data = {"layout": [["KC_A"] * 60], "version": 1}
        path = tmp_path / "test.vil"
        path.write_text(json.dumps(vial_data))

        result = load_keymap_file(path)
        assert result is not None


class TestLoadKeymapFromStdin:
    """Tests for load_keymap_from_stdin function."""

    def test_tty_stdin_raises(self):
        """TTY stdin raises ValueError."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with pytest.raises(ValueError, match="No data piped"):
                load_keymap_from_stdin()

    def test_reads_from_stdin(self):
        """Reads JSON from stdin."""
        keymap_data = {"keymap": [["KC_A"] * 60]}
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = json.dumps(keymap_data)
            result = load_keymap_from_stdin()
            assert result is not None
            assert len(result.layers) == 1

    def test_invalid_json_from_stdin_raises(self):
        """Invalid JSON from stdin raises ValueError."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = "not valid json"
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_keymap_from_stdin()


class TestParsedKeymapBundle:
    """Tests that the loader helpers return a ParsedKeymap bundle."""

    def test_parse_vial_returns_bundle_with_empty_definitions(self):
        data = {"layout": [[["KC_A"] * 60]], "version": 1}
        result = _parse_vial(data)
        assert isinstance(result, ParsedKeymap)
        assert len(result.layers) == 1
        assert result.tap_dances == ()
        assert result.macros == ()

    def test_parse_keybard_returns_bundle(self):
        data = {"keymap": [["KC_A"] * 60]}
        result = _parse_keybard(data)
        assert isinstance(result, ParsedKeymap)
        assert result.tap_dances == ()
        assert result.macros == ()

    def test_parse_c2json_returns_bundle(self):
        data = {"layers": [["KC_A"] * 60]}
        result = _parse_c2json(data)
        assert isinstance(result, ParsedKeymap)
        assert result.tap_dances == ()
        assert result.macros == ()

    def test_load_keymap_json_returns_bundle(self):
        import json as _json

        content = _json.dumps({"keymap": [["KC_A"] * 60]})
        result = load_keymap_json(content)
        assert isinstance(result, ParsedKeymap)


class TestLoadKeymap:
    """Tests for load_keymap main function."""

    def test_load_from_file(self, tmp_path):
        """Loads keymap from file with dict-based layers."""
        keymap_data = {"keymap": [["KC_A"] * 60]}
        path = tmp_path / "test.kbi"
        path.write_text(json.dumps(keymap_data))

        keymap = load_keymap(path)
        assert keymap is not None
        assert isinstance(keymap.layers, dict)
        assert set(keymap.layers.keys()) == {0}

    def test_load_from_stdin_when_none(self):
        """Loads from stdin when path is None."""
        keymap_data = {"keymap": [["KC_A"] * 60]}
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = json.dumps(keymap_data)
            keymap = load_keymap(None)
            assert keymap is not None
            assert isinstance(keymap.layers, dict)
            assert set(keymap.layers.keys()) == {0}

    def test_path_not_file_raises(self, tmp_path):
        """Non-file path raises ValueError."""
        # tmp_path is a directory, not a file
        path = tmp_path / "nonexistent_file.kbi"
        with pytest.raises(ValueError, match="does not exist"):
            load_keymap(path)

    def test_multiple_layers(self, tmp_path):
        """Loads keymap with multiple layers using sequential indices."""
        keymap_data = {"keymap": [["KC_A"] * 60, ["KC_B"] * 60, ["KC_C"] * 60]}
        path = tmp_path / "test.kbi"
        path.write_text(json.dumps(keymap_data))

        keymap = load_keymap(path)
        assert isinstance(keymap.layers, dict)
        assert set(keymap.layers.keys()) == {0, 1, 2}

    def test_layer_indices_pair_with_non_empty_source_layers(self, tmp_path):
        """layer_indices label the non-empty source layers in source order.

        Empty source layers (all KC_NO/KC_TRNS) are filtered before pairing,
        so a sparse vial-style file pads out to 16 layers but only the two
        populated ones are paired with the two config indices.
        """
        layers = [["KC_NO"] * 60 for _ in range(16)]
        layers[0] = ["KC_A"] * 60
        layers[15] = ["KC_B"] * 60
        path = tmp_path / "test.kbi"
        path.write_text(json.dumps({"keymap": layers}))

        keymap = load_keymap(path, layer_indices=[0, 15])

        assert isinstance(keymap.layers, dict)
        assert set(keymap.layers.keys()) == {0, 15}
        assert keymap.layers[0].right.index.center_key == "KC_A"
        assert keymap.layers[15].right.index.center_key == "KC_B"

    def test_layer_indices_zip_compact_c2json_with_sparse_indices(self, tmp_path):
        """Compact c2json layers pair positionally with sparse config indices.

        c2json files only list the layers actually defined in the user's
        keymaps[] array, so a config with sparse indices like [0, 1, 14, 15]
        against a 4-layer compact c2json must label them in source order.
        """
        keymap_data = {
            "layers": [
                ["KC_A"] * 60,
                ["KC_B"] * 60,
                ["KC_C"] * 60,
                ["KC_D"] * 60,
            ]
        }
        path = tmp_path / "test.json"
        path.write_text(json.dumps(keymap_data))

        keymap = load_keymap(path, layer_indices=[0, 1, 14, 15])

        assert isinstance(keymap.layers, dict)
        assert set(keymap.layers.keys()) == {0, 1, 14, 15}
        assert keymap.layers[0].right.index.center_key == "KC_A"
        assert keymap.layers[1].right.index.center_key == "KC_B"
        assert keymap.layers[14].right.index.center_key == "KC_C"
        assert keymap.layers[15].right.index.center_key == "KC_D"

    def test_layer_indices_label_layers_in_source_order(self, tmp_path):
        """All populated source layers receive labels from layer_indices."""
        keymap_data = {"keymap": [["KC_A"] * 60, ["KC_B"] * 60, ["KC_C"] * 60]}
        path = tmp_path / "test.kbi"
        path.write_text(json.dumps(keymap_data))

        keymap = load_keymap(path, layer_indices=[0, 5, 10])

        assert isinstance(keymap.layers, dict)
        assert set(keymap.layers.keys()) == {0, 5, 10}
        assert keymap.layers[0].right.index.center_key == "KC_A"
        assert keymap.layers[5].right.index.center_key == "KC_B"
        assert keymap.layers[10].right.index.center_key == "KC_C"

    def test_svalboard_layout_created_correctly(self, tmp_path):
        """SvalboardKeymap contains SvalboardLayout objects with correct hierarchy."""
        # Use c2json format (no transformation) to test hierarchy directly
        keymap_data = {"layers": [[f"KC_{i}" for i in range(60)]]}
        path = tmp_path / "test.json"
        path.write_text(json.dumps(keymap_data))

        keymap = load_keymap(path)
        assert isinstance(keymap.layers, dict)
        assert set(keymap.layers.keys()) == {0}
        # Access via hierarchy - c2json format is already in QMK order:
        # right.index.center_key is at index 0, left.thumb.down_key at index 54
        assert keymap.layers[0].right.index.center_key == "KC_0"
        assert keymap.layers[0].left.thumb.down_key == "KC_54"


class TestParseVialTapDance:
    """Tests that _parse_vial extracts top-level tap_dance entries."""

    def test_no_tap_dance_key_yields_empty(self):
        data = {"layout": [[["KC_A"] * 60]], "version": 1}
        result = _parse_vial(data)
        assert result.tap_dances == ()

    def test_single_tap_dance(self):
        data = {
            "layout": [[["KC_A"] * 60]],
            "version": 1,
            "tap_dance": [["KC_Q", "KC_LSHIFT", "KC_NO", "KC_NO", 250]],
        }
        result = _parse_vial(data)
        assert result.tap_dances == (
            SvalboardTapDance[str](
                id="0",
                tap="KC_Q",
                hold="KC_LSHIFT",
                double_tap=None,
                tap_then_hold=None,
                tapping_term=250,
            ),
        )

    def test_multiple_tap_dances_get_indexed_ids(self):
        data = {
            "layout": [[["KC_A"] * 60]],
            "version": 1,
            "tap_dance": [
                ["KC_Q", "KC_NO", "KC_NO", "KC_NO", 100],
                ["KC_NO", "KC_NO", "KC_NO", "KC_NO", 200],
                ["KC_A", "KC_B", "KC_C", "KC_D", 300],
            ],
        }
        result = _parse_vial(data)
        assert [td.id for td in result.tap_dances] == ["0", "1", "2"]
        assert result.tap_dances[2].tap == "KC_A"
        assert result.tap_dances[2].hold == "KC_B"
        assert result.tap_dances[2].double_tap == "KC_C"
        assert result.tap_dances[2].tap_then_hold == "KC_D"
        assert result.tap_dances[2].tapping_term == 300

    def test_kc_no_maps_to_none_on_each_field(self):
        data = {
            "layout": [[["KC_A"] * 60]],
            "version": 1,
            "tap_dance": [["KC_NO", "KC_NO", "KC_NO", "KC_NO", 200]],
        }
        result = _parse_vial(data)
        td = result.tap_dances[0]
        assert td.tap is None
        assert td.hold is None
        assert td.double_tap is None
        assert td.tap_then_hold is None


def _vial_data_with_macros(macros: list) -> dict:
    return {"layout": [[["KC_A"] * 60]], "version": 1, "macro": macros}


class TestParseVialMacros:
    """Tests that _parse_vial extracts top-level macro entries."""

    def test_no_macro_key_yields_empty(self):
        data = {"layout": [[["KC_A"] * 60]], "version": 1}
        result = _parse_vial(data)
        assert result.macros == ()

    def test_empty_macro_entry(self):
        data = _vial_data_with_macros([[]])
        result = _parse_vial(data)
        assert result.macros == (SvalboardMacro[str](id="0"),)

    def test_single_keycode_tap_action(self):
        data = _vial_data_with_macros([[["tap", "KC_A"]]])
        result = _parse_vial(data)
        assert result.macros == (
            SvalboardMacro[str](
                id="0",
                actions=(
                    SvalboardMacroAction[str](kind=SvalboardMacroActionKind.TAP, keys=("KC_A",)),
                ),
            ),
        )

    def test_multi_keycode_action(self):
        data = _vial_data_with_macros([[["up", "KC_E", "KC_2"]]])
        result = _parse_vial(data)
        action = result.macros[0].actions[0]
        assert action.kind is SvalboardMacroActionKind.UP
        assert action.keys == ("KC_E", "KC_2")

    def test_text_action(self):
        data = _vial_data_with_macros([[["text", ";qj"]]])
        result = _parse_vial(data)
        action = result.macros[0].actions[0]
        assert action.kind is SvalboardMacroActionKind.TEXT
        assert action.text == ";qj"
        assert action.keys == ()

    def test_delay_action(self):
        data = _vial_data_with_macros([[["delay", 30]]])
        result = _parse_vial(data)
        action = result.macros[0].actions[0]
        assert action.kind is SvalboardMacroActionKind.DELAY
        assert action.duration_ms == 30
        assert action.keys == ()

    def test_mixed_action_sequence(self):
        data = _vial_data_with_macros(
            [
                [
                    ["down", "KC_E"],
                    ["delay", 30],
                    ["down", "KC_1"],
                    ["delay", 30],
                    ["up", "KC_E", "KC_1"],
                ]
            ]
        )
        result = _parse_vial(data)
        kinds = [a.kind for a in result.macros[0].actions]
        assert kinds == [
            SvalboardMacroActionKind.DOWN,
            SvalboardMacroActionKind.DELAY,
            SvalboardMacroActionKind.DOWN,
            SvalboardMacroActionKind.DELAY,
            SvalboardMacroActionKind.UP,
        ]
        assert result.macros[0].actions[4].keys == ("KC_E", "KC_1")

    def test_multiple_macros_get_indexed_ids(self):
        data = _vial_data_with_macros(
            [
                [["tap", "KC_A"]],
                [],
                [["text", "hi"]],
            ]
        )
        result = _parse_vial(data)
        assert [m.id for m in result.macros] == ["0", "1", "2"]
        assert result.macros[1].actions == ()


class TestParseKeybardTapDance:
    """Tests that _parse_keybard extracts top-level tapdances entries."""

    def test_no_tapdances_key_yields_empty(self):
        data = {"keymap": [["KC_A"] * 60]}
        result = _parse_keybard(data)
        assert result.tap_dances == ()

    def test_single_tap_dance(self):
        data = {
            "keymap": [["KC_A"] * 60],
            "tapdances": [
                {
                    "tdid": 0,
                    "tap": "TO(0)",
                    "hold": "MO(3)",
                    "doubletap": "KC_NO",
                    "taphold": "KC_NO",
                    "tapms": 200,
                }
            ],
        }
        result = _parse_keybard(data)
        assert result.tap_dances == (
            SvalboardTapDance[str](
                id="0",
                tap="TO(0)",
                hold="MO(3)",
                double_tap=None,
                tap_then_hold=None,
                tapping_term=200,
            ),
        )

    def test_kc_no_maps_to_none(self):
        data = {
            "keymap": [["KC_A"] * 60],
            "tapdances": [
                {
                    "tdid": 5,
                    "tap": "KC_NO",
                    "hold": "KC_NO",
                    "doubletap": "KC_NO",
                    "taphold": "KC_NO",
                    "tapms": 200,
                }
            ],
        }
        result = _parse_keybard(data)
        td = result.tap_dances[0]
        assert td.id == "5"
        assert td.tap is None
        assert td.hold is None
        assert td.double_tap is None
        assert td.tap_then_hold is None

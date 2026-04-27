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
    _detect_format_from_path,
    _detect_keymap_from_json,
    _get_c2json_layers,
    _get_keybard_layers,
    _get_vial_layers,
    load_keymap,
    load_keymap_file,
    load_keymap_from_stdin,
    load_keymap_json,
)
from skim.domain.domain_types import KeymapType


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


class TestGetVialLayers:
    """Tests for _get_vial_layers function."""

    def test_missing_layout_key_raises(self):
        """Missing 'layout' key raises ValueError."""
        with pytest.raises(ValueError, match="Missing 'layout' key"):
            _get_vial_layers({"other": "data"})

    def test_layout_not_list_raises(self):
        """Non-list 'layout' raises ValueError."""
        with pytest.raises(ValueError, match="'layout' must be a list"):
            _get_vial_layers({"layout": "not a list"})


class TestGetKeybardLayers:
    """Tests for _get_keybard_layers function."""

    def test_missing_keymap_key_raises(self):
        """Missing 'keymap' key raises ValueError."""
        with pytest.raises(ValueError, match="Missing 'keymap' key"):
            _get_keybard_layers({"other": "data"})

    def test_keymap_not_list_raises(self):
        """Non-list 'keymap' raises ValueError."""
        with pytest.raises(ValueError, match="'keymap' must be a list"):
            _get_keybard_layers({"keymap": "not a list"})


class TestGetC2jsonLayers:
    """Tests for _get_c2json_layers function."""

    def test_missing_layers_key_raises(self):
        """Missing 'layers' key raises ValueError."""
        with pytest.raises(ValueError, match="Missing 'layers' key"):
            _get_c2json_layers({"other": "data"})

    def test_layers_not_list_raises(self):
        """Non-list 'layers' raises ValueError."""
        with pytest.raises(ValueError, match="'layers' must be a list"):
            _get_c2json_layers({"layers": "not a list"})

    def test_layer_item_not_list_raises(self):
        """Non-list layer item raises ValueError."""
        with pytest.raises(ValueError, match="Layer 0 must be a list"):
            _get_c2json_layers({"layers": ["not a list"]})

    def test_multiple_invalid_layers_reports_first(self):
        """Reports first invalid layer."""
        with pytest.raises(ValueError, match="Layer 1 must be a list"):
            _get_c2json_layers({"layers": [[], "not a list"]})


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
        assert len(result) == 1  # One layer

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
            assert len(result) == 1

    def test_invalid_json_from_stdin_raises(self):
        """Invalid JSON from stdin raises ValueError."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = "not valid json"
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_keymap_from_stdin()


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

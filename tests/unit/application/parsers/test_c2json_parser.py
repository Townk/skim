"""Unit tests for C2JsonParser."""

import json

import pytest

from skim.application.parsers.c2json_parser import C2JsonParser


class TestC2JsonParser:
    """Test parsing of QMK c2json format."""

    def test_parse_valid_c2json(self):
        """Parse valid c2json content."""
        data = {
            "keyboard": "svalboard",
            "keymap": "test",
            "layout": "LAYOUT",
            "layers": [["KC_A", "KC_B", "KC_C"], ["KC_1", "KC_2", "KC_3"]],
        }
        json_content = json.dumps(data)

        parser = C2JsonParser()
        result = parser.parse(json_content)

        assert len(result) == 2
        assert result[0] == ["KC_A", "KC_B", "KC_C"]
        assert result[1] == ["KC_1", "KC_2", "KC_3"]

    def test_parse_invalid_json(self):
        """Handle invalid JSON syntax."""
        parser = C2JsonParser()

        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.parse("{invalid_json}")

    def test_missing_layers_key(self):
        """Handle missing 'layers' key."""
        data = {"keyboard": "svalboard"}
        json_content = json.dumps(data)

        parser = C2JsonParser()

        with pytest.raises(ValueError, match="Missing 'layers' key"):
            parser.parse(json_content)

    def test_layers_not_a_list(self):
        """Handle 'layers' key not being a list."""
        data = {"layers": "not_a_list"}
        json_content = json.dumps(data)

        parser = C2JsonParser()

        with pytest.raises(ValueError, match="'layers' must be a list"):
            parser.parse(json_content)

    def test_layer_item_not_a_list(self):
        """Handle layer items not being lists."""
        data = {"layers": [["KC_A"], "not_a_list"]}
        json_content = json.dumps(data)

        parser = C2JsonParser()

        with pytest.raises(ValueError, match="Layer 1 must be a list"):
            parser.parse(json_content)

    def test_empty_layers(self):
        """Handle empty layers list."""
        data = {"layers": []}
        json_content = json.dumps(data)

        parser = C2JsonParser()
        result = parser.parse(json_content)

        assert result == []

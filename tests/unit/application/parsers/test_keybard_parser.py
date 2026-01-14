"""Unit tests for KeybardParser."""

import json

import pytest

from skim.application.parsers.keybard_parser import KeybardParser


class TestKeybardParser:
    """Test parsing of Keybard .kbi format."""

    def test_parse_valid_keybard(self):
        """Parse valid keybard content."""
        # Minimal valid structure: "keymap" containing layers (lists of 60 keys)
        # We simulate a layer with known keys "00".."59"
        layer = [f"{i:02d}" for i in range(60)]

        data = {"layers": 1, "keymap": [layer]}
        json_content = json.dumps(data)

        parser = KeybardParser()
        result = parser.parse(json_content)

        assert len(result) == 1
        assert len(result[0]) == 60
        # Check if keys are present
        assert "00" in result[0]
        # We verify result is a list, trusting LayerAdaptor for order
        assert isinstance(result[0], list)

    def test_parse_invalid_json(self):
        """Handle invalid JSON syntax."""
        parser = KeybardParser()

        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.parse("{invalid_json}")

    def test_missing_keymap_key(self):
        """Handle missing 'keymap' key."""
        data = {"layers": 1}
        json_content = json.dumps(data)

        parser = KeybardParser()

        with pytest.raises(ValueError, match="Missing 'keymap' key"):
            parser.parse(json_content)

    def test_keymap_not_a_list(self):
        """Handle 'keymap' key not being a list."""
        data = {"keymap": "not_a_list"}
        json_content = json.dumps(data)

        parser = KeybardParser()

        with pytest.raises(ValueError, match="'keymap' must be a list"):
            parser.parse(json_content)

    def test_empty_keymap(self):
        """Handle empty keymap list."""
        data = {"keymap": []}
        json_content = json.dumps(data)

        parser = KeybardParser()
        result = parser.parse(json_content)

        assert result == []

    def test_extract_metadata_invalid_json(self):
        """Handle invalid JSON in extract_metadata."""
        parser = KeybardParser()
        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.extract_metadata("{invalid}")

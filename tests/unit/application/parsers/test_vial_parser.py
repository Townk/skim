"""Unit tests for VialParser."""

import json

import pytest

from skim.application.parsers.vial_parser import VialParser


class TestVialParser:
    """Test parsing of Vial .vil format."""

    def test_parse_valid_vial(self):
        """Parse valid vial content."""
        # Minimal valid structure: 1 layer, 10 clusters of 6 keys (60 keys total)
        # We use a simple sequential layout to verify transformation
        # 60 keys: "00".."59"
        # Vial format organizes them into clusters
        # LayerAdaptor expects 60 keys per layer after flattening

        # Create a mock layer structure: 10 clusters of 6 keys
        layer = []
        for i in range(10):
            cluster = [f"{i * 6 + j:02d}" for j in range(6)]
            layer.append(cluster)

        data = {"version": 1, "layout": [layer]}
        json_content = json.dumps(data)

        parser = VialParser()
        result = parser.parse(json_content)

        assert len(result) == 1
        assert len(result[0]) == 60
        # Check if one key is present to verify basic parsing
        assert "00" in result[0]
        # We trust LayerAdaptor for the exact ordering, but we can check format
        assert isinstance(result[0], list)

    def test_parse_invalid_json(self):
        """Handle invalid JSON syntax."""
        parser = VialParser()

        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.parse("{invalid_json}")

    def test_missing_layout_key(self):
        """Handle missing 'layout' key."""
        data = {"version": 1}
        json_content = json.dumps(data)

        parser = VialParser()

        with pytest.raises(ValueError, match="Missing 'layout' key"):
            parser.parse(json_content)

    def test_layout_not_a_list(self):
        """Handle 'layout' key not being a list."""
        data = {"layout": "not_a_list"}
        json_content = json.dumps(data)

        parser = VialParser()

        with pytest.raises(ValueError, match="'layout' must be a list"):
            parser.parse(json_content)

    def test_empty_layout(self):
        """Handle empty layout list."""
        data = {"layout": []}
        json_content = json.dumps(data)

        parser = VialParser()
        result = parser.parse(json_content)

        assert result == []

"""Test suite for keymap data models."""

import pytest

from skim.domain.models import KeymapData, Layer


class TestLayer:
    def test_layer_creation_with_all_fields(self):
        labels = [["A", "B", "C", "D", "E", "F"] for _ in range(10)]
        colors = [
            "#FF0000",
            "#00FF00",
            "#0000FF",
            "#FFFF00",
            "#FF00FF",
            "#00FFFF",
            "#FFFFFF",
        ]
        layer_toggles = [[None, None, None, None, None, None] for _ in range(10)]

        layer = Layer(
            name="Test Layer",
            labels=labels,
            colors=colors,
            primary_color=2,
            secondary_color=6,
            layer_toggles=layer_toggles,
        )

        assert layer.name == "Test Layer"
        assert len(layer.labels) == 10
        assert len(layer.colors) == 7
        assert layer.primary_color == 2
        assert layer.secondary_color == 6

    def test_layer_validates_color_count(self):
        labels = [["A"] * 6] * 10
        colors = ["#FF0000", "#00FF00"]
        layer_toggles = [[None] * 6] * 10

        with pytest.raises(ValueError, match="must have exactly 7 colors"):
            Layer(
                name="Bad Layer",
                labels=labels,
                colors=colors,
                primary_color=0,
                secondary_color=1,
                layer_toggles=layer_toggles,
            )

    def test_layer_validates_labels_structure(self):
        labels = [["A"] * 5] * 10
        colors = ["#FF0000"] * 7

        with pytest.raises(ValueError, match="must have 10 rows"):
            Layer(
                name="Bad Layer",
                labels=labels,
                colors=colors,
                primary_color=0,
                secondary_color=1,
                layer_toggles=[[None] * 5] * 9,
            )

    def test_layer_to_dict(self):
        labels = [["A", "B", "C", "D", "E", "F"] for _ in range(10)]
        colors = ["#FF0000"] * 7
        layer_toggles = [[None, None, None, None, None, None] for _ in range(10)]

        layer = Layer(
            name="Test",
            labels=labels,
            colors=colors,
            primary_color=2,
            secondary_color=6,
            layer_toggles=layer_toggles,
        )

        result = layer.to_dict()
        assert result["name"] == "Test"
        assert "labels" in result
        assert "colors" in result
        assert result["primaryColor"] == 2
        assert result["secondaryColor"] == 6


class TestKeymapData:
    def test_keymap_data_creation(self):
        layer1 = Layer(
            name="Layer 1",
            labels=[["A"] * 6] * 10,
            colors=["#FF0000"] * 7,
            primary_color=2,
            secondary_color=6,
            layer_toggles=[[None] * 6] * 10,
        )
        layer2 = Layer(
            name="Layer 2",
            labels=[["B"] * 6] * 10,
            colors=["#00FF00"] * 7,
            primary_color=2,
            secondary_color=6,
            layer_toggles=[[None] * 6] * 10,
        )

        keymap = KeymapData(layers=[layer1, layer2])
        assert len(keymap.layers) == 2
        assert keymap.layers[0].name == "Layer 1"

    def test_keymap_data_to_dict(self):
        layer = Layer(
            name="Test",
            labels=[["A"] * 6] * 10,
            colors=["#FF0000"] * 7,
            primary_color=2,
            secondary_color=6,
            layer_toggles=[[None] * 6] * 10,
        )

        keymap = KeymapData(layers=[layer])
        result = keymap.to_dict()

        assert "layers" in result
        assert len(result["layers"]) == 1
        assert result["layers"][0]["name"] == "Test"

    def test_keymap_data_get_layer_by_index(self):
        layer1 = Layer(
            name="Layer 1",
            labels=[["A"] * 6] * 10,
            colors=["#FF0000"] * 7,
            primary_color=2,
            secondary_color=6,
            layer_toggles=[[None] * 6] * 10,
        )
        layer2 = Layer(
            name="Layer 2",
            labels=[["B"] * 6] * 10,
            colors=["#00FF00"] * 7,
            primary_color=2,
            secondary_color=6,
            layer_toggles=[[None] * 6] * 10,
        )

        keymap = KeymapData(layers=[layer1, layer2])
        assert keymap.get_layer(0).name == "Layer 1"
        assert keymap.get_layer(1).name == "Layer 2"
        assert keymap.get_layer(2) is None

    def test_keymap_data_layer_count(self):
        layers = [
            Layer(
                name=f"Layer {i}",
                labels=[["A"] * 6] * 10,
                colors=["#FF0000"] * 7,
                primary_color=2,
                secondary_color=6,
                layer_toggles=[[None] * 6] * 10,
            )
            for i in range(5)
        ]

        keymap = KeymapData(layers=layers)
        assert keymap.layer_count() == 5

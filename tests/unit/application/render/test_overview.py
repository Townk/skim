# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import drawsvg as draw
import pytest

from skim.application.render.overview import draw_overview
from skim.data.config import (
    Keyboard,
    KeyboardLayer,
    LayerColor,
    Output,
    Palette,
    SkimConfig,
    Style,
)
from skim.data.keyboard import SvalboardKeymap, SvalboardLayout
from skim.domain.domain_types import SvalboardTargetKey


def _make_config(num_layers: int = 3, width: float = 1600) -> SkimConfig:
    layers_cfg = tuple(
        KeyboardLayer(index=i, label=str(i), name=f"Layer{i}") for i in range(num_layers)
    )
    layer_colors = tuple(
        LayerColor(base_color=f"#{(i + 1) * 30:02x}5050") for i in range(num_layers)
    )
    return SkimConfig(
        keyboard=Keyboard(layers=layers_cfg),
        output=Output(
            style=Style(palette=Palette(layers=layer_colors)),
        ),
    )


def _make_keymap(num_layers: int = 3) -> SvalboardKeymap[SvalboardTargetKey]:
    layers = {}
    for layer_idx in range(num_layers):
        layer = SvalboardLayout.from_sequence(
            [SvalboardTargetKey(label=f"L{layer_idx}K{i}") for i in range(60)]
        )
        layers[layer_idx] = layer
    return SvalboardKeymap(layers=layers)


class TestDrawOverview:
    def test_returns_drawing(self):
        config = _make_config()
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        assert isinstance(result, draw.Drawing)

    def test_svg_contains_layers_heading(self):
        config = _make_config()
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        assert "LAYERS" in svg

    def test_svg_contains_layer_names(self):
        config = _make_config()
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        for i in range(3):
            assert f"LAYER{i}" in svg

    def test_svg_contains_variant_when_set(self):
        layers_cfg = (
            KeyboardLayer(index=0, label="0", name="Letters", variant="COLEMAK"),
            KeyboardLayer(index=1, label="1", name="Numbers"),
        )
        layer_colors = (
            LayerColor(base_color="#305050"),
            LayerColor(base_color="#605050"),
        )
        config = SkimConfig(
            keyboard=Keyboard(layers=layers_cfg),
            output=Output(style=Style(palette=Palette(layers=layer_colors))),
        )
        keymap = _make_keymap(2)
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        assert "COLEMAK" in svg

    def test_svg_contains_custom_keymap_title_when_set(self):
        config = _make_config()
        config = config.model_copy(
            update={"output": config.output.model_copy(update={"keymap_title": "My Custom Layout"})}
        )
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        assert "My Custom Layout" in svg

    def test_svg_uses_default_title_when_keymap_title_not_set(self):
        config = _make_config()
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        assert "Layers Layout" in svg

    def test_svg_contains_copyright_when_set(self):
        config = _make_config()
        config = config.model_copy(
            update={"output": config.output.model_copy(update={"copyright": "© 2026 Test"})}
        )
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        assert "© 2026 Test" in svg

    def test_svg_does_not_contain_copyright_when_not_set(self):
        config = _make_config()
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        assert "©" not in svg

    def test_svg_contains_thumbs_label(self):
        config = _make_config()
        keymap = _make_keymap()
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        assert "THUMBS" in svg


class TestOverviewConnectorLines:
    @pytest.mark.skip(reason="Connector line routing disabled pending design spec")
    def test_svg_contains_dashed_lines_for_layer_switching_keys(self):
        """When keys have layer_switch, dotted connector lines appear."""
        layers_cfg = (
            KeyboardLayer(index=0, label="0", name="Base"),
            KeyboardLayer(index=1, label="1", name="Nav"),
        )
        layer_colors = (
            LayerColor(base_color="#305050"),
            LayerColor(base_color="#605050"),
        )
        config = SkimConfig(
            keyboard=Keyboard(layers=layers_cfg),
            output=Output(
                style=Style(
                    palette=Palette(layers=layer_colors),
                    show_layer_indicators=True,
                )
            ),
        )

        # Create keymap where a key switches to layer 1
        keys_l0 = [SvalboardTargetKey(label=f"K{i}") for i in range(60)]
        # Make a finger key switch to layer 1 (e.g. key index 2 = left index east key)
        keys_l0[2] = SvalboardTargetKey(label="NAV", layer_switch=1)
        layer0 = SvalboardLayout.from_sequence(keys_l0)

        keys_l1 = [SvalboardTargetKey(label=f"N{i}") for i in range(60)]
        layer1 = SvalboardLayout.from_sequence(keys_l1)

        keymap = SvalboardKeymap(layers={0: layer0, 1: layer1})
        result = draw_overview(config, keymap)
        svg = result.as_svg()

        # Should contain dashed path elements
        assert "stroke-dasharray" in svg

    def test_no_connector_lines_when_no_layer_switches(self):
        """When no keys have layer_switch, no connector lines appear."""
        config = _make_config(2)
        keymap = _make_keymap(2)  # No layer_switch on any key
        result = draw_overview(config, keymap)
        svg = result.as_svg()
        assert "stroke-dasharray" not in svg

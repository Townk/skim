# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import pytest
import drawsvg as draw

from skim.data.config import (
    Keyboard,
    KeyboardFeatures,
    KeyboardLayer,
    LayerColor,
    Output,
    Palette,
    SkimConfig,
    Style,
)
from skim.data.keyboard import SvalboardKeymap, SvalboardLayout
from skim.domain.domain_types import SvalboardTargetKey
from skim.application.render.overview import draw_overview


def _make_config(num_layers: int = 3, width: float = 1600) -> SkimConfig:
    layers_cfg = tuple(
        KeyboardLayer(label=str(i), name=f"Layer{i}")
        for i in range(num_layers)
    )
    layer_colors = tuple(
        LayerColor(base_color=f"#{(i+1)*30:02x}5050")
        for i in range(num_layers)
    )
    return SkimConfig(
        keyboard=Keyboard(layers=layers_cfg),
        output=Output(
            style=Style(palette=Palette(layers=layer_colors)),
        ),
    )


def _make_keymap(num_layers: int = 3) -> SvalboardKeymap[SvalboardTargetKey]:
    layers = []
    for layer_idx in range(num_layers):
        layer = SvalboardLayout.from_sequence(
            [SvalboardTargetKey(label=f"L{layer_idx}K{i}") for i in range(60)]
        )
        layers.append(layer)
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
            assert f"Layer{i}" in svg

    def test_svg_contains_subtitle_when_set(self):
        layers_cfg = (
            KeyboardLayer(label="0", name="Letters", subtitle="COLEMAK"),
            KeyboardLayer(label="1", name="Numbers"),
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

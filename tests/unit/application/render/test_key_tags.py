# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
"""Layer images tag every key with its keymap position.

``<g data-key="N">`` wraps the shapes and label of the key at position
``N`` of the keymap's flat order, so a tool can find a key in the SVG
without knowing Skim's geometry. Every layer image tags each key it
draws, once, and each tag holds the label of that keymap position. Keys
it does not draw (double-south, unless ``keyboard.features.double_south``
is on) have no tag.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import drawsvg as draw
import pytest

from skim.application.keymap_generator import _get_config, _get_input_keymap, _resolve_keymap
from skim.application.loaders import load_keycode_mappings
from skim.application.render import draw_keymap
from skim.application.render.keymap_layer import KeymapLayer
from skim.application.render.primitives import Point
from skim.application.render.render_context import RenderContext, using_render_context
from skim.data import SkimConfig, SvalboardKeymap, SvalboardLayout
from skim.data.cli import InputFiles, KeymapGeneratorTargets
from skim.domain import SvalboardTargetKey

SAMPLE = Path("samples/keymaps/SvalCOLEMAKDHM.vil")
TAG = re.compile(r'<g data-key="(\d+)">(.*?)</g>', re.S)


def _render(*, reserve_space: bool = False) -> dict[str, str]:
    config = _get_config(None, use_system_fonts=True, keymap_for_defaults=SAMPLE)
    if reserve_space:
        style = config.output.style
        indicator = style.layer_indicator.model_copy(update={"reserve_space": True})
        output = config.output.model_copy(
            update={"style": style.model_copy(update={"layer_indicator": indicator})}
        )
        config = config.model_copy(update={"output": output})
    raw_keymap = _get_input_keymap(InputFiles(keymap=SAMPLE), config)
    targets = KeymapGeneratorTargets.from_args(("all",))
    keymap = _resolve_keymap(config, raw_keymap, targets)
    drawings = draw_keymap(
        config,
        keymap,
        targets,
        raw_keymap=raw_keymap,
        keycode_mappings=load_keycode_mappings(config.keycodes),
    )
    return {name: str(drawing.as_svg()) for name, drawing in drawings.items()}


@pytest.fixture(scope="module")
def rendered() -> dict[str, str]:
    return _render()


def _layer_images(rendered: dict[str, str]) -> dict[str, str]:
    images = {name: svg for name, svg in rendered.items() if name.startswith("keymap-layer-")}
    assert images, "the sample renders no layer images"
    return images


def test_every_layer_image_tags_each_drawn_key_once(rendered: dict[str, str]) -> None:
    # The sample has no double-south keys: finger keys 5, 11, ..., 47
    # (each cluster's sixth) are not drawn. All six thumb keys are.
    drawn = [i for i in range(60) if i >= 48 or i % 6 != 5]
    for name, svg in _layer_images(rendered).items():
        indices = [int(i) for i, _ in TAG.findall(svg)]
        assert sorted(indices) == drawn, name


def test_tags_follow_the_keymap_order(rendered: dict[str, str]) -> None:
    # SvalCOLEMAKDHM layer 0: right index center (0) is N, its north (1)
    # is L; left index center (24) is T; left index north (25) is P.
    svg = rendered["keymap-layer-0"]
    labels = {int(i): re.findall(r">([^<>]+)</t", body) for i, body in TAG.findall(svg)}
    assert labels[0] == ["N"]
    assert labels[1] == ["L"]
    assert labels[24] == ["T"]
    assert labels[25] == ["P"]


def test_the_overview_is_not_tagged(rendered: dict[str, str]) -> None:
    # The overview draws every layer at once; tags there would repeat.
    overview = rendered.get("keymap-overview")
    assert overview is not None
    assert "data-key" not in overview


def _key_outlines(svg: str) -> dict[int, str]:
    """Each tagged key's first shape, colours removed: where the key is drawn."""
    outlines: dict[int, str] = {}
    for index, body in TAG.findall(svg):
        shape = re.match(r"\s*<(\w+)([^>]*)>", body)
        assert shape is not None
        geometry = re.sub(r'\s(fill|stroke|opacity|fill-opacity)="[^"]*"', "", shape.group(2))
        outlines[int(index)] = shape.group(1) + geometry
    return outlines


def test_reserved_space_gives_every_layer_one_geometry() -> None:
    images = _layer_images(_render(reserve_space=True))
    outlines = [_key_outlines(svg) for svg in images.values()]
    assert len(outlines) > 1
    for other in outlines[1:]:
        assert other == outlines[0]


def _layer_outlines(
    layer: SvalboardLayout[SvalboardTargetKey], *, reserve_space: bool
) -> dict[int, str]:
    config = SkimConfig()
    style = config.output.style
    indicator = style.layer_indicator.model_copy(update={"reserve_space": reserve_space})
    output = config.output.model_copy(
        update={"style": style.model_copy(update={"layer_indicator": indicator})}
    )
    config = config.model_copy(update={"output": output})
    with using_render_context(RenderContext.build(config, SvalboardKeymap(layers={}))):
        component = KeymapLayer(layer=layer, qmk_index=0, target_content_w=1500)
        drawing = draw.Drawing(2000, 1000)
        component.draw_at(drawing, Point(0, 0))
    return _key_outlines(str(drawing.as_svg()))


PLAIN = SvalboardLayout.from_sequence([SvalboardTargetKey(label="x")] * 60)
BADGED = PLAIN.map(lambda key: replace(key, layer_switch=1))


def test_badges_move_the_keys_unless_space_is_reserved() -> None:
    # Without the reservation, a layer whose keys carry badges makes room
    # for them and its keys land elsewhere than a layer without badges:
    # the jump reserve_space exists to prevent.
    assert _layer_outlines(PLAIN, reserve_space=False) != _layer_outlines(
        BADGED, reserve_space=False
    )
    assert _layer_outlines(PLAIN, reserve_space=True) == _layer_outlines(BADGED, reserve_space=True)

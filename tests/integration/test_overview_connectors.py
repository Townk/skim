# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Integration: overview rendering with connectors uses the new algorithm."""

import re
from pathlib import Path

from skim.application.keymap_generator import (
    _get_config,
    _get_input_keymap,
    _resolve_keymap,
)
from skim.application.render import draw_keymap
from skim.data.cli import InputFiles, KeymapGeneratorTargets


def test_overview_renders_with_connectors_for_layer_trigger_keymap(tmp_path):
    """Sanity: rendering an overview with show_layer_indicators ON produces SVG with paths."""
    sample = Path("samples/keymaps/vial-sample.vil")
    config = _get_config(None, keymap_for_defaults=sample)
    new_style = config.output.style.model_copy(update={"show_layer_indicators": True})
    new_output = config.output.model_copy(update={"style": new_style})
    cfg = config.model_copy(update={"output": new_output})

    inputs = InputFiles(keymap=sample)
    keymap = _resolve_keymap(cfg, _get_input_keymap(inputs, cfg))
    drawings = draw_keymap(cfg, keymap, KeymapGeneratorTargets(overview=True))

    overview = drawings["keymap-overview"]
    out = tmp_path / "overview.svg"
    overview.save_svg(str(out))
    content = out.read_text()
    # Expect at least one connector path (dotted SVG path).
    assert re.search(r"<path[^>]+stroke-dasharray", content) is not None

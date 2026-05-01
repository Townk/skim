# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The combined macros + tap-dances image entry point.

Reduces to building a :func:`KeymapSpecialKeysDocument` (which
wraps both sections side-by-side in a Row inside the standard
chrome) and handing it to :func:`render`. All the layout logic
lives inside the composable.
"""

from __future__ import annotations

import drawsvg as draw

from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey

from .composable import render
from .keymap_document import KeymapSpecialKeysDocument
from .legend import all_macros, all_tap_dances
from .render_context import RenderContext, using_render_context


def draw_special_keys_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the combined special-keys image (macros left, tap-dances right)."""
    with using_render_context(RenderContext.build(config, keymap)):
        return render(
            KeymapSpecialKeysDocument(
                macros=all_macros(keymap.macros),
                tap_dances=all_tap_dances(keymap.tap_dances),
            )
        )


__all__ = ["draw_special_keys_image"]

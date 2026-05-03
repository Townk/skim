# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Overview image — public entry point.

The overview render lives entirely on the composable framework now:
:func:`draw_overview` is a thin wrapper over
:func:`keymap_overview.draw_overview_v2`. :class:`HeaderDims` and
:func:`compute_header_dims` are re-exported from
:mod:`keymap_overview` for backward compatibility with existing
imports (``Theme.resolve`` is the primary consumer).
"""

import drawsvg as draw

from skim.data import KeycodeMappings, SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey

from .keymap_overview import HeaderDims, compute_header_dims


def draw_overview(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
) -> draw.Drawing:
    """Generate the full overview SVG image for a multi-layer keymap.

    Thin wrapper over :func:`keymap_overview.draw_overview_v2`. The
    legacy imperative pipeline retired with the composable migration.
    """
    from .keymap_overview import draw_overview_v2

    return draw_overview_v2(
        config,
        keymap,
        raw_keymap=raw_keymap,
        keycode_mappings=keycode_mappings,
    )


__all__ = [
    "HeaderDims",
    "compute_header_dims",
    "draw_overview",
]

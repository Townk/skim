# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The combined macros + tap-dances image entry point.

The MACROS section sits on the left, the TAP-DANCE section on the
right, separated by ``geom.column_gap``. Falls back to a single
column when only one of the two sections has content.

This module is the only one that pulls together both per-section
modules (:mod:`macros` and :mod:`tap_dance`) — most renders only need
one or the other, so the side-by-side layout lives in its own file.
"""

from __future__ import annotations

import drawsvg as draw

from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey

from .keymap_document import BODY_SCALE, render
from .legend import _LegendGeometry, _td_name_column_width, all_macros, all_tap_dances
from .macros import MacroSection
from .primitives import Component, Row, Spacer
from .render_context import RenderContext, using_render_context
from .tap_dance import TapDanceSection


def draw_special_keys_image(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Render the combined special-keys image (macros left, tap-dances right).

    Mirrors the overview's two-column legend, just at the standalone scale.
    Falls back to a single column when only one section has content.
    """
    with using_render_context(RenderContext.build(config, keymap)) as ctx:
        macros = all_macros(keymap.macros)
        tap_dances = all_tap_dances(keymap.tap_dances)
        metrics = ctx.document_metrics
        # Bodies render at ``BODY_SCALE``; the static name-column
        # width and the cross-column gap are computed against the
        # scaled geom so the two columns keep their proportions.
        scaled_geom = _LegendGeometry.for_doc_width(metrics.doc_width * BODY_SCALE)

        target_content_w = metrics.doc_width - 2 * metrics.padding
        col_gap = scaled_geom.column_gap
        col_w = (target_content_w - col_gap) / 2 if macros and tap_dances else target_content_w

        sections: list[Component] = []
        if macros:
            sections.append(
                MacroSection(
                    macros=macros,
                    content_width=col_w,
                    width=col_w,
                    scale=BODY_SCALE,
                )
            )
        if tap_dances:
            # Pin the legacy ``_td_name_column_width`` so the combined image
            # keeps its overview-style fixed name column instead of the
            # dynamic sizing the standalone tap-dances image uses.
            sections.append(
                TapDanceSection(
                    tap_dances=tap_dances,
                    width=col_w,
                    scale=BODY_SCALE,
                    name_column_width=_td_name_column_width(scaled_geom, tap_dances),
                )
            )

        if not sections:
            body: Component = Spacer()
        elif len(sections) == 1:
            body = sections[0]
        else:
            body = Row([sections[0], Spacer(width=col_gap), sections[1]], align="top")

        return render(
            body=body,
            content_w=target_content_w,
            # Combined image has no single dominant section title, so the
            # footer keeps its natural size (matches the per-layer/overview).
            footer_section_title=None,
        )


__all__ = ["draw_special_keys_image"]

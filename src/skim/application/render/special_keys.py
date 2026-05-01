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

from .composable import Component, Row, Spacer
from .keymap_document import BODY_SCALE, LabeledSection, render
from .legend import _LegendGeometry, _td_name_column_width, all_macros, all_tap_dances
from .macros import MacroList
from .render_context import RenderContext, using_render_context
from .styling import derive_accent_line
from .tap_dance import TapDanceTable


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
        palette = ctx.theme.palette
        metrics = ctx.document_metrics
        # Bodies render at ``BODY_SCALE``; the static name-column
        # width and the cross-column gap are computed against the
        # scaled geom so the two columns keep their proportions.
        scaled_geom = _LegendGeometry.for_doc_width(metrics.doc_width * BODY_SCALE)
        macro_line = derive_accent_line(palette.macro_color)
        td_line = derive_accent_line(palette.tap_dance_color)

        target_content_w = metrics.doc_width - 2 * metrics.padding
        col_gap = scaled_geom.column_gap
        col_w = (target_content_w - col_gap) / 2 if macros and tap_dances else target_content_w

        sections: list[Component] = []
        if macros:
            sections.append(
                LabeledSection(
                    title="MACROS",
                    color=macro_line,
                    count=len(macros),
                    width=col_w,
                    body=MacroList(
                        macros=macros,
                        accent_fill=palette.macro_color,
                        accent_line=macro_line,
                        text_color=palette.text_color,
                        content_width=col_w,
                        scale=BODY_SCALE,
                    ),
                )
            )
        if tap_dances:
            # Pin the legacy ``_td_name_column_width`` so the combined image
            # keeps its overview-style fixed name column instead of the
            # dynamic sizing the standalone tap-dances image uses.
            td_table = TapDanceTable(
                tap_dances=tap_dances,
                accent_fill=palette.tap_dance_color,
                accent_line=td_line,
                text_color=palette.text_color,
                scale=BODY_SCALE,
                name_column_width=_td_name_column_width(scaled_geom, tap_dances),
            )
            sections.append(
                LabeledSection(
                    title="TAP-DANCE",
                    color=td_line,
                    count=len(tap_dances),
                    width=col_w,
                    body=td_table,
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

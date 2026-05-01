# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.tap_dance."""

from contextlib import contextmanager

from skim.application.render.adjustable_text import measure_text_width
from skim.application.render.render_context import RenderContext, using_render_context
from skim.application.render.tap_dance import (
    TapDanceMetrics,
    TapDanceTable,
    _resolve_name_column_width,
)
from skim.application.render.text import Font
from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTapDance, SvalboardTargetKey


def _measure(text: str, font_size: float) -> float:
    """Rendered width of ``text`` at ``font_size`` via the canonical
    PIL-accurate path the section's name-column resolver uses.
    """
    return measure_text_width(text, Font.FINGER_KEY, font_size)


@contextmanager
def _ctx_for_doc_width(doc_width: float):
    """Push a :class:`RenderContext` whose ``layout.width`` equals ``doc_width``.

    ``TapDanceTable`` is now a context-aware composable; tests that
    construct it directly need an active :func:`using_render_context`
    block. Tests that want to exercise the table at ``doc_width=W``
    pass ``W`` as the layout width and let the composable derive its
    own geometry — same path the real renders take.
    """
    config = SkimConfig.model_validate({"output": {"layout": {"width": doc_width}}})
    keymap = SvalboardKeymap(layers={})
    with using_render_context(RenderContext.build(config, keymap)) as ctx:
        yield ctx


# ---------------------------------------------------------------------------
# Dynamic name-column sizing for TapDanceTable
# ---------------------------------------------------------------------------


def _td(id_: str, name: str | None = None) -> SvalboardTapDance[SvalboardTargetKey]:
    return SvalboardTapDance(id=id_, name=name)


class TestResolveNameColumnWidth:
    """Per-row ellipsis truncation now happens inside :func:`AdjustableText`,
    so this helper only computes the column width the table reserves; the
    rendered names are no longer mutated up front.
    """

    def test_collapses_to_zero_when_no_names(self):
        metrics = TapDanceMetrics.for_doc_width(1600.0)
        cells_block_w = metrics.row_content_indent_gap + 4 * metrics.cell_w + 3 * metrics.cell_gap
        width = _resolve_name_column_width(
            tap_dances=[_td("0"), _td("1")],
            metrics=metrics,
            cells_block_w=cells_block_w,
            max_width=10_000,
        )
        assert width == 0.0

    def test_picks_longest_natural_when_budget_allows(self):
        metrics = TapDanceMetrics.for_doc_width(1600.0)
        # Cells block: four cells with three explicit ``cell_gap``s
        # between them, plus the leading ``row_content_indent_gap``.
        cells_block_w = metrics.row_content_indent_gap + 4 * metrics.cell_w + 3 * metrics.cell_gap
        tds = [_td("0", name="short"), _td("1", name="much longer name")]
        long_natural = _measure("much longer name", metrics.name_font_size)

        width = _resolve_name_column_width(
            tap_dances=tds,
            metrics=metrics,
            cells_block_w=cells_block_w,
            max_width=10_000,  # plenty of slack
        )

        # name_column_width = leading + text + symmetric trailing gap.
        assert width == 2 * metrics.name_gap + long_natural

    def test_caps_column_at_budget_when_longest_overflows(self):
        metrics = TapDanceMetrics.for_doc_width(1600.0)
        cells_block_w = metrics.row_content_indent_gap + 4 * metrics.cell_w + 3 * metrics.cell_gap
        long_name = "the quick brown fox jumps over the lazy dog " * 4
        tds = [_td("0", name="short"), _td("1", name=long_name)]

        # Budget so tight the long name MUST overflow; chip + cells +
        # gaps consume most of it.
        natural_long_w = _measure(long_name, metrics.name_font_size)
        max_width = (
            metrics.chip_width
            + metrics.name_gap
            + metrics.name_gap  # trailing gap
            + cells_block_w
            + (natural_long_w / 4)  # only a quarter of the natural name width
        )
        width = _resolve_name_column_width(
            tap_dances=tds,
            metrics=metrics,
            cells_block_w=cells_block_w,
            max_width=max_width,
        )

        # name_column_width is capped at max budget — leading + text +
        # trailing. AdjustableText handles per-row ellipsis truncation
        # at render time.
        expected_text_w = max_width - metrics.chip_width - 2 * metrics.name_gap - cells_block_w
        assert width == 2 * metrics.name_gap + expected_text_w


# ---------------------------------------------------------------------------
# TapDanceTable end-to-end
# ---------------------------------------------------------------------------


class TestTapDanceTable:
    def test_table_size_caps_at_max_width(self):
        long_name = "the quick brown fox " * 20
        tds = [_td("0", name=long_name)]

        # Tight budget — table must cap and truncate.
        max_width = 600.0
        with _ctx_for_doc_width(1600.0):
            table = TapDanceTable(
                tap_dances=tds,
                accent_fill="#000",
                accent_line="#000",
                text_color="#000",
                max_width=max_width,
            )
        assert table.size.width <= max_width

    def test_table_natural_width_when_names_short(self):
        metrics = TapDanceMetrics.for_doc_width(1600.0)
        tds = [_td("0", name="short")]
        # Budget far larger than the table needs — width should be the
        # natural snug width, not the full budget.
        with _ctx_for_doc_width(1600.0):
            table = TapDanceTable(
                tap_dances=tds,
                accent_fill="#000",
                accent_line="#000",
                text_color="#000",
                max_width=10_000,
            )
        # Natural snug = chip + name area (with symmetric padding) +
        # cells block. The cells block is four cells with three
        # explicit ``cell_gap``s between them — same rhythm as the
        # macro section's pill row.
        natural = _measure("short", metrics.name_font_size)
        expected = (
            metrics.chip_width
            + 2 * metrics.name_gap  # leading + trailing
            + natural
            + metrics.row_content_indent_gap
            + 4 * metrics.cell_w
            + 3 * metrics.cell_gap
        )
        assert abs(table.size.width - expected) < 0.01

    def test_table_collapses_name_column_when_no_names(self):
        metrics = TapDanceMetrics.for_doc_width(1600.0)
        tds = [_td("0"), _td("1")]
        with _ctx_for_doc_width(1600.0):
            table = TapDanceTable(
                tap_dances=tds,
                accent_fill="#000",
                accent_line="#000",
                text_color="#000",
                max_width=10_000,
            )
        # No names — chip flush against the cell block (which ends
        # at the last cell's right edge, no trailing slack).
        expected = (
            metrics.chip_width
            + metrics.row_content_indent_gap
            + 4 * metrics.cell_w
            + 3 * metrics.cell_gap
        )
        assert abs(table.size.width - expected) < 0.01

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.legend_components."""

from contextlib import contextmanager

from skim.application.render.legend import _LegendGeometry
from skim.application.render.legend_components import (
    _ELLIPSIS,
    TapDanceTable,
    _measure_text_width,
    _resolve_name_column,
    _truncate_with_ellipsis,
)
from skim.application.render.render_context import RenderContext, using_render_context
from skim.data import SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTapDance, SvalboardTargetKey


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
# Truncation primitives
# ---------------------------------------------------------------------------


class TestTruncateWithEllipsis:
    def test_returns_input_when_already_fits(self):
        result = _truncate_with_ellipsis("short", font_size=12, max_width=10_000)
        assert result == "short"

    def test_returns_empty_when_max_width_zero(self):
        assert _truncate_with_ellipsis("anything", font_size=12, max_width=0) == ""

    def test_returns_empty_when_input_empty(self):
        assert _truncate_with_ellipsis("", font_size=12, max_width=100) == ""

    def test_appends_ellipsis_when_overflow(self):
        text = "the quick brown fox jumps over the lazy dog"
        natural = _measure_text_width(text, 12)
        # Cap at half the natural width to force truncation.
        result = _truncate_with_ellipsis(text, font_size=12, max_width=natural / 2)
        assert result.endswith(_ELLIPSIS)
        assert len(result) < len(text) + len(_ELLIPSIS)

    def test_truncated_output_fits_within_max_width(self):
        text = "the quick brown fox jumps over the lazy dog"
        natural = _measure_text_width(text, 12)
        cap = natural / 2
        result = _truncate_with_ellipsis(text, font_size=12, max_width=cap)
        assert _measure_text_width(result, 12) <= cap

    def test_returns_just_ellipsis_when_only_room_for_it(self):
        # Pick a max_width that's larger than the ellipsis itself but
        # smaller than ellipsis + any real glyph.
        ellipsis_w = _measure_text_width(_ELLIPSIS, 12)
        result = _truncate_with_ellipsis("anything", font_size=12, max_width=ellipsis_w + 0.1)
        assert result == _ELLIPSIS


# ---------------------------------------------------------------------------
# Dynamic name-column sizing for TapDanceTable
# ---------------------------------------------------------------------------


def _td(id_: str, name: str | None = None) -> SvalboardTapDance[SvalboardTargetKey]:
    return SvalboardTapDance(id=id_, name=name)


class TestResolveNameColumn:
    def test_collapses_to_zero_when_no_names(self):
        geom = _LegendGeometry.for_doc_width(1600.0)
        cells_block_w = 4 * geom.td_cell_w + geom.row_content_indent_gap
        width, adjusted = _resolve_name_column(
            tap_dances=[_td("0"), _td("1")],
            geom=geom,
            cells_block_w=cells_block_w,
            max_width=10_000,
        )
        assert width == 0.0
        assert [td.name for td in adjusted] == [None, None]

    def test_picks_longest_natural_when_budget_allows(self):
        geom = _LegendGeometry.for_doc_width(1600.0)
        # Effective cells block extent — last inner rect's right edge,
        # not the slot's right edge. ``TapDanceTable`` passes this
        # value through.
        inner_w = geom.td_cell_inner_w
        cells_block_w = (
            geom.row_content_indent_gap + 4 * geom.td_cell_w - (geom.td_cell_w - inner_w) / 2.0
        )
        tds = [_td("0", name="short"), _td("1", name="much longer name")]
        long_natural = _measure_text_width("much longer name", geom.td_name_font_size)

        width, adjusted = _resolve_name_column(
            tap_dances=tds,
            geom=geom,
            cells_block_w=cells_block_w,
            max_width=10_000,  # plenty of slack
        )

        # name_column_width = leading + text + symmetric trailing gap.
        assert width == 2 * geom.tag_name_gap + long_natural
        # Names untouched when they fit.
        assert [td.name for td in adjusted] == ["short", "much longer name"]

    def test_truncates_longest_when_budget_caps_below_natural(self):
        geom = _LegendGeometry.for_doc_width(1600.0)
        inner_w = geom.td_cell_inner_w
        cells_block_w = (
            geom.row_content_indent_gap + 4 * geom.td_cell_w - (geom.td_cell_w - inner_w) / 2.0
        )
        long_name = "the quick brown fox jumps over the lazy dog " * 4
        tds = [_td("0", name="short"), _td("1", name=long_name)]

        # Budget so tight the long name MUST truncate; chip + cells +
        # gaps consume most of it.
        natural_long_w = _measure_text_width(long_name, geom.td_name_font_size)
        max_width = (
            geom.tag_w
            + geom.tag_name_gap
            + geom.tag_name_gap  # trailing gap
            + cells_block_w
            + (natural_long_w / 4)  # only a quarter of the natural name width
        )
        width, adjusted = _resolve_name_column(
            tap_dances=tds,
            geom=geom,
            cells_block_w=cells_block_w,
            max_width=max_width,
        )

        # name_column_width is capped at max budget — leading + text +
        # trailing.
        expected_text_w = max_width - geom.tag_w - 2 * geom.tag_name_gap - cells_block_w
        assert width == 2 * geom.tag_name_gap + expected_text_w
        # Long name truncated; short name preserved
        assert adjusted[0].name == "short"
        assert adjusted[1].name is not None
        assert adjusted[1].name.endswith(_ELLIPSIS)
        assert adjusted[1].name != long_name


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
        geom = _LegendGeometry.for_doc_width(1600.0)
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
        # cells block, where the cells block ends at the last inner
        # rect's right edge (not the cell slot's right edge).
        inner_w = geom.td_cell_inner_w
        natural = _measure_text_width("short", geom.td_name_font_size)
        expected = (
            geom.tag_w
            + 2 * geom.tag_name_gap  # leading + trailing
            + natural
            + geom.row_content_indent_gap
            + 4 * geom.td_cell_w
            - (geom.td_cell_w - inner_w) / 2.0
        )
        assert abs(table.size.width - expected) < 0.01

    def test_table_collapses_name_column_when_no_names(self):
        geom = _LegendGeometry.for_doc_width(1600.0)
        tds = [_td("0"), _td("1")]
        with _ctx_for_doc_width(1600.0):
            table = TapDanceTable(
                tap_dances=tds,
                accent_fill="#000",
                accent_line="#000",
                text_color="#000",
                max_width=10_000,
            )
        # No names — chip flush against the cell block (and the cells
        # block ends at the last inner rect's right edge).
        inner_w = geom.td_cell_inner_w
        expected = (
            geom.tag_w
            + geom.row_content_indent_gap
            + 4 * geom.td_cell_w
            - (geom.td_cell_w - inner_w) / 2.0
        )
        assert abs(table.size.width - expected) < 0.01

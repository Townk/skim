"""Unit tests for skim.application.render.legend."""

import drawsvg as draw

from skim.application.render.legend import (
    ACTION_KEY_PRE_GAP,
    ACTION_KEY_STRIP_HEIGHT,
    CONTENT_STRIP_HEIGHT,
    HEADER_STRIP_HEIGHT,
    MACRO_COLUMN_HEADER_HEIGHT,
    SECTION_HEADER_HEIGHT,
    TD_HEADER_HEIGHT,
    TD_ROW_GAP,
    TD_ROW_HEIGHT,
    _macro_section_height,
    all_macros,
    all_tap_dances,
    build_action_glyph,
    build_macro_column_header,
    build_macro_row,
    build_tap_dance_column_header,
    build_tap_dance_row,
    collect_used_ids,
    macro_row_height,
    plan_layout,
    resolve_macros,
    resolve_tap_dances,
    tap_dance_section_height,
)
from skim.data import SvalboardLayout
from skim.domain import (
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardMacroActionKind,
    SvalboardTapDance,
)
from skim.domain.domain_types import SvalboardTargetKey


def _layout_from_keys(keys: list[SvalboardTargetKey]) -> SvalboardLayout[SvalboardTargetKey]:
    """Build a SvalboardLayout from a flat 60-key list (test helper)."""
    return SvalboardLayout.from_sequence(keys)


def _macro(id_: str, name: str | None = None) -> SvalboardMacro:
    return SvalboardMacro(
        id=id_,
        actions=(SvalboardMacroAction(kind=SvalboardMacroActionKind.TAP, keys=()),),
        name=name,
    )


def _td(id_: str, name: str | None = None) -> SvalboardTapDance:
    return SvalboardTapDance(id=id_, name=name)


def test_collect_returns_empty_for_plain_layer():
    keys = [SvalboardTargetKey(label="A") for _ in range(60)]
    layer = _layout_from_keys(keys)
    macros, tap_dances = collect_used_ids(layer)
    assert macros == set()
    assert tap_dances == set()


def test_collect_picks_up_macro_ids():
    keys = [SvalboardTargetKey(label="A") for _ in range(60)]
    keys[0] = SvalboardTargetKey(label="M3", macro_id="3")
    keys[5] = SvalboardTargetKey(label="M3", macro_id="3")  # duplicate is collapsed
    keys[7] = SvalboardTargetKey(label="M5", macro_id="5")
    layer = _layout_from_keys(keys)
    macros, tap_dances = collect_used_ids(layer)
    assert macros == {"3", "5"}
    assert tap_dances == set()


def test_collect_picks_up_tap_dance_ids():
    keys = [SvalboardTargetKey(label="A") for _ in range(60)]
    keys[0] = SvalboardTargetKey(label="TD0", tap_dance_id="0")
    keys[10] = SvalboardTargetKey(label="TD7", tap_dance_id="7")
    layer = _layout_from_keys(keys)
    macros, tap_dances = collect_used_ids(layer)
    assert tap_dances == {"0", "7"}
    assert macros == set()


def test_collect_includes_transparent_fallthroughs():
    """Transparent keys whose ids were inherited from layer 0 still count."""
    keys = [SvalboardTargetKey(label="A") for _ in range(60)]
    keys[3] = SvalboardTargetKey(
        label="M3", macro_id="3", is_transparent=True
    )
    layer = _layout_from_keys(keys)
    macros, _ = collect_used_ids(layer)
    assert macros == {"3"}


def test_collect_picks_up_both_kinds_independently():
    keys = [SvalboardTargetKey(label="A") for _ in range(60)]
    keys[0] = SvalboardTargetKey(label="M0", macro_id="0")
    keys[1] = SvalboardTargetKey(label="TD1", tap_dance_id="1")
    layer = _layout_from_keys(keys)
    macros, tap_dances = collect_used_ids(layer)
    assert macros == {"0"}
    assert tap_dances == {"1"}


def test_resolve_macros_filters_to_used_ids_and_sorts_numerically():
    available = (_macro("0"), _macro("3"), _macro("10"), _macro("5"))
    used = {"3", "10", "5"}
    out = resolve_macros(used, available)
    assert [m.id for m in out] == ["3", "5", "10"]


def test_resolve_macros_lex_sort_for_named_ids():
    available = (_macro("ALPHA"), _macro("BETA"), _macro("GAMMA"))
    used = {"GAMMA", "ALPHA"}
    out = resolve_macros(used, available)
    assert [m.id for m in out] == ["ALPHA", "GAMMA"]


def test_resolve_macros_skips_unknown_ids():
    available = (_macro("0"),)
    used = {"0", "999"}
    out = resolve_macros(used, available)
    assert [m.id for m in out] == ["0"]


def test_resolve_macros_named_first():
    available = (
        _macro("0"),
        _macro("1", name="Print"),
        _macro("2"),
        _macro("3", name="Sign-off"),
    )
    used = {"0", "1", "2", "3"}
    out = resolve_macros(used, available)
    # Named first (id-sorted within group), then unnamed (id-sorted).
    assert [m.id for m in out] == ["1", "3", "0", "2"]


def test_resolve_tap_dances_same_rules():
    available = (_td("0"), _td("1"), _td("2"))
    used = {"0", "2"}
    out = resolve_tap_dances(used, available)
    assert [t.id for t in out] == ["0", "2"]


def test_plan_layout_neither_returns_none():
    assert plan_layout([], []) is None


def test_plan_layout_both_keeps_each_in_own_column():
    plan = plan_layout([_macro("0")], [_td("0")])
    assert plan is not None
    assert [m.id for m in plan.macro_left] == ["0"]
    assert [t.id for t in plan.tap_dance_left] == ["0"]


def test_plan_layout_only_macros_uses_left_column_only():
    macros = [_macro(str(i)) for i in range(5)]
    plan = plan_layout(macros, [])
    assert plan is not None
    # All macros stay in the left column; right side is empty.
    assert [m.id for m in plan.macro_left] == ["0", "1", "2", "3", "4"]
    assert plan.tap_dance_left == []


def test_plan_layout_only_tap_dances_uses_right_column():
    tds = [_td(str(i)) for i in range(3)]
    plan = plan_layout([], tds)
    assert plan is not None
    # All TDs stay in the (right-column) tap_dance_left list.
    assert [t.id for t in plan.tap_dance_left] == ["0", "1", "2"]
    assert plan.macro_left == []


def test_build_action_glyph_tap_returns_circle():
    g = build_action_glyph(SvalboardMacroActionKind.TAP, cx=10, cy=10, color="#000")
    # The glyph for TAP is a draw.Circle directly.
    assert isinstance(g, draw.Circle)


def test_build_action_glyph_for_each_kind_returns_some_element():
    for kind in SvalboardMacroActionKind:
        g = build_action_glyph(kind, cx=0, cy=0, color="#000")
        assert g is not None


def test_build_action_glyph_press_is_filled():
    """Press should be a filled drawing element (a down-triangle)."""
    g = build_action_glyph(SvalboardMacroActionKind.DOWN, cx=10, cy=10, color="#abc")
    # It's a draw.Lines (filled), not a Group.
    assert isinstance(g, draw.Lines)
    assert g.args.get("fill") == "#abc"


def test_build_action_glyph_delay_returns_group():
    """Delay is a clock face — multiple primitives → a Group."""
    g = build_action_glyph(SvalboardMacroActionKind.DELAY, cx=10, cy=10, color="#000")
    assert isinstance(g, draw.Group)


def _macro_with_actions(*kinds_and_keys) -> SvalboardMacro:
    """Helper: build a macro from (kind, *args) tuples.

    For TAP/DOWN/UP, args are key labels (one or more strings).
    For TEXT, args is one string.
    For DELAY, args is one int (duration_ms).
    """
    actions = []
    for kind, *rest in kinds_and_keys:
        if kind in (
            SvalboardMacroActionKind.TAP,
            SvalboardMacroActionKind.DOWN,
            SvalboardMacroActionKind.UP,
        ):
            keys = tuple(SvalboardTargetKey(label=k) for k in rest)
            actions.append(SvalboardMacroAction(kind=kind, keys=keys))
        elif kind == SvalboardMacroActionKind.TEXT:
            actions.append(SvalboardMacroAction(kind=kind, text=rest[0]))
        elif kind == SvalboardMacroActionKind.DELAY:
            actions.append(SvalboardMacroAction(kind=kind, duration_ms=rest[0]))
    return SvalboardMacro(id="0", actions=tuple(actions))


def test_macro_row_height_no_overflow():
    # Unnamed macro — no header strip, just one content line.
    macro = _macro_with_actions(
        (SvalboardMacroActionKind.TAP, "A"),
        (SvalboardMacroActionKind.TAP, "B"),
    )
    h = macro_row_height(macro, content_width=600)
    assert h == CONTENT_STRIP_HEIGHT


def test_macro_row_height_two_content_lines_when_overflow():
    long_macro = _macro_with_actions(
        *(((SvalboardMacroActionKind.TAP, "K"),) * 30)
    )
    # Unnamed macro, tight column → at least 2 content lines (no header strip).
    h = macro_row_height(long_macro, content_width=120)
    assert h >= 2 * CONTENT_STRIP_HEIGHT


def test_macro_row_height_no_name_omits_header_strip():
    macro = _macro_with_actions((SvalboardMacroActionKind.TAP, "A"))
    h = macro_row_height(macro, content_width=600)
    assert h == CONTENT_STRIP_HEIGHT


def test_macro_row_height_named_includes_header_strip():
    macro = _macro_with_actions((SvalboardMacroActionKind.TAP, "A"))
    macro_named = SvalboardMacro(id=macro.id, actions=macro.actions, name="Print")
    h = macro_row_height(macro_named, content_width=600)
    assert h == HEADER_STRIP_HEIGHT + CONTENT_STRIP_HEIGHT


def test_build_macro_row_returns_group():
    macro = _macro_with_actions((SvalboardMacroActionKind.TAP, "A"))
    g = build_macro_row(
        macro=macro, x=0, y=0, content_width=600,
        accent_fill="#89511C", accent_line="#DD9857", text_color="#000",
    )
    assert isinstance(g, draw.Group)


def test_tap_dance_section_height_includes_column_header_and_rows():
    rows = [_td("0"), _td("1"), _td("2")]
    h = tap_dance_section_height(rows)
    assert h == TD_HEADER_HEIGHT + len(rows) * (TD_ROW_HEIGHT + TD_ROW_GAP)


def test_tap_dance_section_height_zero_for_empty_rows():
    h = tap_dance_section_height([])
    # An empty list contributes no height — the header is not reserved when
    # there are no rows, so the legend's column-balanced height math does not
    # overstate when only one column is populated.
    assert h == 0.0


def test_build_tap_dance_row_returns_group():
    td = SvalboardTapDance(
        id="0",
        tap=SvalboardTargetKey(label="Z"),
        hold=SvalboardTargetKey(label="⌘"),
        double_tap=None,
        tap_then_hold=None,
        name="Undo / Cmd",
    )
    g = build_tap_dance_row(
        td=td, x=0, y=0, column_width=600,
        accent_fill="#41687F", accent_line="#9AB9CB", text_color="#000",
    )
    assert isinstance(g, draw.Group)


def test_build_tap_dance_row_handles_none_variants():
    """Missing variants render an empty/dashed cell, not a crash."""
    td = SvalboardTapDance(id="0", tap=None, hold=None, double_tap=None, tap_then_hold=None)
    g = build_tap_dance_row(
        td=td, x=0, y=0, column_width=600,
        accent_fill="#41687F", accent_line="#9AB9CB", text_color="#000",
    )
    assert isinstance(g, draw.Group)


def test_build_tap_dance_column_header_returns_group():
    g = build_tap_dance_column_header(x=0, y=0, text_color="#000")
    assert isinstance(g, draw.Group)


import pytest  # noqa: E402

from skim.application.render.legend import build_legend, legend_height  # noqa: E402
from skim.data import Palette  # noqa: E402


@pytest.fixture
def palette():
    return Palette()


def test_legend_height_zero_when_no_specials(palette):
    layout = plan_layout([], [])
    assert legend_height(layout, content_width=1200) == 0.0


def test_build_legend_returns_none_when_no_specials(palette):
    layout = plan_layout([], [])
    assert build_legend(layout, x=0, y=0, content_width=1200, palette=palette) is None


def test_legend_height_grows_with_macro_overflow(palette):
    short = _macro_with_actions((SvalboardMacroActionKind.TAP, "A"))
    long_ = _macro_with_actions(*(((SvalboardMacroActionKind.TAP, "K"),) * 30))
    layout_a = plan_layout([short], [])
    layout_b = plan_layout([long_], [])
    h_a = legend_height(layout_a, content_width=1200)
    h_b = legend_height(layout_b, content_width=200)
    assert h_b > h_a


def test_build_legend_macros_only_returns_group(palette):
    """When only macros present, returns a Group with the section header
    spanning both columns and rows balanced."""
    macros = [_macro(str(i)) for i in range(3)]
    layout = plan_layout(macros, [])
    g = build_legend(layout, x=0, y=0, content_width=1200, palette=palette)
    assert isinstance(g, draw.Group)


def test_build_legend_both_returns_group(palette):
    """When both types present, returns a Group with two columns."""
    layout = plan_layout([_macro("0")], [_td("0")])
    g = build_legend(layout, x=0, y=0, content_width=1200, palette=palette)
    assert isinstance(g, draw.Group)


def test_all_macros_returns_sorted_full_list():
    """all_macros returns every macro sorted numerically then lexicographically."""
    available = (_macro("5"), _macro("0"), _macro("3"), _macro("10"))
    result = all_macros(available)
    assert [m.id for m in result] == ["0", "3", "5", "10"]


def test_all_macros_returns_sorted_full_list_named():
    """all_macros handles named (non-numeric) ids sorted lexicographically."""
    available = (_macro("GAMMA"), _macro("ALPHA"), _macro("BETA"))
    result = all_macros(available)
    assert [m.id for m in result] == ["ALPHA", "BETA", "GAMMA"]


def test_all_tap_dances_returns_sorted_full_list():
    """all_tap_dances returns every tap-dance sorted numerically."""
    available = (_td("2"), _td("0"), _td("5"), _td("1"))
    result = all_tap_dances(available)
    assert [t.id for t in result] == ["0", "1", "2", "5"]


def test_all_tap_dances_empty_input():
    """all_tap_dances returns an empty list for an empty tuple."""
    result = all_tap_dances(())
    assert result == []


def test_legend_key_label_appends_layer_number_for_layer_only_function():
    from skim.application.render.legend import _legend_key_label

    key = SvalboardTargetKey(
        label="\U000F03FE",  # any layer-icon glyph (or a plain string for the test)
        layer_switch=2,
    )
    assert _legend_key_label(key) == "\U000F03FE 2"


def test_legend_key_label_passes_compound_label_through():
    from skim.application.render.legend import _legend_key_label
    from skim.domain.domain_types import SEPARATOR_CHAR

    key = SvalboardTargetKey(
        label=f"L1{SEPARATOR_CHAR}A",
        layer_switch=1,
    )
    assert _legend_key_label(key) == f"L1{SEPARATOR_CHAR}A"


def test_legend_key_label_returns_plain_label_when_no_layer_switch():
    from skim.application.render.legend import _legend_key_label

    key = SvalboardTargetKey(label="A")
    assert _legend_key_label(key) == "A"


def test_build_macro_column_header_returns_group():
    g = build_macro_column_header(x=0, y=0, text_color="#000")
    assert isinstance(g, draw.Group)


def test_macro_section_height_includes_column_header(palette):
    macros = [_macro("0", name="Print")]
    h = _macro_section_height(macros, col_width=600)
    expected = (
        SECTION_HEADER_HEIGHT
        + MACRO_COLUMN_HEADER_HEIGHT
        + macro_row_height(macros[0], 600)
        + ACTION_KEY_PRE_GAP
        + ACTION_KEY_STRIP_HEIGHT
    )
    assert h == expected

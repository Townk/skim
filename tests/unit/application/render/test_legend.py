"""Unit tests for skim.application.render.legend."""

import drawsvg as draw

from skim.application.render.legend import (
    CONTENT_STRIP_HEIGHT,
    HEADER_STRIP_HEIGHT,
    build_action_glyph,
    build_macro_row,
    collect_used_ids,
    macro_row_height,
    plan_layout,
    resolve_macros,
    resolve_tap_dances,
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
    assert plan.macro_right == []
    assert [t.id for t in plan.tap_dance_left] == ["0"]
    assert plan.tap_dance_right == []
    assert plan.macros_span_columns is False
    assert plan.tap_dances_span_columns is False


def test_plan_layout_only_macros_balances_two_columns():
    macros = [_macro(str(i)) for i in range(5)]
    plan = plan_layout(macros, [])
    assert plan is not None
    # 5 entries → 3 left, 2 right (ceil/floor split).
    assert [m.id for m in plan.macro_left] == ["0", "1", "2"]
    assert [m.id for m in plan.macro_right] == ["3", "4"]
    assert plan.macros_span_columns is True
    assert plan.tap_dance_left == []
    assert plan.tap_dance_right == []


def test_plan_layout_single_macro_only_left_column():
    plan = plan_layout([_macro("0")], [])
    assert plan is not None
    assert [m.id for m in plan.macro_left] == ["0"]
    assert plan.macro_right == []
    assert plan.macros_span_columns is True


def test_plan_layout_only_tap_dances_balances():
    tds = [_td(str(i)) for i in range(3)]
    plan = plan_layout([], tds)
    assert plan is not None
    # 3 entries → 2 left, 1 right.
    assert [t.id for t in plan.tap_dance_left] == ["0", "1"]
    assert [t.id for t in plan.tap_dance_right] == ["2"]
    assert plan.tap_dances_span_columns is True


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
    macro = _macro_with_actions(
        (SvalboardMacroActionKind.TAP, "A"),
        (SvalboardMacroActionKind.TAP, "B"),
    )
    h = macro_row_height(macro, content_width=600)
    assert h == HEADER_STRIP_HEIGHT + CONTENT_STRIP_HEIGHT


def test_macro_row_height_two_content_lines_when_overflow():
    long_macro = _macro_with_actions(
        *(((SvalboardMacroActionKind.TAP, "K"),) * 30)
    )
    # Tight column → at least 2 content lines.
    h = macro_row_height(long_macro, content_width=120)
    assert h >= HEADER_STRIP_HEIGHT + 2 * CONTENT_STRIP_HEIGHT


def test_build_macro_row_returns_group():
    macro = _macro_with_actions((SvalboardMacroActionKind.TAP, "A"))
    g = build_macro_row(
        macro=macro, x=0, y=0, content_width=600,
        accent_fill="#89511C", accent_line="#DD9857", text_color="#000",
    )
    assert isinstance(g, draw.Group)

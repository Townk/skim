"""Unit tests for skim.application.render.legend."""

from skim.application.render.legend import collect_used_ids, resolve_macros, resolve_tap_dances
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

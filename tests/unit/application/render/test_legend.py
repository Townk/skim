"""Unit tests for skim.application.render.legend."""

from skim.application.render.legend import collect_used_ids
from skim.data import SvalboardLayout
from skim.domain.domain_types import SvalboardTargetKey


def _layout_from_keys(keys: list[SvalboardTargetKey]) -> SvalboardLayout[SvalboardTargetKey]:
    """Build a SvalboardLayout from a flat 60-key list (test helper)."""
    return SvalboardLayout.from_sequence(keys)


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

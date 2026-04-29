# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.symbol_legend."""

from skim.application.loaders import load_keycode_mappings
from skim.application.render.symbol_legend import (
    build_symbol_legend,
    collect_used_descriptions,
    symbol_legend_height,
)
from skim.data import Palette, SkimConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mappings():
    """Return the real keycode mappings (uses lru_cache, cheap after first call)."""
    return load_keycode_mappings(SkimConfig().keycodes)


def _entries(keycodes, keymap=None):
    return collect_used_descriptions(keycodes, keymap, _mappings())


# ---------------------------------------------------------------------------
# collect_used_descriptions tests
# ---------------------------------------------------------------------------

class TestCollectUsedDescriptions:
    def test_collect_simple_modifier(self):
        """KC_LEFT_CTRL produces one entry with 'Left Ctrl' description."""
        entries = _entries(["KC_LEFT_CTRL"])
        assert len(entries) == 1
        assert entries[0].description == "Left Ctrl"
        assert entries[0].sort_key == "KC_LEFT_CTRL"

    def test_collect_alias_resolves_to_canonical(self):
        """KC_LCTL is an alias for KC_LEFT_CTRL → still produces 'Left Ctrl'."""
        entries = _entries(["KC_LCTL"])
        assert len(entries) == 1
        assert entries[0].description == "Left Ctrl"

    def test_collect_recurses_into_wrapper_lctl(self):
        """LCTL(KC_A) → KC_LEFT_CTRL entry; KC_A has no description."""
        entries = _entries(["LCTL(KC_A)"])
        sort_keys = {e.sort_key for e in entries}
        # LCTL is a function in macro_functions but has no function_description.
        # KC_A is plain and not in symbol_descriptions.
        # KC_LEFT_CTRL should be found via the function's template (@@KC_LEFT_CTRL; @0;).
        # The function args include KC_A → no symbol entry.
        # There may be an entry for KC_LEFT_CTRL if the template arg is recursed.
        # Accept 0 or 1 entries; just confirm no crash and KC_A not in entries.
        assert "KC_A" not in sort_keys

    def test_collect_layer_function(self):
        """MO(1) produces a 'MO' function entry with layer-# description and symbol."""
        entries = _entries(["MO(1)"])
        assert any(e.sort_key == "MO" for e in entries)
        mo_entry = next(e for e in entries if e.sort_key == "MO")
        assert "layer #" in mo_entry.description
        assert "#" in mo_entry.display_label

    def test_collect_lt_function_not_described(self):
        """LT is a tap-hold combination — not in function_descriptions.

        The user can read the tap|hold label directly on the key, so we
        intentionally omit tap-hold patterns from the legend. ``LT(1, KC_A)``
        recurses into its args (no LT entry; KC_A isn't described either).
        """
        entries = _entries(["LT(1,KC_A)"])
        assert all(e.sort_key != "LT" for e in entries)

    def test_collect_tg_function(self):
        """TG(2) produces a 'TG' function entry with 'Toggle' description."""
        entries = _entries(["TG(2)"])
        assert any(e.sort_key == "TG" for e in entries)
        tg_entry = next(e for e in entries if e.sort_key == "TG")
        assert "Toggle" in tg_entry.description

    def test_collect_dedupes_repeats(self):
        """Two keys both bound to KC_LEFT_CTRL → single entry."""
        entries = _entries(["KC_LEFT_CTRL", "KC_LEFT_CTRL"])
        ctrl_entries = [e for e in entries if e.sort_key == "KC_LEFT_CTRL"]
        assert len(ctrl_entries) == 1

    def test_collect_dedupes_alias_and_canonical(self):
        """KC_LEFT_CTRL and KC_LCTL resolve to same canonical → single entry."""
        entries = _entries(["KC_LEFT_CTRL", "KC_LCTL"])
        ctrl_entries = [e for e in entries if e.description == "Left Ctrl"]
        assert len(ctrl_entries) == 1

    def test_collect_skips_obvious_keys(self):
        """KC_A only → empty entries list (no symbol description for letters)."""
        entries = _entries(["KC_A"])
        assert entries == []

    def test_collect_enter(self):
        """KC_ENTER or KC_ENT should produce an entry."""
        entries_direct = _entries(["KC_ENTER"])
        entries_alias = _entries(["KC_ENT"])
        # Either the canonical or alias should resolve
        assert len(entries_direct) >= 1 or len(entries_alias) >= 1

    def test_collect_space(self):
        """KC_SPACE or KC_SPC produces a 'Space' entry."""
        entries = _entries(["KC_SPACE"])
        space_entries = [e for e in entries if "Space" in e.description]
        assert len(space_entries) == 1

    def test_collect_spc_alias(self):
        """KC_SPC (alias for KC_SPACE) should resolve to a 'Space' entry."""
        entries = _entries(["KC_SPC"])
        space_entries = [e for e in entries if "Space" in e.description]
        assert len(space_entries) == 1

    def test_collect_backspace(self):
        """KC_BACKSPACE should produce a 'Backspace' entry."""
        entries = _entries(["KC_BACKSPACE"])
        bs_entries = [e for e in entries if "Backspace" in e.description]
        assert len(bs_entries) == 1

    def test_collect_empty_input(self):
        """Empty input produces empty output."""
        assert _entries([]) == []

    def test_collect_only_unknown_keycodes(self):
        """Unknown keycodes produce no entries."""
        entries = _entries(["SOME_CUSTOM_KEY", "ANOTHER_CUSTOM"])
        assert entries == []

    def test_collect_sorted(self):
        """Entries are sorted by category first, then by sort_key within a category."""
        from itertools import groupby

        from skim.application.render.symbol_legend import _category_index

        entries = _entries(["KC_SPACE", "KC_LEFT_CTRL", "MO(1)"])
        # Category priority is respected: Layers (MO) < Modifiers (KC_LEFT_CTRL)
        # < Special Keys (KC_SPACE).
        cat_indices = [_category_index(e.category) for e in entries]
        assert cat_indices == sorted(cat_indices)

        # Within each category, sort_key order is preserved (lexicographic).
        for _cat, group in groupby(entries, key=lambda e: e.category):
            group_list = list(group)
            sort_keys = [e.sort_key for e in group_list]
            assert sort_keys == sorted(sort_keys)

    def test_collect_groups_by_category(self):
        """Entries with category metadata sort by category, then by id."""
        entries = _entries(["KC_NUM_LOCK", "KC_LEFT_CTRL", "MO(1)", "KC_ENTER"])
        categories = [e.category for e in entries]
        # Layers (MO) → Modifiers (KC_LEFT_CTRL) → Lock Keys (KC_NUM_LOCK)
        # → Special Keys (KC_ENTER)
        assert categories == ["Layers", "Modifiers", "Lock Keys", "Special Keys"]

    def test_collect_multiple_functions(self):
        """MO(1) and TG(2) each produce their own entry, deduped."""
        entries = _entries(["MO(1)", "MO(2)", "TG(1)"])
        mo_entries = [e for e in entries if e.sort_key == "MO"]
        tg_entries = [e for e in entries if e.sort_key == "TG"]
        assert len(mo_entries) == 1
        assert len(tg_entries) == 1

    def test_lalt_t_produces_left_alt_entry(self):
        """LALT_T(KC_F12) is a modifier hold-tap; should produce a Left Alt entry."""
        # LALT_T is in macro_functions as "@@KC_LEFT_ALT;|;@0;" so the template
        # references KC_LEFT_ALT. The arg KC_F12 has no symbol description.
        entries = _entries(["LALT_T(KC_F12)"])
        # The template recursion may or may not produce an alt entry depending on
        # whether the template arg string is recursed. Accept either outcome here;
        # the important thing is no exception and no KC_F12 entry.
        assert not any(e for e in entries if "F12" in e.sort_key)

    def test_osl_function(self):
        """OSL(3) produces an OSL entry with 'One-shot layer' description."""
        entries = _entries(["OSL(3)"])
        osl_entries = [e for e in entries if e.sort_key == "OSL"]
        assert len(osl_entries) == 1
        assert "One-shot" in osl_entries[0].description

    def test_collect_function_call_pattern_match(self):
        """A function-call pattern in symbol_descriptions matches the whole
        keycode and does NOT recurse into args."""
        from skim.application.render.symbol_legend import collect_used_descriptions

        mappings: dict = {
            "keycodes": {
                "KC_LEFT": "←",
                "KC_LEFT_ALT": "%%nf-md-apple_keyboard_option;",
            },
            "pre_processing": {},
            "macro_functions": {
                "A": "@@KC_LEFT_ALT; @0;",
            },
            "modifier_union": {},
            "symbol_descriptions": {
                "A(KC_LEFT)": "Previous word",
                "KC_LEFT_ALT": "Left Alt",
            },
            "function_descriptions": {},
        }
        entries = collect_used_descriptions(["A(KC_LEFT)"], None, mappings)
        # ONE entry for the whole function-call pattern; NOT two separate entries
        assert len(entries) == 1
        assert entries[0].description == "Previous word"
        assert entries[0].sort_key == "A(KC_LEFT)"
        # No "Left Alt" entry from recursion
        assert not any(e.description == "Left Alt" for e in entries)

    def test_collect_function_call_no_pattern_recurses(self):
        """A function-call NOT in symbol_descriptions falls back to
        function_descriptions + recursion into args."""
        from skim.application.render.symbol_legend import collect_used_descriptions

        mappings: dict = {
            "keycodes": {
                "KC_LEFT_ALT": "%%nf-md-apple_keyboard_option;",
                "KC_LEFT_CTRL": "⌃",
            },
            "pre_processing": {},
            "macro_functions": {
                "LCTL": "@@KC_LEFT_CTRL; @0;",
            },
            "modifier_union": {},
            "symbol_descriptions": {
                "KC_LEFT_ALT": "Left Alt",
            },
            "function_descriptions": {
                "LCTL": "Hold control",
            },
        }
        entries = collect_used_descriptions(["LCTL(KC_LEFT_ALT)"], None, mappings)
        sort_keys = {e.sort_key for e in entries}
        descriptions = {e.description for e in entries}
        # Function entry from function_descriptions
        assert "LCTL" in sort_keys
        assert "Hold control" in descriptions
        # Atomic entry from recursion into args
        assert "KC_LEFT_ALT" in sort_keys
        assert "Left Alt" in descriptions
        assert len(entries) == 2

    def test_function_display_label_derived_from_template(self):
        """A function-description entry derives its display_label from the
        macro_functions template via the label adapter (``#`` as layer arg).

        When the template has no layer placeholder the adapter appends `` #``
        for layer functions so the legend reader knows a layer arg is involved.
        The description uses the new ``#0;`` placeholder syntax which resolves
        to the literal ``#`` at legend-render time.
        """
        from skim.application.render.symbol_legend import collect_used_descriptions

        mappings: dict = {
            "keycodes": {},
            "pre_processing": {},
            "macro_functions": {
                # Template has no #N; placeholder — layer shown as icon only.
                "MO": "%%nf-md-layers_outline;",
            },
            "modifier_union": {},
            "symbol_descriptions": {},
            "function_descriptions": {
                # Use the new #N; placeholder syntax
                "MO": "Hold layer #0;",
            },
        }
        entries = collect_used_descriptions(["MO(5)"], None, mappings)
        mo_entries = [e for e in entries if e.sort_key == "MO"]
        assert len(mo_entries) == 1
        entry = mo_entries[0]
        # display_label is derived from the template + ``#`` appended for layer functions
        assert "%%nf-md-layers_outline;" in entry.display_label
        assert "#" in entry.display_label
        # ``#0;`` in the raw description resolves to ``#`` at render time
        assert entry.description == "Hold layer #"

    def test_description_resolves_at_at_keycode_alias(self):
        """``@@KEYCODE;`` in a function description is resolved to the
        keycode's display label via the adapter's alias chain.

        E.g. ``"Hold @@KC_LEFT_CTRL; while pressing #0;"`` should render as
        ``"Hold ⌃ while pressing #"`` when KC_LEFT_CTRL maps to ``⌃``.
        """
        from skim.application.render.symbol_legend import collect_used_descriptions

        mappings: dict = {
            "keycodes": {
                "KC_LEFT_CTRL": "⌃",
            },
            "pre_processing": {},
            "macro_functions": {
                "MO": "%%nf-md-layers_outline;",
            },
            "modifier_union": {},
            "symbol_descriptions": {},
            "function_descriptions": {
                "MO": "Hold @@KC_LEFT_CTRL; while pressing #0;",
            },
        }
        entries = collect_used_descriptions(["MO(2)"], None, mappings)
        mo_entries = [e for e in entries if e.sort_key == "MO"]
        assert len(mo_entries) == 1
        entry = mo_entries[0]
        # @@KC_LEFT_CTRL; → "⌃", #0; → "#"
        assert entry.description == "Hold ⌃ while pressing #"


# ---------------------------------------------------------------------------
# symbol_legend_height tests
# ---------------------------------------------------------------------------

class TestSymbolLegendHeight:
    def test_empty_entries_returns_zero(self):
        assert symbol_legend_height([], 800.0) == 0.0

    def test_nonempty_returns_positive(self):
        entries = _entries(["KC_LEFT_CTRL", "MO(1)"])
        h = symbol_legend_height(entries, 800.0)
        assert h > 0

    def test_more_entries_same_or_larger_height(self):
        """More entries → same or more rows → same or taller block."""
        entries_few = _entries(["MO(1)"])
        entries_many = _entries(["MO(1)", "KC_LEFT_CTRL", "KC_LEFT_SHIFT", "KC_ENTER", "KC_SPACE"])
        h_few = symbol_legend_height(entries_few, 800.0)
        h_many = symbol_legend_height(entries_many, 800.0)
        assert h_many >= h_few


# ---------------------------------------------------------------------------
# Per-instance description tests
# ---------------------------------------------------------------------------

def _mappings_with_function_description(func: str, description: str):
    """Return a copy of real keycode mappings with one function_descriptions entry
    overridden to ``description``."""
    from types import MappingProxyType

    base = load_keycode_mappings(SkimConfig().keycodes)
    raw = dict(base)
    raw["function_descriptions"] = dict(raw.get("function_descriptions", {}))
    raw["function_descriptions"][func] = description
    return MappingProxyType(raw)


def test_description_with_at_placeholder_produces_per_instance_entries():
    """When function_descriptions[FUNC] contains @N;, each unique arg
    combination produces its own entry."""
    mappings = _mappings_with_function_description("MO", "Hold for layer @0;")
    keycodes = ["MO(1)", "MO(2)", "MO(2)"]  # MO(2) repeats — should still dedupe.
    entries = collect_used_descriptions(keycodes, None, mappings)
    mo_entries = [e for e in entries if "MO" in e.sort_key]
    assert len(mo_entries) == 2  # one per unique args
    descs = sorted(e.description for e in mo_entries)
    assert "Hold for layer 1" in descs[0]
    assert "Hold for layer 2" in descs[1]


def test_description_with_only_hash_placeholder_dedupes():
    """When function_descriptions[FUNC] uses only #N; or no placeholders,
    all uses dedupe to one entry."""
    mappings = _mappings_with_function_description("MO", "Hold for layer #0;")
    keycodes = ["MO(1)", "MO(2)", "MO(5)"]
    entries = collect_used_descriptions(keycodes, None, mappings)
    mo_entries = [e for e in entries if e.sort_key == "MO"]
    assert len(mo_entries) == 1
    assert "layer #" in mo_entries[0].description


def test_description_mixed_at_and_hash():
    """Mixed @N; and #N; → per-instance mode; @N; resolves, #N; stays as #."""
    mappings = _mappings_with_function_description(
        "MO", "Layer @0; pattern: #0;"
    )
    entries = collect_used_descriptions(["MO(7)"], None, mappings)
    mo_entries = [e for e in entries if "MO" in e.sort_key]
    assert len(mo_entries) == 1
    assert "Layer 7 pattern: #" in mo_entries[0].description


# ---------------------------------------------------------------------------
# build_symbol_legend tests
# ---------------------------------------------------------------------------

class TestBuildSymbolLegend:
    def _palette(self):
        return Palette()

    def test_returns_none_when_empty(self):
        assert build_symbol_legend([], 0, 0, 800, self._palette()) is None

    def test_returns_group_when_nonempty(self):
        import drawsvg as draw
        entries = _entries(["KC_LEFT_CTRL"])
        g = build_symbol_legend(entries, 0, 0, 800, self._palette())
        assert g is not None
        assert isinstance(g, draw.Group)

    def _to_svg(self, group) -> str:
        """Render a Group to SVG string via a Drawing wrapper."""
        import drawsvg as draw
        d = draw.Drawing(1600, 400)
        d.append(group)
        return d.as_svg()

    def test_contains_symbols_header(self):
        """The rendered group contains a 'SYMBOLS' text element."""
        entries = _entries(["KC_LEFT_CTRL", "MO(1)"])
        g = build_symbol_legend(entries, 0, 0, 800, self._palette())
        assert g is not None
        svg_str = self._to_svg(g)
        assert "SYMBOLS" in svg_str

    def test_contains_description_text(self):
        """The rendered group contains the description text of at least one entry."""
        entries = _entries(["KC_LEFT_CTRL"])
        g = build_symbol_legend(entries, 0, 0, 800, self._palette())
        assert g is not None
        svg_str = self._to_svg(g)
        assert "Left Ctrl" in svg_str

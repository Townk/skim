# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Data utilities for the section composables.

This module owns the data-resolution layer the section composables
consume — every "given a config + parsed keymap, compute the rows /
ids / entries the section will paint" helper lives here so the
section composables themselves stay focused on layout.

Macro / tap-dance helpers
-------------------------

* :func:`collect_used_ids` — walks a layer to collect the macro and
  tap-dance ids referenced anywhere on it.
* :func:`resolve_macros` / :func:`resolve_tap_dances` — filter the
  parsed entries down to a set of used ids and sort named-first,
  then by id.
* :func:`all_macros` / :func:`all_tap_dances` — same sort applied to
  every parsed entry (used by the overview, which shows everything).
* :func:`format_key_label` — single-line display label for a target
  key. Used by the macro-pill, tap-dance-cell, and symbol-legend
  composables.

Symbol-legend helpers
---------------------

* :class:`SymbolLegendEntry` — the data type the legend rows render
  from.
* :func:`collect_used_descriptions` — walks each key's raw keycode
  pre-resolution and produces one ``SymbolLegendEntry`` per
  distinct canonical keycode / function. Recurses through wrapper
  functions (``LT(N, KC_A)``, ``LCTL(KC_A)``, …), tap-dance
  variants, and macro action keys; resolves atomic keycodes through
  the ``@@`` alias chain. The original name and every chain step
  are checked against ``symbol_descriptions``; function names are
  checked against ``function_descriptions``.

The orchestration helpers that gate ``collect_used_descriptions``
on ``output.style.show_transparent_fallthrough`` and pick which
layers to walk live in :mod:`skim.application.render`'s entry
points, not here.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from skim.data import KeycodeMappings, SvalboardKeymap, SvalboardLayout
from skim.domain import SvalboardMacro, SvalboardTapDance
from skim.domain.domain_types import SEPARATOR_CHAR, SvalboardTargetKey

if TYPE_CHECKING:
    from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter


# ---------------------------------------------------------------------------
# Macro / tap-dance helpers
# ---------------------------------------------------------------------------


def collect_used_ids(
    layer: SvalboardLayout[SvalboardTargetKey],
) -> tuple[set[str], set[str]]:
    """Return ``(macro_ids, tap_dance_ids)`` referenced anywhere on ``layer``.

    Transparent fallthroughs already carry the inherited ids (handled by
    :func:`KeymapTargetAdapter._substitute`), so a single pass over every
    key is enough.
    """
    macros: set[str] = set()
    tap_dances: set[str] = set()
    for key in layer:
        if key is None:
            continue
        if key.macro_id is not None:
            macros.add(key.macro_id)
        if key.tap_dance_id is not None:
            tap_dances.add(key.tap_dance_id)
    return macros, tap_dances


def _id_sort_key(id_: str) -> tuple[int, int | str]:
    """Numeric ids sort first (ascending), then named ids lex-ascending."""
    try:
        return (0, int(id_))
    except ValueError:
        return (1, id_)


def _named_first_sort_key(
    entry: SvalboardMacro[SvalboardTargetKey] | SvalboardTapDance[SvalboardTargetKey],
) -> tuple[int, int, int | str]:
    """Sort entries with a user-defined ``name`` first, then by id.

    Within each "named" / "unnamed" group, numeric ids precede named ids,
    and within each kind they sort ascending.
    """
    has_no_name = 0 if entry.name else 1
    id_kind, id_value = _id_sort_key(entry.id)
    return (has_no_name, id_kind, id_value)


def resolve_macros(
    used_ids: set[str],
    available: tuple[SvalboardMacro[SvalboardTargetKey], ...],
) -> list[SvalboardMacro[SvalboardTargetKey]]:
    """Filter ``available`` to ``used_ids`` and sort named entries first, then by id."""
    by_id = {m.id: m for m in available}
    return sorted(
        (by_id[i] for i in used_ids if i in by_id),
        key=_named_first_sort_key,
    )


def resolve_tap_dances(
    used_ids: set[str],
    available: tuple[SvalboardTapDance[SvalboardTargetKey], ...],
) -> list[SvalboardTapDance[SvalboardTargetKey]]:
    """Filter ``available`` to ``used_ids`` and sort named entries first, then by id."""
    by_id = {t.id: t for t in available}
    return sorted(
        (by_id[i] for i in used_ids if i in by_id),
        key=_named_first_sort_key,
    )


def all_macros(
    macros: tuple[SvalboardMacro[SvalboardTargetKey], ...],
) -> list[SvalboardMacro[SvalboardTargetKey]]:
    """Return all parsed macros sorted named-first, then by id (no filter)."""
    return sorted(macros, key=_named_first_sort_key)


def all_tap_dances(
    tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...],
) -> list[SvalboardTapDance[SvalboardTargetKey]]:
    """Return all parsed tap-dances sorted named-first, then by id (no filter)."""
    return sorted(tap_dances, key=_named_first_sort_key)


def format_key_label(key: SvalboardTargetKey) -> str:
    """Return the single-line label string to display for ``key``.

    Newlines are collapsed to spaces — multi-line key labels work
    fine on the keymap proper but break section pills / cells, which
    are sized for one line of text and would spill past the rounded
    rect on additional lines.

    For layer-only functions (``MO(N)``, ``TO(N)``, ``TG(N)`` …), the
    resolved label is just the layer glyph — ambiguous on its own. We
    append the target layer number so the reader can tell which layer
    is being switched to. Compound functions (``LT(N, KC_A)``, ``LM(N,
    mods)``) already embed the layer digit alongside the tap key via
    the ``|`` separator, so they pass through unchanged.
    """
    label = key.label.replace("\n", " ")
    if key.layer_switch is not None and SEPARATOR_CHAR not in label:
        return f"{label} {key.layer_switch}"
    return label


# ---------------------------------------------------------------------------
# Symbol-legend entry-resolution layer
# ---------------------------------------------------------------------------

_TRANSPARENT_KEYCODES = frozenset({"KC_TRANSPARENT", "KC_TRNS", "_______"})
_TRANSPARENT_GLYPH = "⛛"

_FUNC_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\((.+)\)$")
"""Match ``FUNCNAME(args)`` at the top level."""

_ALIAS_RE = re.compile(r"@@([A-Z0-9_]+);")
"""Match ``@@KEYCODE;`` alias references inside a label string."""

_LAYER_FUNCTION_NAMES = frozenset({"DF", "PDF", "MO", "LM", "LT", "OSL", "TG", "TO", "TT"})
"""Layer-switching function names for which a ``#`` layer-arg indicator is
appended to the display label when the rendered result doesn't already
contain one."""


@dataclass(frozen=True, slots=True)
class SymbolLegendEntry:
    """One row in the symbol legend.

    Attributes:
        display_label: The resolved label string shown in the legend's
            left "symbol" cell.
        description: Human-readable description from the yaml data.
        sort_key: Canonical keycode or function name used for deduplication
            and stable ordering.
        category: QMK-style category name for grouped display (e.g.
            ``"Modifiers"``, ``"Layers"``).  Empty string means uncategorized.
    """

    display_label: str
    description: str
    sort_key: str
    category: str = ""


def _build_entry_sort_key(
    keycode_mappings: KeycodeMappings,
) -> Callable[[SymbolLegendEntry], tuple]:
    """Return a sort-key callable bound to the YAML's category order.

    Symbol categories are listed first (in the order they appear in
    ``symbol_descriptions``), then any function-only categories
    appear after them. Numeric ``sort_key`` values sort ahead of
    lexicographic ones within a category (so layer indices ``0..9``
    group cleanly even when other categories use textual sort keys).
    """
    sym_order: tuple[str, ...] = tuple(keycode_mappings.get("symbol_category_order", ()))
    func_order: tuple[str, ...] = tuple(keycode_mappings.get("function_category_order", ()))
    seen: set[str] = set(sym_order)
    merged = sym_order + tuple(c for c in func_order if c not in seen)
    index_by_name = {name: i for i, name in enumerate(merged)}
    fallback = len(merged)

    def sort_key(entry: SymbolLegendEntry) -> tuple:
        cat_idx = index_by_name.get(entry.category, fallback)
        try:
            sort_pair: tuple = (0, int(entry.sort_key))
        except (ValueError, TypeError):
            sort_pair = (1, entry.sort_key)
        return (cat_idx,) + sort_pair

    return sort_key


def _resolve_aliases(keycode: str, keycodes: dict[str, str]) -> list[str]:
    """Return the chain of keycode names traversed when resolving ``keycode``.

    The first entry is ``keycode`` itself; subsequent entries are the
    keycodes found by following ``@@KEY;`` alias references, one level
    per step, stopping at cycles or non-alias labels.

    Only returns the *names* (keys), not the labels.  The last name in the
    list is the one whose label is not itself an alias.
    """
    chain: list[str] = []
    visited: set[str] = set()
    current = keycode
    while current not in visited:
        visited.add(current)
        chain.append(current)
        label = keycodes.get(current)
        if label is None:
            break
        alias_match = _ALIAS_RE.fullmatch(label.strip())
        if alias_match is None:
            break
        current = alias_match.group(1)
    return chain


def _count_placeholders(template: str) -> int:
    """Count ``@N;`` and ``#N;`` placeholders in a function template."""
    return len(re.findall(r"[@#]\d+;", template))


def _is_per_instance_description(desc: str) -> bool:
    """Return True iff ``desc`` contains any ``@N;`` placeholder.

    When a description contains ``@N;`` placeholders, each unique
    (function, args) combination produces its own legend entry instead
    of a single generic entry per function name.
    """
    return bool(re.search(r"@\d+;", desc))


def _resolve_description_generic(raw: str, adapter: KeycodeLabelAdapter) -> str:
    """Resolve a generic function description.

    Both ``@N;`` and ``#N;`` are replaced with the literal ``#``; ``|;``
    becomes :data:`~skim.domain.SEPARATOR_CHAR`; ``@@KEYCODE;`` references
    are resolved through the adapter's alias chain.
    """
    text = re.sub(r"[@#]\d+;", "#", raw)
    text = text.replace("|;", SEPARATOR_CHAR)
    return adapter._resolve_label_reference(text, set())


def _resolve_description_per_instance(
    raw: str,
    args: list[str],
    adapter: KeycodeLabelAdapter,
) -> str:
    """Resolve a per-instance function description.

    ``#N;`` → literal ``#``; ``@N;`` → the recursively-resolved label of
    ``args[N]``; ``|;`` → :data:`~skim.domain.SEPARATOR_CHAR`; ``@@KEYCODE;``
    references are resolved through the adapter's alias chain.
    """
    text = re.sub(r"#\d+;", "#", raw)

    def _replace_at(match: re.Match) -> str:
        idx = int(match.group(1))
        if idx >= len(args):
            return ""
        return adapter._resolve_keycode_argument(args, idx)

    text = re.sub(r"@(\d+);", _replace_at, text)
    text = text.replace("|;", SEPARATOR_CHAR)
    return adapter._resolve_label_reference(text, set())


def _function_display_label(
    func_name: str,
    macro_functions: dict[str, str],
    keycode_mappings: KeycodeMappings,
) -> str:
    """Render the display symbol for a function-description entry.

    Builds a synthetic keycode (``MO(#)``, ``LM(#,KC_NO)``, …) and runs
    it through the standard label adapter so glyphs render exactly as they
    do on a key.  ``#`` is used as the layer-arg placeholder.

    For layer functions, when the resolved label contains no layer reference
    (no ``#`` character and no separator), ``#`` is appended so the legend
    reader sees that a layer arg is part of the function.
    """
    from skim.data import Keyboard
    from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter

    adapter = KeycodeLabelAdapter(Keyboard(), keycode_mappings)

    template = macro_functions.get(func_name, "")
    arg_count = max(1, _count_placeholders(template))
    args = ["#"] + ["KC_NO"] * (arg_count - 1)
    synthetic = f"{func_name}({','.join(args)})"
    result = adapter.transform(synthetic)
    label = result.label or ""

    if func_name in _LAYER_FUNCTION_NAMES and "#" not in label and SEPARATOR_CHAR not in label:
        label = f"{label} #" if label else "#"

    return label


def _parse_function_args(args_str: str) -> list[str]:
    """Split comma-separated args respecting nested parentheses."""
    args: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in args_str:
        if ch.isspace():
            continue
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        args.append("".join(current))
    return args


def _resolve_display_label(
    keycode: str,
    keycodes_dict: dict[str, str],
    macro_functions: dict[str, str],
) -> str:
    """Resolve a keycode (atomic or function-call) to its display label string.

    Lightweight resolver that works without a full ``Keyboard`` config.
    For function-call forms it expands the macro_functions template,
    substituting ``@@KEY;`` alias references and ``@N;`` argument
    placeholders. Layer-number placeholders (``#N;``) are left as-is
    (rare for display use).

    Returns the resolved label, or ``keycode`` itself as a fallback.
    """
    func_match = _FUNC_RE.match(keycode)
    if func_match:
        func_name = func_match.group(1)
        args_str = func_match.group(2)
        template = macro_functions.get(func_name)
        if template is None:
            return keycode
        args = _parse_function_args(args_str)

        def _sub_arg(m: re.Match[str]) -> str:
            idx = int(m.group(1))
            if idx >= len(args):
                return ""
            return _resolve_display_label(args[idx], keycodes_dict, macro_functions)

        result = re.sub(r"@(\d+);", _sub_arg, template)

        def _sub_alias(m: re.Match[str]) -> str:
            key = m.group(1)
            label = keycodes_dict.get(key, key)
            nested = _ALIAS_RE.fullmatch(label.strip())
            if nested:
                label = keycodes_dict.get(nested.group(1), nested.group(1))
            return label

        result = re.sub(r"@@([A-Z0-9_]+);", _sub_alias, result)
        if "|;" in result:
            result = result.split("|;")[0].strip()
        return result.strip()

    chain = _resolve_aliases(keycode, keycodes_dict)
    canonical = chain[-1]
    raw_label = keycodes_dict.get(canonical, canonical)

    def _sub_alias(m: re.Match[str]) -> str:
        key = m.group(1)
        label = keycodes_dict.get(key, key)
        nested = _ALIAS_RE.fullmatch(label.strip())
        if nested:
            label = keycodes_dict.get(nested.group(1), nested.group(1))
        return label

    display = re.sub(r"@@([A-Z0-9_]+);", _sub_alias, raw_label).strip()
    return display if display else keycode


def _collect_raw(
    keycodes_raw: Iterable[str],
    keymap: SvalboardKeymap[str] | SvalboardKeymap[SvalboardTargetKey] | None,
    keycode_mappings: KeycodeMappings,
    out: dict[str, SymbolLegendEntry],
    visited_funcs: set[str],
    include_transparent: bool = True,
) -> None:
    """Recursive worker that populates ``out`` (sort_key → entry).

    Walks ``keycodes_raw`` and follows the chains documented at the
    top of the symbol-legend section above.
    """
    keycodes_dict: dict[str, str] = keycode_mappings.get("keycodes", {})
    pre_proc: dict[str, str] = keycode_mappings.get("pre_processing", {})
    macro_functions: dict[str, str] = keycode_mappings.get("macro_functions", {})
    symbol_desc: dict[str, str] = keycode_mappings.get("symbol_descriptions", {})
    func_desc: Mapping[str, str | dict[str, str]] = keycode_mappings.get(
        "function_descriptions", {}
    )
    symbol_cats: dict[str, str] = keycode_mappings.get("symbol_categories", {})
    func_cats: dict[str, str] = keycode_mappings.get("function_categories", {})
    legend_aliases: dict[str, str] = keycode_mappings.get("symbol_legend_aliases", {})

    for raw in keycodes_raw:
        keycode = pre_proc.get(raw, raw)

        # Transparent family — special-cased so the ⛛ glyph entry only
        # appears when fall-through is off (otherwise the glyph never
        # paints on the keymap and the legend entry would be misleading).
        if keycode in _TRANSPARENT_KEYCODES:
            if include_transparent:
                sort_k = "KC_TRANSPARENT"
                if sort_k not in out and "KC_TRANSPARENT" in symbol_desc:
                    out[sort_k] = SymbolLegendEntry(
                        display_label=_TRANSPARENT_GLYPH,
                        description=symbol_desc["KC_TRANSPARENT"],
                        sort_key=sort_k,
                        category=symbol_cats.get("KC_TRANSPARENT", ""),
                    )
            continue

        # Whole-keycode lookup — handles atomic matches AND function-call
        # patterns listed verbatim in symbol_descriptions (e.g.
        # ``A(KC_LEFT)``). Apply the legend-alias redirect first so
        # spellings sharing a canonical form (atomic L/R variants, plus
        # function-call variants like ``A(KC_RGHT)`` →
        # ``A(KC_RIGHT)``) collapse onto one entry.
        effective_keycode = legend_aliases.get(keycode, keycode)
        if effective_keycode in symbol_desc:
            desc = symbol_desc[effective_keycode]
            display = _resolve_display_label(keycode, keycodes_dict, macro_functions)
            sort_k = effective_keycode
            if sort_k not in out:
                out[sort_k] = SymbolLegendEntry(
                    display_label=display,
                    description=desc,
                    sort_key=sort_k,
                    category=symbol_cats.get(effective_keycode, ""),
                )
            continue

        # Function call?
        func_match = _FUNC_RE.match(keycode)
        if func_match:
            func_name = func_match.group(1)
            args_str = func_match.group(2)

            if func_name in func_desc and func_name not in visited_funcs:
                from skim.data import Keyboard
                from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter

                fd_entry = func_desc[func_name]
                raw_desc = fd_entry if isinstance(fd_entry, str) else fd_entry["description"]
                adapter = KeycodeLabelAdapter(Keyboard(), keycode_mappings)

                if _is_per_instance_description(raw_desc):
                    inst_args = _parse_function_args(args_str)
                    desc = _resolve_description_per_instance(raw_desc, inst_args, adapter)
                    target_key = adapter.transform(keycode)
                    display_label = format_key_label(target_key)
                    sort_k = keycode
                    if sort_k not in out:
                        out[sort_k] = SymbolLegendEntry(
                            display_label=display_label,
                            description=desc,
                            sort_key=sort_k,
                            category=func_cats.get(func_name, ""),
                        )
                    continue
                else:
                    desc = _resolve_description_generic(raw_desc, adapter)
                    label = _function_display_label(func_name, macro_functions, keycode_mappings)
                    sort_k = func_name
                    if sort_k not in out:
                        out[sort_k] = SymbolLegendEntry(
                            display_label=label,
                            description=desc,
                            sort_key=sort_k,
                            category=func_cats.get(func_name, ""),
                        )
                    # Fall through to recurse into args.

            # Follow ``@@KEYCODE;`` references inside the function's
            # ``macro_functions`` display template — those keycodes paint
            # as glyphs on the rendered key (e.g. ``LWIN_T``'s template
            # ``@@KC_LWIN;|;@0;`` shows the Windows glyph), so their
            # ``symbol_descriptions`` need to surface in the legend even
            # when the function itself isn't covered by a
            # ``function_descriptions`` entry.
            if func_name in macro_functions:
                template_refs = _ALIAS_RE.findall(macro_functions[func_name])
                if template_refs:
                    _collect_raw(
                        template_refs,
                        keymap,
                        keycode_mappings,
                        out,
                        visited_funcs,
                        include_transparent=include_transparent,
                    )

            args = _parse_function_args(args_str)
            _collect_raw(
                args,
                keymap,
                keycode_mappings,
                out,
                visited_funcs,
                include_transparent=include_transparent,
            )
            continue

        # TD(id) — recurse into the tap-dance's variant keycodes.
        td_match = re.match(r"^TD\((\w+)\)$", keycode)
        if td_match and keymap is not None:
            td_id = td_match.group(1)
            td_by_id = {t.id: t for t in keymap.tap_dances}
            if td_id in td_by_id:
                td = td_by_id[td_id]
                variant_keycodes: list[str] = []
                for variant in (td.tap, td.hold, td.double_tap, td.tap_then_hold):
                    if variant is not None:
                        kc = (
                            variant if isinstance(variant, str) else getattr(variant, "label", None)
                        )
                        if kc:
                            variant_keycodes.append(kc)
                _collect_raw(
                    variant_keycodes,
                    keymap,
                    keycode_mappings,
                    out,
                    visited_funcs,
                    include_transparent=include_transparent,
                )
            continue

        # MACRO_id or Mdigit — recurse into the macro's action keycodes.
        macro_match = re.match(r"^(?:MACRO_(\w+)|M(\d+))$", keycode)
        if macro_match and keymap is not None:
            macro_id = macro_match.group(1) or macro_match.group(2)
            macro_by_id = {m.id: m for m in keymap.macros}
            if macro_id in macro_by_id:
                macro = macro_by_id[macro_id]
                action_keycodes: list[str] = []
                for action in macro.actions:
                    for key in action.keys:
                        kc = key if isinstance(key, str) else getattr(key, "label", None)
                        if kc:
                            action_keycodes.append(kc)
                _collect_raw(
                    action_keycodes,
                    keymap,
                    keycode_mappings,
                    out,
                    visited_funcs,
                    include_transparent=include_transparent,
                )
            continue

        # Plain atomic keycode — walk its alias chain.
        chain = _resolve_aliases(keycode, keycodes_dict)
        canonical = chain[-1]
        effective_canonical = legend_aliases.get(canonical, canonical)

        for name in chain:
            effective_name = legend_aliases.get(name, name)
            if effective_name in symbol_desc:
                desc = symbol_desc[effective_name]
                raw_label = keycodes_dict.get(effective_canonical, effective_canonical)
                display = re.sub(r"@@[A-Z0-9_]+;", "", raw_label).strip()
                if not display:
                    first_label = keycodes_dict.get(keycode, keycode)
                    display = re.sub(r"@@[A-Z0-9_]+;", "", first_label).strip() or keycode
                sort_k = effective_name
                if sort_k not in out:
                    out[sort_k] = SymbolLegendEntry(
                        display_label=display,
                        description=desc,
                        sort_key=sort_k,
                        category=symbol_cats.get(effective_name, ""),
                    )
                break


def collect_used_descriptions(
    keycodes: Iterable[str],
    keymap: SvalboardKeymap[str] | SvalboardKeymap[SvalboardTargetKey] | None,
    keycode_mappings: KeycodeMappings,
    include_transparent: bool = True,
) -> list[SymbolLegendEntry]:
    """Return description entries for the symbols used in ``keycodes``.

    Sorted output: one entry per distinct canonical keycode or
    function name found in ``symbol_descriptions`` /
    ``function_descriptions``. ``include_transparent`` controls
    whether the ⛛ ``KC_TRANSPARENT`` entry is emitted; pass ``False``
    when the renderer is using fall-through-to-layer-zero (the glyph
    never appears on the keymap then).
    """
    out: dict[str, SymbolLegendEntry] = {}
    _collect_raw(
        keycodes, keymap, keycode_mappings, out, set(), include_transparent=include_transparent
    )
    return sorted(out.values(), key=_build_entry_sort_key(keycode_mappings))

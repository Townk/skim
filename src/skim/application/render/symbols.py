# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SYMBOLS section — composables + the entry-resolution data layer.

This module owns both halves of the symbols pipeline:

* **Data layer** — walks each key's raw keycode (pre-resolution),
  recursing through wrapper functions (``LT(N, KC_A)``, ``LCTL(KC_A)``,
  …), tap-dance variants, and macro action keys. Atomic keycodes
  resolve through the ``@@`` alias chain; both the original name and
  every step in the chain are checked against
  ``symbol_descriptions``. Function names are checked against
  ``function_descriptions``. Used by the entry points to pre-collect
  the rows the section will display.

* **Composables** — :func:`SymbolEntry` (one row), :func:`SymbolTable`
  (multi-column grid), :func:`SymbolSection` (section title +
  table).

The orchestration helpers that gate ``collect_used_descriptions``
on ``output.style.show_transparent_fallthrough`` and iterate the
right set of layers live in :mod:`skim.application.render`'s entry
points, not here — symbols module exposes only the algorithmic
primitive plus the section composables.

The symbol legend's accent line is a fixed neutral gray rather than a
palette colour — symbols don't belong to either macros or tap-dances,
so the title strip stays visually neutral. ``column``-major flow is
the default and matches the historical legacy behaviour.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from skim.data import KeycodeMappings, SvalboardKeymap
from skim.domain import SEPARATOR_CHAR, SvalboardTargetKey

from .adjustable_text import AdjustableText, measure_text_width
from .composable import Composable
from .primitives import Column, Component, MetricsComponent, Point, Size
from .render_context import RenderContext, TextStyle
from .rich_text import RichText
from .section_data import format_key_label
from .section_stripe import SectionStripe, SectionStripeMetrics
from .text import Font

if TYPE_CHECKING:
    from skim.domain.adapters.keycode_label_adapter import KeycodeLabelAdapter

# ---------------------------------------------------------------------------
# Per-doc-width ratios — entry-row / glyph / description typography.
# Expressed as fractions of the document width so the symbols section
# stays visually proportional across canvas sizes.
# ---------------------------------------------------------------------------

_ENTRY_ROW_HEIGHT_RATIO = 20.0 / 1600.0
_SYMBOL_FONT_SIZE_RATIO = 13.0 / 1600.0
_DESC_FONT_SIZE_RATIO = 13.0 / 1600.0
_MIN_GLYPH_CELL_RATIO = 4.0 / 1600.0  # measurement floor for blank glyph cells

# Neutral accent — the SYMBOLS title strip is independent of any per-layer
# colour, so the rule and title text use a fixed gray.
_ACCENT_LINE = "#888888"

# Description text is rendered slightly faded so the glyph reads as the
# primary content of each row.
_DESC_OPACITY = 0.75

FlowDirection = Literal["row", "column"]
"""Where adjacent entries in the multi-column grid sit relative to each other.

* ``"row"`` — fill rows left-to-right (row-major). Adjacent indices
  sit in the same row, the next row starts when the current one fills.
* ``"column"`` — fill columns top-to-bottom (column-major; the
  default). Adjacent indices sit in the same column.
"""


# ---------------------------------------------------------------------------
# Entry-resolution data layer
#
# Walks each key's raw keycode pre-resolution and produces one
# :class:`SymbolLegendEntry` per distinct canonical keycode / function
# encountered. Recurses through wrapper functions, tap-dance variants
# and macro actions; resolves atomic keycodes through the ``@@`` alias
# chain. Both the original name and every chain step are checked
# against ``symbol_descriptions``; function names are checked against
# ``function_descriptions``.
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

    Walks ``keycodes_raw`` and follows the chains documented at the top
    of this module.
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


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolSectionMetrics:
    """Metrics exposed by a built :func:`SymbolSection`.

    The single field is the section title strip's ``rule_offset`` —
    surfaced so the parent document doesn't need to import
    :class:`SectionStripeMetrics` just to compute the gap that
    should sit above and below the section.
    """

    rule_offset: float


@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolMetrics:
    """Sizing constants for the symbols composables.

    Owns the entry-level pixel metrics (row height, glyph / description
    font sizes, the glyph cell measurement floor). The four universal
    table spacings (``table_col_spacing`` between columns,
    ``table_row_spacing`` between rows, ``table_header_spacing``
    between the glyph cell and the description, ``section_spacing``
    between the title strip and the table) come from
    :class:`DocumentMetrics` so the symbols section participates in the
    same rhythm every other table-shaped composable uses.
    """

    # Universal table spacings — sourced from ``DocumentMetrics``.
    table_col_spacing: float
    table_header_spacing: float
    table_row_spacing: float

    # Symbol-entry specifics.
    entry_row_height: float
    symbol_font_size: float
    desc_font_size: float
    min_glyph_cell: float

    @classmethod
    def from_ctx(cls, ctx: RenderContext, *, scale: float = 1.0) -> SymbolMetrics:
        """Resolve from the active context's document metrics.

        ``scale`` multiplies the underlying doc-width so the body of a
        body-scaled image (the standalone symbols image, which uses
        ``BODY_SCALE``) renders larger glyphs / text while the chrome
        stays at its unscaled per-image size.
        """
        doc_m = ctx.document_metrics
        w = doc_m.doc_width * scale
        return cls(
            table_col_spacing=doc_m.table_col_spacing * scale,
            table_header_spacing=doc_m.table_header_spacing * scale,
            table_row_spacing=doc_m.table_row_spacing * scale,
            entry_row_height=w * _ENTRY_ROW_HEIGHT_RATIO,
            symbol_font_size=w * _SYMBOL_FONT_SIZE_RATIO,
            desc_font_size=w * _DESC_FONT_SIZE_RATIO,
            min_glyph_cell=w * _MIN_GLYPH_CELL_RATIO,
        )


# ---------------------------------------------------------------------------
# Symbol composables
# ---------------------------------------------------------------------------


def _measure_glyph_width(label: str, *, metrics: SymbolMetrics, color: str) -> float:
    """Width the glyph cell needs to render ``label`` exactly.

    Builds a throwaway :func:`RichText` with no width budget — the
    element reports its own natural size, so going through it keeps
    the column-width pre-pass identical to what the painted entry
    uses. Floors at ``min_glyph_cell`` so blank or whitespace-only
    labels never collapse the column.
    """
    style = TextStyle(font=Font.FINGER_KEY, size=metrics.symbol_font_size, color=color)
    natural = RichText(text=label, style=style).size.width
    return max(natural, metrics.min_glyph_cell)


@Composable(use_context=True)
def SymbolEntry(
    ctx,
    *,
    entry: SymbolLegendEntry,
    text_color: str,
    glyph_cell_width: float,
    scale: float = 1.0,
):
    """One symbol-legend row: glyph cell + description.

    The glyph cell is ``glyph_cell_width`` wide (passed in by the parent
    :func:`SymbolTable` so every entry's glyph centres at the same x);
    the description sits to the right, separated by
    ``table_header_spacing``. Reported width covers both. The glyph
    is rendered through :func:`RichText` so labels carrying Nerd Font
    tokens render with the right per-span fonts.
    """
    metrics = SymbolMetrics.from_ctx(ctx, scale=scale)

    glyph_style = TextStyle(
        font=Font.FINGER_KEY,
        size=metrics.symbol_font_size,
        weight=700,
        color=text_color,
    )
    glyph_el = RichText(
        text=entry.display_label,
        style=glyph_style,
        text_anchor="start",
        dominant_baseline="central",
    )
    desc_el = AdjustableText(
        text=entry.description,
        style=TextStyle(
            font=Font.FINGER_KEY,
            size=metrics.desc_font_size,
            color=text_color,
        ),
        opacity=_DESC_OPACITY,
        text_anchor="start",
        dominant_baseline="central",
    )

    width = glyph_cell_width + metrics.table_header_spacing + desc_el.size.width
    height = metrics.entry_row_height
    size = Size(width, height)

    def draw_at(d, origin):
        cy = origin.y + height / 2
        # Glyph centred horizontally inside the uniform glyph cell.
        glyph_origin = Point(
            origin.x + glyph_cell_width / 2 - glyph_el.size.width / 2,
            cy - glyph_el.size.height / 2,
        )
        glyph_el.draw_at(d, glyph_origin)
        # Description left-aligned immediately after the glyph cell.
        desc_origin = Point(
            origin.x + glyph_cell_width + metrics.table_header_spacing,
            cy - desc_el.size.height / 2,
        )
        desc_el.draw_at(d, desc_origin)

    return size, draw_at


@Composable(use_context=True)
def SymbolTable(
    ctx,
    *,
    entries: list[SymbolLegendEntry],
    text_color: str,
    max_width: float,
    wrap_content: bool = False,
    column_count: int | None = None,
    flow: FlowDirection = "column",
    scale: float = 1.0,
):
    """Multi-column grid of :func:`SymbolEntry` instances.

    The table never exceeds ``max_width``. ``wrap_content`` chooses
    between the two layout policies the canvas needs:

    * ``False`` (default) — fill the budget. Pick the most columns
      that fit at natural width; if column-major flow would leave
      trailing slots empty, snug ``col_count`` to the row count
      actually needed (e.g. 13 entries naturally fitting 10 cols
      → 2 rows → only 7 cols actually populated, so report 7 cols);
      then inflate each column slot so the painted grid spans
      ``max_width`` exactly. Use for sections sharing a parent
      column with a peer that drives the canvas width — the per-
      layer image's symbols section drops here.
    * ``True`` — snug to natural. Pick the most columns that fit
      and report the natural ``col_count * natural_entry_w + gaps``
      width with no inflation. Use for the standalone symbols image,
      where the canvas wraps the table's actual width.

    A positive ``column_count`` overrides the column-count search
    and forces that exact count. With ``wrap_content=True`` the
    table reports the natural width of those N columns; with
    ``wrap_content=False`` the columns inflate to fill ``max_width``.

    Per-entry width is uniform across the grid: widest glyph +
    ``table_header_spacing`` + widest description, plus any slack
    introduced by ``wrap_content=False``. Empty ``entries`` returns
    a zero-sized noop component.

    ``flow`` controls the index → cell mapping:

    * ``"column"`` (default) — column-major. Adjacent entries land in
      the same column; the next column starts when the current one
      fills. Visually keeps related entries (e.g. a numbered category)
      close together vertically.
    * ``"row"`` — row-major. Adjacent entries land in the same row.
    """
    metrics = SymbolMetrics.from_ctx(ctx, scale=scale)
    if not entries:
        size = Size(0.0, 0.0)

        def _noop(d, origin):
            del d, origin

        return size, _noop

    glyph_widths = [
        _measure_glyph_width(e.display_label, metrics=metrics, color=text_color) for e in entries
    ]
    desc_widths = [
        max(
            measure_text_width(e.description, Font.FINGER_KEY, metrics.desc_font_size),
            metrics.min_glyph_cell,
        )
        for e in entries
    ]
    max_glyph_w = max(glyph_widths)
    max_desc_w = max(desc_widths)
    natural_entry_w = max_glyph_w + metrics.table_header_spacing + max_desc_w

    n = len(entries)
    if column_count is not None:
        col_count = max(1, column_count)
    else:
        # The most columns that pack within ``max_width`` at the
        # natural per-entry width.
        col_count = max(
            1,
            int(
                (max_width + metrics.table_col_spacing)
                / (natural_entry_w + metrics.table_col_spacing)
            ),
        )
        if not wrap_content:
            # Snug to the row count actually needed so the
            # inflate-to-fill below doesn't spread visible content
            # thinly across trailing empty columns.
            # ``wrap_content=True`` keeps the natural ``col_count``
            # so the table snugs to that width verbatim.
            row_count_initial = (n + col_count - 1) // col_count
            col_count = (n + row_count_initial - 1) // row_count_initial

    total_gaps = max(0, col_count - 1) * metrics.table_col_spacing
    entry_w = (
        natural_entry_w
        if wrap_content
        else max(natural_entry_w, (max_width - total_gaps) / col_count)
    )
    row_count = (n + col_count - 1) // col_count

    entry_els: list[Component] = [
        SymbolEntry(
            entry=entry,
            text_color=text_color,
            glyph_cell_width=max_glyph_w,
            scale=scale,
        )
        for entry in entries
    ]

    width = col_count * entry_w + total_gaps
    height = (
        row_count * metrics.entry_row_height + max(0, row_count - 1) * metrics.table_row_spacing
    )
    size = Size(width, height)

    def draw_at(d, origin):
        for idx, el in enumerate(entry_els):
            if flow == "row":
                col = idx % col_count
                row = idx // col_count
            else:  # column-major
                col = idx // row_count
                row = idx % row_count
            cell_x = origin.x + col * (entry_w + metrics.table_col_spacing)
            cell_y = origin.y + row * (metrics.entry_row_height + metrics.table_row_spacing)
            el.draw_at(d, Point(cell_x, cell_y))

    return size, draw_at


@Composable(use_context=True)
def SymbolSection(
    ctx,
    *,
    entries: list[SymbolLegendEntry],
    max_width: float,
    wrap_content: bool = False,
    column_count: int | None = None,
    flow: FlowDirection = "column",
    scale: float = 1.0,
):
    """The SYMBOLS section — :func:`SectionStripe` + :func:`SymbolTable`.

    Encapsulates the title strip, the section's neutral accent colour
    and the standard inter-strip / body gap. ``max_width`` is the
    column-allocated budget. ``wrap_content`` chooses the layout
    policy and is forwarded to :func:`SymbolTable`:

    * ``False`` (default) — the section paints exactly ``max_width``
      wide, with the table balancing columns to fill the budget.
    * ``True`` — the table snugs to its natural width and the
      section reports that snug width so the parent canvas can wrap
      the section.

    ``column_count`` pins the table to that exact count.

    ``scale`` is forwarded to the underlying :func:`SymbolTable` so
    the entries enlarge while the section title strip stays at the
    unscaled per-image size.
    """
    palette = ctx.theme.palette
    stripe_metrics = SectionStripeMetrics.for_doc_width(ctx.config.output.layout.width)

    table = SymbolTable(
        entries=entries,
        text_color=palette.text_color,
        max_width=max_width,
        wrap_content=wrap_content,
        column_count=column_count,
        flow=flow,
        scale=scale,
    )
    stripe_width = table.size.width if wrap_content else max_width
    inner = Column(
        [
            SectionStripe(
                title="SYMBOLS",
                count=len(entries),
                width=stripe_width,
                accent_line=_ACCENT_LINE,
                # The standalone symbols image (``wrap_content=True``)
                # carries the ``N ENTRIES`` count for parity with the
                # macros / tap-dances images; the per-layer symbols
                # section (``wrap_content=False``) hides it so the
                # count doesn't compete with the keyboard for
                # attention.
                show_count=wrap_content,
            ),
            table,
        ],
        gap=ctx.document_metrics.section_spacing,
        align="start",
    )
    return MetricsComponent(
        size=inner.size,
        draw_fn=inner.draw_fn,
        metrics=SymbolSectionMetrics(rule_offset=stripe_metrics.rule_offset),
    )


__all__ = [
    "FlowDirection",
    "SymbolLegendEntry",
    "SymbolSection",
    "collect_used_descriptions",
]

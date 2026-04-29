# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Symbol legend rendering — describes the non-obvious symbols used
on a layer (or across the keymap on the overview).

Walks each key's raw keycode (pre-resolution), recursing into wrapper
functions like ``LT(N, KC_A)`` and ``LCTL(KC_A)``, and tap-dance /
macro definitions.  Atomic keycodes resolve through the ``@@`` alias
chain; both the original name and every step in the chain are checked
against ``symbol_descriptions``.  Function names are checked against
``function_descriptions``.

Public entry point: :func:`collect_used_descriptions`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

import drawsvg as draw

from skim.application.render.text import Font, Label, TextPart
from skim.data import KeycodeMappings, SvalboardKeymap
from skim.domain import SvalboardTargetKey

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

_FUNC_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\((.+)\)$")
"""Match ``FUNCNAME(args)`` at the top level."""

_ALIAS_RE = re.compile(r"@@([A-Z0-9_]+);")
"""Match ``@@KEYCODE;`` alias references inside a label string."""


@dataclass(frozen=True, slots=True)
class SymbolLegendEntry:
    """One row in the symbol legend.

    Attributes:
        display_label: The resolved label string shown in the legend's
            left "symbol" cell.
        description: Human-readable description from the yaml data.
        sort_key: Canonical keycode or function name used for deduplication
            and stable ordering.
    """

    display_label: str
    description: str
    sort_key: str


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def _resolve_aliases(
    keycode: str,
    keycodes: dict[str, str],
) -> list[str]:
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


def _get_function_label(
    func_name: str,
    macro_functions: dict[str, str],
) -> str:
    """Return a display label for a function (the non-argument part of the template).

    We strip ``@N;`` and ``#N;`` placeholders and ``|;`` separators from
    the template, then keep only ``%%...;`` nerd-font glyph tokens and any
    remaining plain text.  If nothing meaningful is left, fall back to the
    function name itself.
    """
    template = macro_functions.get(func_name)
    if not template:
        return func_name

    # Remove placeholders and separators
    cleaned = re.sub(r"[#@]\d+;", "", template)
    cleaned = cleaned.replace("|;", "").strip()

    # If the cleaned template has content, use it; otherwise use func_name
    return cleaned if cleaned else func_name


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


def _collect_raw(
    keycodes_raw: Iterable[str],
    keymap: SvalboardKeymap[str] | SvalboardKeymap[SvalboardTargetKey] | None,
    keycode_mappings: KeycodeMappings,
    out: dict[str, SymbolLegendEntry],
    visited_funcs: set[str],
) -> None:
    """Recursive worker that populates ``out`` (sort_key → entry).

    Parameters
    ----------
    keycodes_raw:
        Raw keycode strings to inspect (pre-pre-processing).
    keymap:
        The full keymap object, used to recurse into tap-dance variants
        and macro action keys.  May be ``None`` if unavailable.
    keycode_mappings:
        Full yaml dict (keycodes, pre_processing, macro_functions,
        modifier_union, symbol_descriptions, function_descriptions).
    out:
        Accumulator dict keyed by ``sort_key``.
    visited_funcs:
        Guards against recursive expansion of the same function name.
    """
    keycodes_dict: dict[str, str] = keycode_mappings.get("keycodes", {})
    pre_proc: dict[str, str] = keycode_mappings.get("pre_processing", {})
    macro_functions: dict[str, str] = keycode_mappings.get("macro_functions", {})
    symbol_desc: dict[str, str] = keycode_mappings.get("symbol_descriptions", {})
    func_desc: dict[str, str] = keycode_mappings.get("function_descriptions", {})

    for raw in keycodes_raw:
        # Apply pre-processing normalisation
        keycode = pre_proc.get(raw, raw)

        # --- Function call? ---
        func_match = _FUNC_RE.match(keycode)
        if func_match:
            func_name = func_match.group(1)
            args_str = func_match.group(2)

            # Check function_descriptions
            if func_name in func_desc and func_name not in visited_funcs:
                desc = func_desc[func_name]
                label = _get_function_label(func_name, macro_functions)
                sort_k = func_name
                if sort_k not in out:
                    out[sort_k] = SymbolLegendEntry(
                        display_label=label,
                        description=desc,
                        sort_key=sort_k,
                    )

            # Recurse into args
            args = _parse_function_args(args_str)
            _collect_raw(args, keymap, keycode_mappings, out, visited_funcs)
            continue

        # --- TD(id)? ---
        td_match = re.match(r"^TD\((\w+)\)$", keycode)
        if td_match and keymap is not None:
            td_id = td_match.group(1)
            td_by_id = {t.id: t for t in keymap.tap_dances}
            if td_id in td_by_id:
                td = td_by_id[td_id]
                variant_keycodes: list[str] = []
                for variant in (td.tap, td.hold, td.double_tap, td.tap_then_hold):
                    if variant is not None:
                        kc = variant if isinstance(variant, str) else getattr(variant, "label", None)
                        if kc:
                            variant_keycodes.append(kc)
                _collect_raw(variant_keycodes, keymap, keycode_mappings, out, visited_funcs)
            continue

        # --- MACRO_id or Mdigit? ---
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
                _collect_raw(action_keycodes, keymap, keycode_mappings, out, visited_funcs)
            continue

        # --- Plain atomic keycode ---
        chain = _resolve_aliases(keycode, keycodes_dict)
        for name in chain:
            if name in symbol_desc:
                desc = symbol_desc[name]
                # The display label is the resolved label of the *original* keycode
                # (post pre-processing, through the full alias chain)
                canonical = chain[-1]
                raw_label = keycodes_dict.get(canonical, canonical)
                # Strip any remaining @@; or %% tokens for a clean label
                display = re.sub(r"@@[A-Z0-9_]+;", "", raw_label).strip()
                if not display:
                    # Fall back to the resolved keycode label via the first name
                    first_label = keycodes_dict.get(keycode, keycode)
                    display = re.sub(r"@@[A-Z0-9_]+;", "", first_label).strip() or keycode
                sort_k = name
                if sort_k not in out:
                    out[sort_k] = SymbolLegendEntry(
                        display_label=display,
                        description=desc,
                        sort_key=sort_k,
                    )
                break  # Use the first matching step in the chain


def collect_used_descriptions(
    keycodes: Iterable[str],
    keymap: SvalboardKeymap[str] | SvalboardKeymap[SvalboardTargetKey] | None,
    keycode_mappings: KeycodeMappings,
) -> list[SymbolLegendEntry]:
    """Return description entries for the symbols used in ``keycodes``.

    Parameters
    ----------
    keycodes:
        Raw keycode strings as they appear in the keymap (pre-resolution).
    keymap:
        Full keymap object (for tap-dance and macro recursion).
    keycode_mappings:
        Loaded yaml dict (from ``load_keycode_mappings``).

    Returns
    -------
    list[SymbolLegendEntry]
        Sorted list of entries, one per distinct canonical keycode or
        function name found in ``symbol_descriptions`` /
        ``function_descriptions``.
    """
    out: dict[str, SymbolLegendEntry] = {}
    _collect_raw(keycodes, keymap, keycode_mappings, out, set())
    return sorted(out.values(), key=lambda e: e.sort_key)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# Geometry constants
_SYMBOL_HEADER_HEIGHT = 28
_ENTRY_ROW_HEIGHT = 22
_SYMBOL_CELL_MIN_W = 40.0
_SYMBOL_FONT_SIZE = 11
_DESC_FONT_SIZE = 11
_COLUMN_GAP = 40.0
_SYMBOL_DESC_GAP = 10.0   # gap between symbol cell and description text
_ROW_GAP = 4.0


def _measure_label_width(label: str, font_size: float) -> float:
    """Measure the rendered width of ``label`` at ``font_size``."""
    label_obj = Label(label, Font.FINGER_KEY, text_color="#000")
    width = 0.0
    for part in label_obj.parts:
        font = part.font.load(font_size)
        if isinstance(part, TextPart):
            width += font.getlength(part.text)
        else:
            width += part.measure_width(font)
    return max(width, 4.0)


def symbol_legend_height(
    entries: list[SymbolLegendEntry],
    content_width: float,
) -> float:
    """Return the total height the symbol legend block needs.

    Returns 0 when ``entries`` is empty.
    """
    if not entries:
        return 0.0

    # Estimate column count
    max_symbol_w = max(
        _measure_label_width(e.display_label, _SYMBOL_FONT_SIZE) for e in entries
    )
    symbol_cell_w = max(_SYMBOL_CELL_MIN_W, max_symbol_w + 8.0)

    # Estimate description width
    desc_font = Font.FINGER_KEY.load(_DESC_FONT_SIZE)
    max_desc_w = max(desc_font.getlength(e.description) for e in entries)

    entry_w = symbol_cell_w + _SYMBOL_DESC_GAP + max_desc_w
    col_count = max(1, int((content_width + _COLUMN_GAP) / (entry_w + _COLUMN_GAP)))
    row_count = (len(entries) + col_count - 1) // col_count

    return _SYMBOL_HEADER_HEIGHT + row_count * (_ENTRY_ROW_HEIGHT + _ROW_GAP)


def build_symbol_legend(
    entries: list[SymbolLegendEntry],
    x: float,
    y: float,
    content_width: float,
    palette: object,  # Palette (avoid circular import by keeping loose type)
    use_system_fonts: bool = False,
) -> draw.Group | None:
    """Render the symbol legend block at ``(x, y)``.

    Returns ``None`` when ``entries`` is empty.
    """
    if not entries:
        return None

    from skim.data import Palette

    assert isinstance(palette, Palette)
    text_color = palette.text_color
    accent_line = "#888888"  # neutral-gray, independent of any per-layer color

    # Compute layout geometry
    max_symbol_w = max(
        _measure_label_width(e.display_label, _SYMBOL_FONT_SIZE) for e in entries
    )
    symbol_cell_w = max(_SYMBOL_CELL_MIN_W, max_symbol_w + 8.0)

    desc_font_obj = Font.FINGER_KEY.load(_DESC_FONT_SIZE)
    max_desc_w = max(desc_font_obj.getlength(e.description) for e in entries)

    entry_w = symbol_cell_w + _SYMBOL_DESC_GAP + max_desc_w
    col_count = max(1, int((content_width + _COLUMN_GAP) / (entry_w + _COLUMN_GAP)))

    g = draw.Group()

    label_font = (
        Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value
    )

    # Section header
    n = len(entries)
    g.append(draw.Text(
        "SYMBOLS",
        x=x, y=y + 12,
        font_size=11, font_weight="700", letter_spacing=3,
        text_anchor="start", font_family=label_font, fill=accent_line,
    ))
    g.append(draw.Text(
        f"{n} {'ENTRY' if n == 1 else 'ENTRIES'}",
        x=x + content_width, y=y + 12,
        font_size=10, text_anchor="end", fill="#888", font_weight="400",
        letter_spacing=1, font_family=label_font,
    ))
    g.append(draw.Line(
        sx=x, sy=y + 20, ex=x + content_width, ey=y + 20,
        stroke=accent_line, stroke_opacity=0.5, stroke_width=1.2,
    ))

    # Entries in row-major column flow
    content_y = y + _SYMBOL_HEADER_HEIGHT
    for idx, entry in enumerate(entries):
        col = idx % col_count
        row = idx // col_count
        # Column x: evenly distribute
        col_x = x + col * (entry_w + _COLUMN_GAP)
        row_y = content_y + row * (_ENTRY_ROW_HEIGHT + _ROW_GAP)
        cell_mid_y = row_y + _ENTRY_ROW_HEIGHT / 2

        # Symbol cell background (pill)
        g.append(draw.Rectangle(
            x=col_x, y=row_y + (_ENTRY_ROW_HEIGHT - 18) / 2,
            width=symbol_cell_w, height=18, rx=4, ry=4,
            fill="#FAFAF6", stroke=text_color, stroke_opacity=0.18,
        ))
        # Symbol label centred in cell
        g.append(
            Label(
                entry.display_label,
                Font.FINGER_KEY,
                text_color=text_color,
                background_color="#FAFAF6",
                text_anchor="middle",
                dominant_baseline="central",
            ).build_text(
                col_x + symbol_cell_w / 2,
                cell_mid_y + 0.5,
                _SYMBOL_FONT_SIZE,
                use_system_fonts,
            )
        )
        # Description text
        g.append(draw.Text(
            entry.description,
            x=col_x + symbol_cell_w + _SYMBOL_DESC_GAP,
            y=cell_mid_y + 0.5,
            font_size=_DESC_FONT_SIZE,
            dominant_baseline="central",
            font_family=label_font,
            fill=text_color,
            opacity=0.75,
        ))

    return g

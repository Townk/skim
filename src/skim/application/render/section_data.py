# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Macro / tap-dance data utilities + shared key-label formatting.

A small kit of helpers consumed by the section composables (and
the symbol legend, which reuses the key-label formatter):

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
"""

from skim.data import SvalboardLayout
from skim.domain import SvalboardMacro, SvalboardTapDance
from skim.domain.domain_types import SEPARATOR_CHAR, SvalboardTargetKey


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

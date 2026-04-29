# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Loaders for parsing keymap files from various formats.

This module provides functions for loading Svalboard keymap data from
different file formats (Vial, Keybard, QMK c2json) and sources (files,
stdin). It handles format detection, JSON parsing, and conversion to
the internal SvalboardKeymap structure, including tap-dance and macro
definitions where the source format provides them.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skim.data import SvalboardKeymap, SvalboardLayout
from skim.domain import (
    KeymapType,
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardMacroActionKind,
    SvalboardTapDance,
)
from skim.domain.adapters import KeymapJsonAdapter

EMPTY_LAYER_KEYCODES = frozenset({"KC_NO", "KC_TRNS"})
"""Keycodes that mark a key as inactive on a layer."""


@dataclass(frozen=True, slots=True)
class ParsedKeymap:
    """Bundle of all per-keymap data extracted from a single source file.

    Attributes:
        layers: Layer data in QMK ordering, one list of 60 keycode strings
            per layer.
        tap_dances: Tap-dance definitions from the source. Empty when the
            source format does not carry them (e.g. c2json).
        macros: Macro definitions from the source. Empty when the source
            does not carry them.
    """

    layers: list[list[str]]
    tap_dances: tuple[SvalboardTapDance[str], ...] = ()
    macros: tuple[SvalboardMacro[str], ...] = ()


def is_empty_layer(layer: list[str]) -> bool:
    """Return True if every key on the layer is empty (KC_NO/KC_TRNS)."""
    return all(keycode in EMPTY_LAYER_KEYCODES for keycode in layer)


def _detect_keymap_from_json(data: Any) -> KeymapType:
    """Detect the keymap format from parsed JSON structure."""
    if "layout" in data and "version" in data:
        return KeymapType.VIAL
    if "keymap" in data and isinstance(data["keymap"], list):
        return KeymapType.KEYBARD
    if "layers" in data and isinstance(data["layers"], list):
        return KeymapType.C2JSON
    raise ValueError("Unknown keymap format")


def _detect_format_from_path(path: Path) -> KeymapType | None:
    """Detect the keymap format from file extension."""
    if path.suffix == ".vil":
        return KeymapType.VIAL
    if path.suffix == ".kbi":
        return KeymapType.KEYBARD
    return None


def _vial_keycode_or_none(value: Any) -> str | None:
    """Map Vial's ``"KC_NO"`` sentinel to ``None`` for tap-dance fields."""
    if value is None or value == "KC_NO":
        return None
    return str(value)


def _parse_vial_tap_dances(data: Any) -> tuple[SvalboardTapDance[str], ...]:
    """Parse the top-level ``tap_dance`` array if present.

    Entries with all four variants set to None (i.e. all `KC_NO` in source)
    are silently skipped.
    """
    raw = data.get("tap_dance")
    if not isinstance(raw, list):
        return ()
    tap_dances: list[SvalboardTapDance[str]] = []
    for index, row in enumerate(raw):
        if not isinstance(row, list) or len(row) < 5:
            continue
        td = SvalboardTapDance[str](
            id=str(index),
            tap=_vial_keycode_or_none(row[0]),
            hold=_vial_keycode_or_none(row[1]),
            double_tap=_vial_keycode_or_none(row[2]),
            tap_then_hold=_vial_keycode_or_none(row[3]),
            tapping_term=int(row[4]),
        )
        if td.tap is None and td.hold is None and td.double_tap is None and td.tap_then_hold is None:
            continue
        tap_dances.append(td)
    return tuple(tap_dances)


def _parse_keybard_tap_dances(data: Any) -> tuple[SvalboardTapDance[str], ...]:
    """Parse the top-level ``tapdances`` array if present.

    Entries with all four variants set to None (i.e. all `KC_NO` in source)
    are silently skipped.
    """
    raw = data.get("tapdances")
    if not isinstance(raw, list):
        return ()
    tap_dances: list[SvalboardTapDance[str]] = []
    for entry in raw:
        if not isinstance(entry, dict) or "tdid" not in entry:
            continue
        td = SvalboardTapDance[str](
            id=str(entry["tdid"]),
            tap=_vial_keycode_or_none(entry.get("tap")),
            hold=_vial_keycode_or_none(entry.get("hold")),
            double_tap=_vial_keycode_or_none(entry.get("doubletap")),
            tap_then_hold=_vial_keycode_or_none(entry.get("taphold")),
            tapping_term=int(entry.get("tapms", 200)),
        )
        if td.tap is None and td.hold is None and td.double_tap is None and td.tap_then_hold is None:
            continue
        tap_dances.append(td)
    return tuple(tap_dances)


def _parse_keybard_macros(data: Any) -> tuple[SvalboardMacro[str], ...]:
    """Parse the top-level ``macros`` array if present.

    IDs are 0-based, matching how keycodes reference macros (``M0`` → first
    macro). Entries with no actions are silently skipped.
    """
    raw = data.get("macros")
    if not isinstance(raw, list):
        return ()
    macros: list[SvalboardMacro[str]] = []
    for entry in raw:
        if not isinstance(entry, dict) or "mid" not in entry:
            continue
        mid = entry["mid"]
        if not isinstance(mid, int):
            continue
        parsed_actions = _parse_vial_macro_actions(entry.get("actions", []))
        if not parsed_actions:
            continue
        macros.append(
            SvalboardMacro[str](
                id=str(mid),
                actions=parsed_actions,
            )
        )
    return tuple(macros)


_KEY_ACTION_KINDS: dict[str, SvalboardMacroActionKind] = {
    "tap": SvalboardMacroActionKind.TAP,
    "down": SvalboardMacroActionKind.DOWN,
    "up": SvalboardMacroActionKind.UP,
}


def _parse_c2json_action(raw: Any) -> SvalboardMacroAction[str] | None:
    """Parse a single QMK-schema macro action from its object form."""
    if not isinstance(raw, dict):
        return None
    action = raw.get("action")
    if action in _KEY_ACTION_KINDS:
        keycodes = raw.get("keycodes", [])
        if not isinstance(keycodes, list):
            return None
        return SvalboardMacroAction[str](
            kind=_KEY_ACTION_KINDS[action],
            keys=tuple(str(k) for k in keycodes),
        )
    if action == "text":
        return SvalboardMacroAction[str](
            kind=SvalboardMacroActionKind.TEXT, text=str(raw.get("text", ""))
        )
    if action == "delay":
        return SvalboardMacroAction[str](
            kind=SvalboardMacroActionKind.DELAY,
            duration_ms=int(raw.get("duration", 0)),
        )
    return None


def _parse_c2json_macro_actions(raw: Any) -> tuple[SvalboardMacroAction[str], ...]:
    """Parse the action sequence of a single c2json macro."""
    if not isinstance(raw, list):
        return ()
    parsed = (_parse_c2json_action(action) for action in raw)
    return tuple(action for action in parsed if action is not None)


def _parse_c2json_macros(data: Any) -> tuple[SvalboardMacro[str], ...]:
    """Parse the optional top-level ``macros`` array if present.

    IDs are 0-based, matching how keycodes reference macros (``M0`` → first
    macro). Entries with no actions are silently skipped.
    """
    raw = data.get("macros")
    if not isinstance(raw, list):
        return ()
    macros: list[SvalboardMacro[str]] = []
    for index, actions in enumerate(raw):
        parsed_actions = _parse_c2json_macro_actions(actions)
        if not parsed_actions:
            continue
        macros.append(SvalboardMacro[str](id=str(index), actions=parsed_actions))
    return tuple(macros)


def _parse_vial_action(raw: Any) -> SvalboardMacroAction[str] | None:
    """Parse a single Vial macro action from its array form.

    Action shape: ``[kind, *rest]`` where kind is one of
    ``"tap" | "down" | "up" | "text" | "delay"``. ``tap``/``down``/``up``
    accept one or more keycodes; ``text`` takes a string; ``delay`` takes
    a numeric millisecond duration. Returns ``None`` if ``raw`` is not a
    parseable action.
    """
    if not isinstance(raw, list) or not raw:
        return None
    kind = raw[0]
    if kind in _KEY_ACTION_KINDS:
        keys = tuple(str(k) for k in raw[1:])
        return SvalboardMacroAction[str](kind=_KEY_ACTION_KINDS[kind], keys=keys)
    if kind == "text" and len(raw) >= 2:
        return SvalboardMacroAction[str](kind=SvalboardMacroActionKind.TEXT, text=str(raw[1]))
    if kind == "delay" and len(raw) >= 2:
        return SvalboardMacroAction[str](
            kind=SvalboardMacroActionKind.DELAY, duration_ms=int(raw[1])
        )
    return None


def _parse_vial_macro_actions(raw: Any) -> tuple[SvalboardMacroAction[str], ...]:
    """Parse the action sequence of a single Vial macro."""
    if not isinstance(raw, list):
        return ()
    parsed = (_parse_vial_action(action) for action in raw)
    return tuple(action for action in parsed if action is not None)


def _parse_vial_macros(data: Any) -> tuple[SvalboardMacro[str], ...]:
    """Parse the top-level ``macro`` array if present.

    IDs are 0-based, matching how keycodes reference macros (``M0`` → first
    macro). Entries with no actions are silently skipped.
    """
    raw = data.get("macro")
    if not isinstance(raw, list):
        return ()
    macros: list[SvalboardMacro[str]] = []
    for index, actions in enumerate(raw):
        parsed_actions = _parse_vial_macro_actions(actions)
        if not parsed_actions:
            continue
        macros.append(SvalboardMacro[str](id=str(index), actions=parsed_actions))
    return tuple(macros)


def _parse_vial(data: Any) -> ParsedKeymap:
    """Parse a Vial-format JSON object into a ParsedKeymap.

    Layers come from the top-level ``layout`` key. Tap dances and macros
    are parsed from top-level ``tap_dance`` and ``macro`` keys.
    """
    if "layout" not in data:
        raise ValueError("Missing 'layout' key in vial data")
    layout = data["layout"]
    if not isinstance(layout, list):
        raise ValueError("'layout' must be a list")
    layers = KeymapJsonAdapter.transform(layout, KeymapType.VIAL)
    return ParsedKeymap(
        layers=layers,
        tap_dances=_parse_vial_tap_dances(data),
        macros=_parse_vial_macros(data),
    )


def _parse_keybard(data: Any) -> ParsedKeymap:
    """Parse a Keybard-format JSON object into a ParsedKeymap."""
    if "keymap" not in data:
        raise ValueError("Missing 'keymap' key in keybard data")
    keymap = data["keymap"]
    if not isinstance(keymap, list):
        raise ValueError("'keymap' must be a list")
    layers = KeymapJsonAdapter.transform(keymap, KeymapType.KEYBARD)
    return ParsedKeymap(
        layers=layers,
        tap_dances=_parse_keybard_tap_dances(data),
        macros=_parse_keybard_macros(data),
    )


def _parse_c2json(data: Any) -> ParsedKeymap:
    """Parse a c2json-format JSON object into a ParsedKeymap."""
    if "layers" not in data:
        raise ValueError("Missing 'layers' key in c2json data")
    layers_raw = data["layers"]
    if not isinstance(layers_raw, list):
        raise ValueError("'layers' must be a list")
    for i, layer in enumerate(layers_raw):
        if not isinstance(layer, list):
            raise ValueError(f"Layer {i} must be a list")
    layers = KeymapJsonAdapter.transform(layers_raw, KeymapType.C2JSON)
    return ParsedKeymap(
        layers=layers,
        tap_dances=(),
        macros=_parse_c2json_macros(data),
    )


def load_keymap_json(content: str, keymap_type: KeymapType | None = None) -> ParsedKeymap:
    """Parse keymap JSON content into a :class:`ParsedKeymap`."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    resolved_type = keymap_type or _detect_keymap_from_json(data)

    if resolved_type == KeymapType.VIAL:
        return _parse_vial(data)
    if resolved_type == KeymapType.KEYBARD:
        return _parse_keybard(data)
    return _parse_c2json(data)


def load_keymap_file(file_path: Path) -> ParsedKeymap:
    """Load keymap data from a file as a :class:`ParsedKeymap`."""
    return load_keymap_json(
        file_path.read_text(encoding="utf-8"), _detect_format_from_path(file_path)
    )


def load_keymap_from_stdin() -> ParsedKeymap:
    """Load keymap data from standard input as a :class:`ParsedKeymap`."""
    if sys.stdin.isatty():
        raise ValueError("No data piped to stdin. Use: cat keymap.json | skim generate -")
    keymap_content = sys.stdin.read()
    return load_keymap_json(keymap_content)


def load_keymap(
    file_path: Path | None,
    layer_indices: list[int] | None = None,
) -> SvalboardKeymap[str]:
    """Load a complete keymap from file or stdin."""
    parsed: ParsedKeymap | None = None
    if file_path is None:
        parsed = load_keymap_from_stdin()
    elif file_path.is_file():
        parsed = load_keymap_file(file_path)

    if parsed is not None:
        non_empty = [layer for layer in parsed.layers if not is_empty_layer(layer)]
        indices = layer_indices or list(range(len(non_empty)))
        return SvalboardKeymap(
            layers={
                idx: SvalboardLayout[str].from_sequence(layer)
                for idx, layer in zip(indices, non_empty, strict=False)
            },
            tap_dances=parsed.tap_dances,
            macros=parsed.macros,
        )

    raise ValueError("The provided keymap file path does not exist")

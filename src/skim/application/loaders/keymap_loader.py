# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Loaders for parsing keymap files from various formats.

This module provides functions for loading Svalboard keymap data from
different file formats (Vial, Keybard, QMK c2json) and sources (files,
stdin). It handles format detection, JSON parsing, and conversion to
the internal SvalboardKeymap structure.

The module supports:
- Automatic format detection from file extension or JSON structure
- Loading from files or stdin
- Validation of JSON structure

Example:
    >>> from pathlib import Path
    >>> from skim.application.loaders.keymap_loader import load_keymap
    >>> keymap = load_keymap(Path("my-keymap.kbi"))
    >>> len(keymap.layers)
    8
"""

import json
import sys
from pathlib import Path
from typing import Any

from skim.data import SvalboardKeymap, SvalboardLayout
from skim.domain import KeymapType
from skim.domain.adapters import KeymapJsonAdapter


def _detect_keymap_from_json(data: Any) -> KeymapType:
    """Detect the keymap format from parsed JSON structure.

    Analyzes the JSON structure to determine which application created
    the keymap file.

    Args:
        data: Parsed JSON data from a keymap file.

    Returns:
        The detected KeymapType based on the JSON structure.

    Raises:
        ValueError: If the JSON structure doesn't match any known format.
    """
    if "layout" in data and "version" in data:
        return KeymapType.VIAL

    if "keymap" in data and isinstance(data["keymap"], list):
        return KeymapType.KEYBARD

    if "layers" in data and isinstance(data["layers"], list):
        return KeymapType.C2JSON

    raise ValueError("Unknown keymap format")


def _detect_format_from_path(path: Path) -> KeymapType | None:
    """Detect the keymap format from file extension.

    Args:
        path: Path to the keymap file.

    Returns:
        The KeymapType if detected from extension, or None if unknown.
    """
    if path.suffix == ".vil":
        return KeymapType.VIAL

    elif path.suffix == ".kbi":
        return KeymapType.KEYBARD

    return None


def _get_c2json_layers(data: Any) -> list[list[str]]:
    """Extract and validate layers from c2json format.

    Args:
        data: Parsed JSON data in c2json format.

    Returns:
        List of layer keycodes in QMK ordering.

    Raises:
        ValueError: If the JSON structure is invalid.
    """
    if "layers" not in data:
        raise ValueError("Missing 'layers' key in c2json data")

    layers = data["layers"]
    if not isinstance(layers, list):
        raise ValueError("'layers' must be a list")

    for i, layer in enumerate(layers):
        if not isinstance(layer, list):
            raise ValueError(f"Layer {i} must be a list")

    return KeymapJsonAdapter.transform(layers, KeymapType.C2JSON)


def _get_vial_layers(data: Any) -> list[list[str]]:
    """Extract and validate layers from Vial format.

    Args:
        data: Parsed JSON data in Vial format.

    Returns:
        List of layer keycodes in QMK ordering.

    Raises:
        ValueError: If the JSON structure is invalid.
    """
    if "layout" not in data:
        raise ValueError("Missing 'layout' key in vial data")

    layout = data["layout"]
    if not isinstance(layout, list):
        raise ValueError("'layout' must be a list")

    return KeymapJsonAdapter.transform(layout, KeymapType.VIAL)


def _get_keybard_layers(data: Any) -> list[list[str]]:
    """Extract and validate layers from Keybard format.

    Args:
        data: Parsed JSON data in Keybard format.

    Returns:
        List of layer keycodes in QMK ordering.

    Raises:
        ValueError: If the JSON structure is invalid.
    """
    if "keymap" not in data:
        raise ValueError("Missing 'keymap' key in keybard data")

    keymap = data["keymap"]
    if not isinstance(keymap, list):
        raise ValueError("'keymap' must be a list")
    return KeymapJsonAdapter.transform(keymap, KeymapType.KEYBARD)


def load_keymap_json(content: str, keymap_type: KeymapType | None = None) -> list[list[str]]:
    """Parse keymap JSON content and extract layer data.

    Parses JSON content, detects or uses the specified format, and extracts
    normalized layer data in QMK ordering.

    Args:
        content: JSON string containing keymap data.
        keymap_type: Optional format specification. If None, format is
            auto-detected from JSON structure.

    Returns:
        List of layers, each containing 60 keycode strings in QMK order.

    Raises:
        ValueError: If JSON is invalid or format is unknown.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    resolved_type = keymap_type or _detect_keymap_from_json(data)

    if resolved_type == KeymapType.VIAL:
        return _get_vial_layers(data)

    if resolved_type == KeymapType.KEYBARD:
        return _get_keybard_layers(data)

    return _get_c2json_layers(data)


def load_keymap_file(file_path: Path) -> list[list[str]]:
    """Load keymap data from a file.

    Reads the file, detects format from extension, and parses the content.

    Args:
        file_path: Path to the keymap file (.vil, .kbi, or .json).

    Returns:
        List of layers, each containing 60 keycode strings in QMK order.

    Raises:
        ValueError: If file content is invalid.
        FileNotFoundError: If file doesn't exist.
    """
    return load_keymap_json(
        file_path.read_text(encoding="utf-8"), _detect_format_from_path(file_path)
    )


def load_keymap_from_stdin() -> list[list[str]]:
    """Load keymap data from standard input.

    Reads JSON content from stdin and parses it. Format is auto-detected
    from JSON structure.

    Returns:
        List of layers, each containing 60 keycode strings in QMK order.

    Raises:
        ValueError: If stdin is a TTY (no data piped) or JSON is invalid.
    """
    if sys.stdin.isatty():
        raise ValueError("No data piped to stdin. Use: cat keymap.json | skim generate -")
    keymap_content = sys.stdin.read()
    return load_keymap_json(keymap_content)


def load_keymap(
    file_path: Path | None,
    layer_indices: list[int] | None = None,
) -> SvalboardKeymap[str]:
    """Load a complete keymap from file or stdin.

    Main entry point for loading keymaps. Loads from the specified file
    or from stdin if no file is provided.

    Args:
        file_path: Path to the keymap file, or None to read from stdin.
        layer_indices: Optional list of layer indices to select from the
            source file. Each index identifies the position of a layer in
            the source ``layout``/``keymap`` array; out-of-range indices
            are skipped. If None, every layer is loaded with sequential
            indices (0, 1, 2, ...).

    Returns:
        A SvalboardKeymap containing raw keycode strings for all layers.

    Raises:
        ValueError: If the file doesn't exist or content is invalid.
    """
    keymap_json = None
    if file_path is None:
        keymap_json = load_keymap_from_stdin()
    elif file_path.is_file():
        keymap_json = load_keymap_file(file_path)

    if keymap_json is not None:
        indices = layer_indices or list(range(len(keymap_json)))
        return SvalboardKeymap(
            {
                idx: SvalboardLayout[str].from_sequence(keymap_json[idx])
                for idx in indices
                if 0 <= idx < len(keymap_json)
            }
        )

    raise ValueError("The provided keymap file path does not exist")

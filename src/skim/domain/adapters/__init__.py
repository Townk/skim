# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Adapters for data transformation and external formats.

This package provides adapters for converting between different data
representations, such as:
- Transforming raw keycodes to display labels
- Normalizing keymap JSON from various sources (Vial, Keybard, QMK)
- Converting raw keymaps to renderable target keymaps
"""

from .keycode_label_adapter import KeycodeLabelAdapter
from .keymap_json_adapter import KeymapJsonAdapter
from .keymap_target_adapter import KeymapTargetAdapter

__all__ = [
    "KeycodeLabelAdapter",
    "KeymapJsonAdapter",
    "KeymapTargetAdapter",
]

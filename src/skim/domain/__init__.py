# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Domain layer for skim.

This package contains the core business logic and domain entities, independent
of frameworks or external details. It includes:
- Domain types and enumerations
- Adapter interfaces and implementations
- Utility functions
"""

from .domain_types import (
    NBSP_CHAR,
    SEPARATOR_CHAR,
    Alignment,
    KeyboardSide,
    KeyDirection,
    KeymapType,
    SvalboardMacro,
    SvalboardMacroAction,
    SvalboardMacroActionKind,
    SvalboardTapDance,
    SvalboardTargetKey,
)
from .utils import clip

__all__ = [
    "NBSP_CHAR",
    "SEPARATOR_CHAR",
    "Alignment",
    "KeyboardSide",
    "KeyDirection",
    "KeymapType",
    "SvalboardMacro",
    "SvalboardMacroAction",
    "SvalboardMacroActionKind",
    "SvalboardTapDance",
    "SvalboardTargetKey",
    "clip",
]

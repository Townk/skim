"""Domain layer for Skim.

This layer contains business logic and domain models with no dependencies
on external frameworks or infrastructure.
"""

from .domain_types import (
    NBSP_CHAR,
    SEPARATOR_CHAR,
    Alignment,
    KeyboardSide,
    KeyDirection,
    KeymapType,
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
    "SvalboardTargetKey",
    "clip",
]

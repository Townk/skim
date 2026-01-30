# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Data models and structures for skim.

This package contains the core data structures used throughout the application,
including:
- Configuration models (Pydantic)
- Keyboard layout structures (Finger/Thumb clusters)
- CLI argument transfer objects
- Trie implementation for prefix matching
"""

from types import MappingProxyType
from typing import TypeAlias

from .cli import InputFiles, KeymapGeneratorTargets, OutputFiles, RenderEngine
from .config import (
    Border,
    Keyboard,
    KeyboardFeatures,
    KeyboardLayer,
    Keycode,
    Keycodes,
    LayerColor,
    Layout,
    Output,
    Palette,
    SkimConfig,
    Spacing,
    SplitSidePosition,
    Style,
)
from .keyboard import (
    ClusterT,
    FingerCluster,
    SplitSide,
    SvalboardKeymap,
    SvalboardLayout,
    ThumbCluster,
    zip_clusters,
    zip_layouts,
)
from .trie import Trie

KeycodeMappings: TypeAlias = MappingProxyType[str, dict[str, str]]

__all__ = [
    "InputFiles",
    "KeymapGeneratorTargets",
    "OutputFiles",
    "RenderEngine",
    "Border",
    "Keyboard",
    "KeyboardFeatures",
    "KeyboardLayer",
    "Keycode",
    "Keycodes",
    "LayerColor",
    "Layout",
    "Output",
    "Palette",
    "SkimConfig",
    "Spacing",
    "SplitSidePosition",
    "Style",
    "ClusterT",
    "FingerCluster",
    "SplitSide",
    "SvalboardKeymap",
    "SvalboardLayout",
    "ThumbCluster",
    "zip_clusters",
    "zip_layouts",
    "Trie",
    "KeycodeMappings",
]

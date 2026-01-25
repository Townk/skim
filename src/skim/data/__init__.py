from types import MappingProxyType
from typing import TypeAlias

from .cli import InputFiles, KeymapGeneratorTargets, OutputFiles
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

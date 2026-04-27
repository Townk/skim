# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Domain types and value objects for skim keymap processing.

This module defines the core domain types used throughout the skim application,
including enumerations for alignment, keyboard sides, and key directions, as
well as data classes for representing processed key data.

These types form the foundation of the domain model and are used across
multiple layers of the application.

Attributes:
    SEPARATOR_CHAR: Unicode box-drawing character (│) used to separate
        tap and hold labels on dual-function keys.
    NBSP_CHAR: Non-breaking space character used to allow the same behavior as
        hold-tap symbols, but for any two sides of a lable.

Example:
    >>> from skim.domain.domain_types import KeyboardSide, KeyDirection
    >>> side = KeyboardSide.LEFT
    >>> side.opposite
    <KeyboardSide.RIGHT: 'right'>
    >>> direction = KeyDirection.NORTH
    >>> direction.opposite
    <KeyDirection.SOUTH: 'south'>
"""

from dataclasses import dataclass
from enum import Enum


class Alignment(Enum):
    """Alignment options for positioning elements.

    Used for specifying horizontal or vertical alignment of graphical
    elements within their containers, such as keys within clusters or
    labels within keys.

    Attributes:
        START: Align to the start (left for horizontal, top for vertical).
        CENTER: Center alignment.
        END: Align to the end (right for horizontal, bottom for vertical).

    Example:
        >>> align = Alignment.START
        >>> align.opposite
        <Alignment.END: 'end'>
        >>> Alignment.CENTER.opposite
        <Alignment.CENTER: 'center'>
    """

    __slots__ = ()

    START = "start"
    CENTER = "center"
    END = "end"

    @property
    def opposite(self) -> "Alignment":
        """Get the opposite alignment.

        Returns:
            The opposite alignment: START becomes END and vice versa.
            CENTER returns itself as it has no opposite.

        Example:
            >>> Alignment.START.opposite
            <Alignment.END: 'end'>
        """
        if self == Alignment.START:
            return Alignment.END
        if self == Alignment.END:
            return Alignment.START
        return Alignment.CENTER


class KeyboardSide(Enum):
    """Enumeration of keyboard sides (left or right hand).

    Used to distinguish between the two halves of the split Svalboard
    keyboard, which affects rendering orientation and key positioning.

    Attributes:
        LEFT: The left-hand side of the keyboard.
        RIGHT: The right-hand side of the keyboard.

    Example:
        >>> side = KeyboardSide.LEFT
        >>> side.opposite
        <KeyboardSide.RIGHT: 'right'>
    """

    __slots__ = ()

    LEFT = "left"
    RIGHT = "right"

    @property
    def opposite(self) -> "KeyboardSide":
        """Get the opposite keyboard side.

        Returns:
            LEFT if the current side is RIGHT, and vice versa.

        Example:
            >>> KeyboardSide.RIGHT.opposite
            <KeyboardSide.LEFT: 'left'>
        """
        return KeyboardSide.LEFT if self == KeyboardSide.RIGHT else KeyboardSide.RIGHT


class KeyDirection(Enum):
    """Cardinal directions for directional keys in finger clusters.

    Each finger cluster on the Svalboard has directional keys arranged
    around a center key. This enum represents the four cardinal directions
    used for these surrounding keys.

    The directions correspond to the physical movement required to press
    the key relative to the finger's home position:

    - NORTH: Pushing the finger forward (away from palm)
    - SOUTH: Pulling the finger backward (toward palm)
    - EAST: Moving toward the thumb
    - WEST: Moving away from the thumb

    Attributes:
        NORTH: The northward (forward) direction.
        SOUTH: The southward (backward) direction.
        EAST: The eastward (thumb-ward) direction.
        WEST: The westward (away from thumb) direction.

    Example:
        >>> direction = KeyDirection.NORTH
        >>> direction.opposite
        <KeyDirection.SOUTH: 'south'>
    """

    __slots__ = ()

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"

    @property
    def opposite(self) -> "KeyDirection":
        """Get the opposite cardinal direction.

        Returns:
            The opposite direction: NORTH becomes SOUTH, EAST becomes WEST,
            and vice versa.

        Example:
            >>> KeyDirection.EAST.opposite
            <KeyDirection.WEST: 'west'>
        """
        if self == KeyDirection.NORTH:
            return KeyDirection.SOUTH
        if self == KeyDirection.SOUTH:
            return KeyDirection.NORTH
        if self == KeyDirection.EAST:
            return KeyDirection.WEST
        return KeyDirection.EAST


class KeymapType(Enum):
    """Enumeration of supported keymap file formats.

    Identifies the source format of a keymap file, which determines how
    the file content should be parsed and interpreted.

    Attributes:
        C2JSON: QMK's c2json format, produced by ``qmk c2json`` command.
            Contains raw layer data in QMK's internal ordering.
        VIAL: Vial firmware format (.vil files). Contains keymap data
            with Vial-specific key ordering.
        KEYBARD: Keybard application format (.kbi files). Contains keymap
            data with Keybard-specific key ordering.

    Example:
        >>> KeymapType.VIAL.value
        'vial'
    """

    __slots__ = ()

    C2JSON = "c2json"
    VIAL = "vial"
    KEYBARD = "keybard"


@dataclass(frozen=True, slots=True)
class SvalboardTargetKey:
    """Processed key data ready for rendering.

    Represents a single key after all keycode transformations have been
    applied. Contains the display label and optional metadata about
    layer-switching behavior.

    This is a frozen (immutable) dataclass, ensuring that key data
    cannot be accidentally modified after creation.

    Attributes:
        label: The text label to display on the key. May contain special
            characters like the separator character (│) for dual-function
            keys. Defaults to an empty string.
        layer_switch: The target layer index if this key switches layers
            (e.g., MO(1), LT(2, KC_A)), or None if the key doesn't switch
            layers. Layer indices are 0-based. Defaults to None.
        is_transparent: True when the source keycode belongs to QMK's
            transparent family (KC_TRANSPARENT, KC_TRNS, _______). Downstream
            stages may use this to render the key as a faded fall-through of
            the base-layer label. Defaults to False.

    Example:
        >>> # Simple key with just a label
        >>> key = SvalboardTargetKey(label="A")
        >>> key.label
        'A'

        >>> # Layer-tap key (tap for A, hold for layer 1)
        >>> key = SvalboardTargetKey(label="A│L1", layer_switch=1)
        >>> key.layer_switch
        1
    """

    label: str = ""
    layer_switch: int | None = None
    is_transparent: bool = False


SEPARATOR_CHAR = "│"
"""Unicode box-drawing character used to separate tap and hold labels.

This character (U+2502, BOX DRAWINGS LIGHT VERTICAL) is used to visually
separate the "tap" and "hold" portions of dual-function key labels, such
as layer-tap keys (LT) and mod-tap keys (MT).

Example:
    A layer-tap key that types 'A' on tap and activates layer 1 on hold
    would be displayed as: "A│L1"
"""

NBSP_CHAR = "\u00a0"
"""Non-breaking space character for key labels.

Used in key labels that want to display symbol and text and align the symbol
the same way the skim controls hold-tap symbols alignment. Anything on the left
of the non-breaking space behaves just like the hold symbol in a hold-tap key.

Example:
    A label like "⌘ Cmd" could use NBSP_CHAR to make the symbol show outward
    the key cluster: "⌘\u00a0Cmd".

    This would display "⌘ Cmd" on keys at the left side of the cluster and
    "Cmd ⌘" on keys at the right of the cluster.
"""

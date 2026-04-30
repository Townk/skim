# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable rendering primitives for skim images.

A :class:`CanvasElement` is anything with a known size that can paint
itself at an origin in a ``drawsvg.Drawing``. The :func:`Composable`
decorator turns a builder function returning ``(size, draw_fn)`` into a
factory that yields :class:`CanvasElement` instances — composition is
just calling other composables and using their elements as children.

Why this exists
---------------

Image renderers used to compute their own sizes inline, position
children inline, and append shapes directly to the ``Drawing``. Every
new image variant duplicated that same scaffolding, so a fix in one
place often had to be re-applied in others. With composables, every
piece of the rendered output (a label, a row, a section, the whole
image) is a self-contained element that knows its own extent and how to
paint itself — a parent only ever queries ``size`` and calls
``draw_at`` to lay it out.

Authoring a composable
----------------------

Decorate a function that returns ``(size, draw_fn)`` with
:func:`Composable`. The body has two responsibilities:

  1. Compute the natural extent of the element from its inputs (often
     by querying the sizes of child elements).
  2. Return a closure ``(d, origin) -> None`` that paints into ``d``
     starting at ``origin`` (the element's top-left).

For pure composition (where one composable simply wraps another and
adds no new draw behaviour), a body can return the inner element's
size and bound ``draw_at`` directly::

    @Composable
    def Header(...):
        inner = Row([title, logo], gap=...)
        return inner.size, inner.draw_at
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import wraps
from typing import Protocol

import drawsvg as draw

# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Size:
    """Width × height in SVG units."""

    width: float
    height: float

    @classmethod
    def zero(cls) -> "Size":
        return cls(0.0, 0.0)


@dataclass(frozen=True, slots=True)
class Point:
    """An ``(x, y)`` origin in SVG coordinates."""

    x: float = 0.0
    y: float = 0.0

    def offset(self, dx: float = 0.0, dy: float = 0.0) -> "Point":
        return Point(self.x + dx, self.y + dy)


DrawFn = Callable[[draw.Drawing, Point], None]
"""Signature of the closure produced by a composable's body."""


class CanvasElement(Protocol):
    """Anything with a known size that knows how to paint itself.

    Composition uses these as building blocks: a parent queries
    :attr:`size` to lay out its children, then calls :meth:`draw_at`
    to paint each one.
    """

    @property
    def size(self) -> Size: ...

    def draw_at(self, d: draw.Drawing, origin: Point) -> None: ...


@dataclass(frozen=True, slots=True)
class _Element:
    """Concrete :class:`CanvasElement` produced by :func:`Composable`.

    The draw closure is stored as a private field; ``draw_at`` is a
    method that defers to it. Bound-method semantics let a parent
    composable still delegate by passing ``inner.draw_at`` straight
    through as the ``draw_fn`` of its own return tuple.
    """

    size: Size
    _draw_fn: DrawFn

    def draw_at(self, d: draw.Drawing, origin: Point) -> None:
        self._draw_fn(d, origin)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def Composable(
    builder: Callable[..., tuple[Size, DrawFn]],
) -> Callable[..., CanvasElement]:
    """Wrap a ``(size, draw_fn)`` builder into a ``CanvasElement`` factory.

    The decorated function focuses on:

      1. Computing its size from its inputs (and any child elements).
      2. Returning a draw closure that paints into a Drawing at a given
         origin.

    Calling the decorated function returns a :class:`CanvasElement`
    that can be composed with other composables.
    """

    @wraps(builder)
    def factory(*args, **kwargs) -> CanvasElement:
        size, draw_fn = builder(*args, **kwargs)
        return _Element(size=size, _draw_fn=draw_fn)

    return factory


# ---------------------------------------------------------------------------
# Layout primitives
# ---------------------------------------------------------------------------


def _align_offset(align: str, available: float, used: float) -> float:
    """Return the alignment offset for a child of size ``used``.

    Accepts symmetric vertical and horizontal spellings — ``"start"`` /
    ``"top"`` / ``"left"`` align to the leading edge, ``"end"`` /
    ``"bottom"`` / ``"right"`` to the trailing edge, ``"center"``
    centres the child within ``available``.
    """
    if align in ("center", "middle"):
        return (available - used) / 2.0
    if align in ("end", "bottom", "right"):
        return available - used
    return 0.0  # "start" / "top" / "left" (the default)


@Composable
def Spacer(width: float = 0.0, height: float = 0.0):
    """An invisible element that takes up ``width × height`` of space.

    Useful inside :func:`Row` / :func:`Column` to push siblings apart
    or to reserve fixed gaps that don't follow the container's natural
    spacing.
    """
    size = Size(width, height)

    def draw_at(d, origin):
        del d, origin  # nothing to paint

    return size, draw_at


@Composable
def Row(
    children: Iterable[CanvasElement],
    gap: float = 0.0,
    align: str = "center",
):
    """Lay ``children`` out horizontally, left-to-right.

    ``align`` controls the y-position of children that are shorter than
    the row: ``"top"``, ``"center"``, or ``"bottom"``.
    """
    children_list = list(children)
    width = sum(c.size.width for c in children_list) + max(0, len(children_list) - 1) * gap
    height = max((c.size.height for c in children_list), default=0.0)
    size = Size(width, height)

    def draw_at(d, origin):
        cursor_x = origin.x
        for c in children_list:
            y_off = _align_offset(align, height, c.size.height)
            c.draw_at(d, Point(cursor_x, origin.y + y_off))
            cursor_x += c.size.width + gap

    return size, draw_at


@Composable
def Column(
    children: Iterable[CanvasElement],
    gap: float = 0.0,
    align: str = "start",
):
    """Lay ``children`` out vertically, top-to-bottom.

    ``align`` controls the x-position of children that are narrower
    than the column: ``"start"``, ``"center"``, or ``"end"``.
    """
    children_list = list(children)
    width = max((c.size.width for c in children_list), default=0.0)
    height = sum(c.size.height for c in children_list) + max(0, len(children_list) - 1) * gap
    size = Size(width, height)

    def draw_at(d, origin):
        cursor_y = origin.y
        for c in children_list:
            x_off = _align_offset(align, width, c.size.width)
            c.draw_at(d, Point(origin.x + x_off, cursor_y))
            cursor_y += c.size.height + gap

    return size, draw_at


@Composable
def Padding(
    child: CanvasElement,
    all: float = 0.0,
    *,
    top: float | None = None,
    right: float | None = None,
    bottom: float | None = None,
    left: float | None = None,
):
    """Wrap ``child`` in padding.

    ``all`` sets every side; per-side overrides take precedence when
    supplied.
    """
    pad_top = all if top is None else top
    pad_right = all if right is None else right
    pad_bottom = all if bottom is None else bottom
    pad_left = all if left is None else left
    size = Size(
        child.size.width + pad_left + pad_right,
        child.size.height + pad_top + pad_bottom,
    )

    def draw_at(d, origin):
        child.draw_at(d, origin.offset(pad_left, pad_top))

    return size, draw_at


@Composable
def BorderedFrame(
    child: CanvasElement,
    *,
    border_radius: float = 0.0,
    background: str = "white",
    border: str | None = None,
    border_width: float = 0.0,
):
    """Paint a rounded rectangle behind ``child`` and overlay it.

    The frame's natural size matches ``child``'s — the rectangle is
    drawn at the same extent, so callers typically wrap the child in
    :func:`Padding` first if they want breathing room between the
    border and the content.
    """
    size = child.size

    def draw_at(d, origin):
        d.append(
            draw.Rectangle(
                x=origin.x,
                y=origin.y,
                width=size.width,
                height=size.height,
                rx=border_radius,
                ry=border_radius,
                fill=background,
                stroke=border,
                stroke_width=border_width if border else None,
            )
        )
        child.draw_at(d, origin)

    return size, draw_at

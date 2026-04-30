# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Composable rendering primitives for skim images.

A :class:`Component` is anything with a known size that can paint
itself at an origin in a ``drawsvg.Drawing``. The :func:`Composable`
decorator marks a function as one that constructs a :class:`BaseComponent`
(or a typed subclass), so composition is just calling other composables
and using the components they produce as children.

Why this exists
---------------

Image renderers used to compute their own sizes inline, position
children inline, and append shapes directly to the ``Drawing``. Every
new image variant duplicated that same scaffolding, so a fix in one
place often had to be re-applied in others. With composables, every
piece of the rendered output (a label, a row, a section, the whole
image) is a self-contained element that knows its own extent and how
to paint itself — a parent only ever queries ``size`` and calls
``draw_at`` to lay it out.

Authoring a composable
----------------------

Decorate the function with :func:`Composable`. The body has two
responsibilities:

  1. Compute the natural extent of the element from its inputs (often
     by querying the sizes of child elements).
  2. Return a closure ``(d, origin) -> None`` that paints into ``d``
     starting at ``origin`` (the element's top-left).

For the common case the body returns a ``(size, draw_fn)`` tuple and
the decorator wraps it into a plain :class:`BaseComponent`::

    @Composable
    def Label(text: str, font_size: float):
        size = _measure(text, font_size)

        def draw(d, origin): ...

        return size, draw

For pure composition (one composable simply wrapping another), the
body can return the inner component's ``(size, draw_at)`` directly —
``draw_at`` is a bound method whose signature matches ``DrawFn``::

    @Composable
    def Header(...):
        inner = Row([title, logo], gap=...)
        return inner.size, inner.draw_at

When a composable needs to expose extra information beyond ``size`` /
``draw_at`` (e.g. a thumb cluster surfacing per-indicator anchor points
to the connector router), define a typed subclass of
:class:`BaseComponent` and return an instance of that subclass
directly::

    @dataclass(frozen=True, slots=True, kw_only=True)
    class ThumbClusterComponent(BaseComponent):
        connector_anchors: tuple[ConnectorAnchor, ...]

    @Composable
    def ThumbCluster(...) -> ThumbClusterComponent:
        size = ...
        anchors = (...)
        def draw(d, origin): ...
        return ThumbClusterComponent(
            size=size, draw_fn=draw, connector_anchors=anchors,
        )

Parents that need the extra fields type the variable as the subclass;
parents that only need ``size`` / ``draw_at`` rely on the
:class:`Component` Protocol view automatically.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import wraps
from typing import Any, ParamSpec, Protocol, TypeVar, overload

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


class _DrawTarget(Protocol):
    """Anything composables can paint into — i.e. anything with ``.append``.

    ``drawsvg.Drawing`` and ``drawsvg.Group`` both qualify (their
    ``append`` signatures are compatible) but they don't share a common
    ancestor in drawsvg, so we use a structural Protocol instead of a
    Union to keep the relationship implicit.

    The parameter name and ``Any`` element type are chosen to match
    drawsvg's actual ``Drawing.append`` / ``Group.append`` signatures
    so pyright accepts both as structurally satisfying this Protocol —
    Protocol parameters are contravariant (a stricter element type
    here would reject the more permissive real implementations) and
    pyright also checks parameter names for positional-or-keyword
    arguments.
    """

    def append(self, element: Any) -> None: ...


DrawFn = Callable[[_DrawTarget, Point], None]
"""Signature of the closure produced by a composable's body."""


class Component(Protocol):
    """Anything with a known size that knows how to paint itself.

    Composition uses these as building blocks: a parent queries
    :attr:`size` to lay out its children, then calls :meth:`draw_at`
    to paint each one.

    ``size`` is declared as an attribute (not ``@property``) so plain
    dataclass fields satisfy it without pyright flagging a method/
    field override mismatch when subclasses define ``size: Size``.
    """

    size: Size

    def draw_at(self, d: _DrawTarget, origin: Point) -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class BaseComponent(Component):
    """Canonical :class:`Component` implementation — size + a draw closure.

    The default component type produced by :func:`Composable` from a
    ``(size, draw_fn)`` tuple. Composables that need to expose extra
    metadata to their parents (e.g. per-indicator anchor points)
    subclass this and return an instance of the subclass directly.
    Subclasses should themselves be ``@dataclass(frozen=True,
    slots=True, kw_only=True)``.

    ``draw_fn`` is stored as a field but is invoked through the
    :meth:`draw_at` method so the public surface stays consistent with
    the :class:`Component` protocol; ``draw_at`` is a bound method
    that callers can pass straight through as a ``DrawFn`` when a
    parent composable simply delegates to a child.

    Inherits explicitly from :class:`Component` — pyright would accept
    structural conformance, but the explicit relationship is
    self-documenting and makes typed subclasses (``XComponent``)
    automatically inherit it.
    """

    size: Size
    draw_fn: DrawFn

    def draw_at(self, d: _DrawTarget, origin: Point) -> None:
        self.draw_fn(d, origin)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


_P = ParamSpec("_P")
_C = TypeVar("_C", bound=BaseComponent)
_BuilderResult = tuple[Size, DrawFn]


@overload
def Composable(builder: Callable[_P, _C]) -> Callable[_P, _C]: ...


@overload
def Composable(builder: Callable[_P, _BuilderResult]) -> Callable[_P, BaseComponent]: ...


def Composable(
    builder: Callable[_P, BaseComponent | _BuilderResult],
) -> Callable[_P, BaseComponent]:
    """Mark a function as a composable.

    The decorated function may return either:

      * ``(size, draw_fn)`` — auto-wrapped into a plain
        :class:`BaseComponent`.
      * a :class:`BaseComponent` instance (or subclass) — passed
        through unchanged so typed subclasses keep their extra
        metadata.

    Composition is just calling decorated functions and using the
    components they produce as children of other composables.
    """

    @wraps(builder)
    def factory(*args: _P.args, **kwargs: _P.kwargs) -> BaseComponent:
        result = builder(*args, **kwargs)
        if isinstance(result, BaseComponent):
            return result
        size, draw_fn = result
        return BaseComponent(size=size, draw_fn=draw_fn)

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
    children: Iterable[Component],
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
    children: Iterable[Component],
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
    child: Component,
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
def Align(
    child: Component,
    *,
    width: float | None = None,
    height: float | None = None,
    horizontal: str = "start",
    vertical: str = "start",
):
    """Place ``child`` inside a larger box, aligned to one of its edges.

    When ``width`` (or ``height``) is supplied and exceeds the child's
    natural extent, the child is positioned within the resulting box
    according to ``horizontal`` / ``vertical`` (``start`` / ``center`` /
    ``end``). When the dimension is omitted it defaults to the child's
    natural extent. Useful for right-aligning a footer inside a wider
    column or centring a small child inside a fixed slot.
    """
    box_w = width if width is not None and width > child.size.width else child.size.width
    box_h = height if height is not None and height > child.size.height else child.size.height
    size = Size(box_w, box_h)

    def draw_at(d, origin):
        dx = _align_offset(horizontal, box_w, child.size.width)
        dy = _align_offset(vertical, box_h, child.size.height)
        child.draw_at(d, origin.offset(dx, dy))

    return size, draw_at


@Composable
def BorderedFrame(
    child: Component,
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

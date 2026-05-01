# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Primitive types and layout building blocks for the composable framework.

The "primitives" module is the bottom layer of the rendering stack —
value types, the :class:`Component` Protocol that every composable
implements, the canonical :class:`BaseComponent` implementation, and
the four generic layout helpers that any composition uses.

Order of declarations in this file (bottom-up):

* :class:`Canvas` — the structural Protocol any drawsvg target
  satisfies (``Drawing`` / ``Group``).
* :class:`Point`, :class:`Size` — value types.
* :data:`DrawFn` — the ``(Canvas, Point) -> None`` paint closure
  signature.
* :class:`Padding` — per-side inset value object.
* :class:`Component`, :class:`BaseComponent`,
  :class:`MetricsComponent` — the contract every composable
  satisfies, the canonical implementation, and the typed-subclass
  variant that also exposes a ``metrics`` namespace.
* :func:`align_within` — pure helper for parent-driven alignment.
* :func:`Spacer`, :func:`Row`, :func:`Column` — generic layout
  primitives.

The :func:`Composable` decorator lives in :mod:`composable` (one
tier up); it's the "framework" built on top of these primitives.

Importing
---------

Direct imports — there is no re-export from :mod:`composable`. New
code that needs ``Size`` / ``Point`` / ``Padding`` / a layout
primitive imports it from here::

    from .primitives import Canvas, Padding, Point, Row, Size, Spacer
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

# ---------------------------------------------------------------------------
# Canvas — the paint target Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Canvas(Protocol):
    """Anything composables can paint into — i.e. anything with ``.append``.

    ``drawsvg.Drawing`` and ``drawsvg.Group`` both qualify (their
    ``append`` signatures are compatible) but they don't share a
    common ancestor in drawsvg, so we use a structural Protocol
    instead of a Union to keep the relationship implicit.

    The parameter name and ``Any`` element type are chosen to match
    drawsvg's actual ``Drawing.append`` / ``Group.append`` signatures
    so pyright accepts both as structurally satisfying this Protocol —
    Protocol parameters are contravariant (a stricter element type
    here would reject the more permissive real implementations) and
    pyright also checks parameter names for positional-or-keyword
    arguments.
    """

    def append(self, element: Any) -> None: ...


# ---------------------------------------------------------------------------
# Geometry value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Point:
    """An ``(x, y)`` origin in SVG coordinates."""

    x: float = 0.0
    y: float = 0.0

    def offset(self, dx: float = 0.0, dy: float = 0.0) -> Point:
        return Point(self.x + dx, self.y + dy)


@dataclass(frozen=True, slots=True)
class Size:
    """Width × height in SVG units."""

    width: float
    height: float

    @classmethod
    def zero(cls) -> Size:
        return cls(0.0, 0.0)


DrawFn = Callable[[Canvas, Point], None]
"""Signature of the closure produced by a composable's body."""


# ---------------------------------------------------------------------------
# Padding (per-side inset value object)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, init=False)
class Padding:
    """Per-side inset values — a value object, not a composable.

    Components that need to apply padding to their content take a
    :class:`Padding` parameter (or read one from context) and offset
    their content by ``padding.left`` / ``padding.top`` while
    growing their reported size by ``padding.horizontal`` /
    ``padding.vertical``. Padding is the parent's concern, not its
    own component.

    Several constructors for ergonomic use::

        Padding()  # zero on all sides
        Padding(10)  # all sides = 10
        Padding(10, 20)  # vertical=10, horizontal=20
        Padding(10, 20, 30, 40)  # top, right, bottom, left
        Padding(all=10)  # same as Padding(10)
        Padding(vertical=10, horizontal=20)  # same as Padding(10, 20)
        Padding(top=10, right=20, bottom=5)  # per-side overrides
    """

    top: float
    right: float
    bottom: float
    left: float

    def __init__(
        self,
        *args: float,
        all: float | None = None,
        vertical: float | None = None,
        horizontal: float | None = None,
        top: float | None = None,
        right: float | None = None,
        bottom: float | None = None,
        left: float | None = None,
    ) -> None:
        # Resolve from positional args first; CSS-style 1/2/4-value forms.
        if len(args) == 1:
            t_v = r_v = b_v = l_v = float(args[0])
        elif len(args) == 2:
            t_v = b_v = float(args[0])
            r_v = l_v = float(args[1])
        elif len(args) == 4:
            t_v, r_v, b_v, l_v = (float(v) for v in args)
        elif not args:
            t_v = r_v = b_v = l_v = 0.0
        else:
            raise TypeError(
                f"Padding() accepts 0, 1, 2, or 4 positional arguments, got {len(args)}"
            )

        # Then layer keyword groups on top, narrowest first so per-side
        # wins over symmetric, and symmetric wins over ``all``.
        if all is not None:
            t_v = r_v = b_v = l_v = float(all)
        if vertical is not None:
            t_v = b_v = float(vertical)
        if horizontal is not None:
            r_v = l_v = float(horizontal)
        if top is not None:
            t_v = float(top)
        if right is not None:
            r_v = float(right)
        if bottom is not None:
            b_v = float(bottom)
        if left is not None:
            l_v = float(left)

        # Frozen dataclass — bypass the freeze to set the resolved values.
        object.__setattr__(self, "top", t_v)
        object.__setattr__(self, "right", r_v)
        object.__setattr__(self, "bottom", b_v)
        object.__setattr__(self, "left", l_v)

    @property
    def horizontal(self) -> float:
        """Total horizontal inset (``left + right``)."""
        return self.left + self.right

    @property
    def vertical(self) -> float:
        """Total vertical inset (``top + bottom``)."""
        return self.top + self.bottom


# ---------------------------------------------------------------------------
# Component contract + canonical implementation
# ---------------------------------------------------------------------------


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

    def draw_at(self, d: Canvas, origin: Point) -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class BaseComponent(Component):
    """Canonical :class:`Component` implementation — size + a draw closure.

    The default component type produced by the ``@Composable``
    decorator from a ``(size, draw_fn)`` tuple. Composables that need
    to expose extra metadata to their parents (e.g. per-indicator
    anchor points) subclass this and return an instance of the
    subclass directly. Subclasses should themselves be
    ``@dataclass(frozen=True, slots=True, kw_only=True)``.

    ``draw_fn`` is stored as a field but is invoked through the
    :meth:`draw_at` method so the public surface stays consistent
    with the :class:`Component` protocol; ``draw_at`` is a bound
    method that callers can pass straight through as a ``DrawFn``
    when a parent composable simply delegates to a child.

    Inherits explicitly from :class:`Component` — pyright would
    accept structural conformance, but the explicit relationship is
    self-documenting and makes typed subclasses (``XComponent``)
    automatically inherit it.
    """

    size: Size
    draw_fn: DrawFn

    def draw_at(self, d: Canvas, origin: Point) -> None:
        self.draw_fn(d, origin)


_M = TypeVar("_M")


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricsComponent(BaseComponent, Generic[_M]):
    """A :class:`BaseComponent` that exposes its component-specific metrics.

    Convention: every "real" composable (anything beyond a layout
    primitive) returns a :class:`MetricsComponent` parameterised by a
    frozen dataclass that captures everything its parent might want
    to read — resolved widths, dynamic truncation outcomes, per-row
    heights, anchor points, etc. Layout primitives (``Spacer``,
    ``Row``, ``Column``) keep returning plain :class:`BaseComponent`
    since they have no component-specific metrics worth exposing.

    The two-tier surface keeps ``component.size`` and
    ``component.draw_at`` on the protocol contract while
    component-specific data lives behind a single, predictable
    namespace::

        @dataclass(frozen=True, slots=True, kw_only=True)
        class TapDanceTableMetrics:
            cell_width: float
            name_column_width: float
            ...


        @Composable(use_context=True)
        def TapDanceTable(ctx, *, tap_dances) -> MetricsComponent[TapDanceTableMetrics]:
            metrics = TapDanceTableMetrics.compute(ctx, tap_dances)
            ...
            return MetricsComponent(size=..., draw_fn=..., metrics=metrics)
    """

    metrics: _M


# ---------------------------------------------------------------------------
# Alignment helper
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


def align_within(
    outer: Size,
    inner: Size,
    *,
    horizontal: str = "start",
    vertical: str = "start",
) -> Point:
    """Return the offset placing ``inner`` inside ``outer`` per alignment.

    Pure helper used by composables that need to position one rect
    inside another. Alignment is the parent's concern (it owns the
    layout decision), so the helper hands back a :class:`Point` and
    the caller paints accordingly.

    ``horizontal`` accepts ``"start"`` / ``"left"``, ``"center"`` /
    ``"middle"``, ``"end"`` / ``"right"``; ``vertical`` accepts
    ``"start"`` / ``"top"``, ``"center"`` / ``"middle"``, ``"end"`` /
    ``"bottom"``. Misaligned axes (inner larger than outer) snap to
    the leading edge.
    """
    return Point(
        _align_offset(horizontal, outer.width, inner.width),
        _align_offset(vertical, outer.height, inner.height),
    )


# ---------------------------------------------------------------------------
# Layout primitives
# ---------------------------------------------------------------------------


def Spacer(width: float = 0.0, height: float = 0.0) -> BaseComponent:
    """An invisible element that takes up ``width × height`` of space.

    Useful inside :func:`Row` / :func:`Column` to push siblings apart
    or to reserve fixed gaps that don't follow the container's natural
    spacing.
    """
    size = Size(width, height)

    def draw_at(d: Canvas, origin: Point) -> None:
        del d, origin  # nothing to paint

    return BaseComponent(size=size, draw_fn=draw_at)


def Row(
    children: Iterable[Component],
    gap: float = 0.0,
    align: str = "center",
) -> BaseComponent:
    """Lay ``children`` out horizontally, left-to-right.

    ``align`` controls the y-position of children that are shorter than
    the row: ``"top"``, ``"center"``, or ``"bottom"``.
    """
    children_list = list(children)
    width = sum(c.size.width for c in children_list) + max(0, len(children_list) - 1) * gap
    height = max((c.size.height for c in children_list), default=0.0)
    size = Size(width, height)

    def draw_at(d: Canvas, origin: Point) -> None:
        cursor_x = origin.x
        for c in children_list:
            y_off = _align_offset(align, height, c.size.height)
            c.draw_at(d, Point(cursor_x, origin.y + y_off))
            cursor_x += c.size.width + gap

    return BaseComponent(size=size, draw_fn=draw_at)


def Column(
    children: Iterable[Component],
    gap: float = 0.0,
    align: str = "start",
) -> BaseComponent:
    """Lay ``children`` out vertically, top-to-bottom.

    ``align`` controls the x-position of children that are narrower
    than the column: ``"start"``, ``"center"``, or ``"end"``.
    """
    children_list = list(children)
    width = max((c.size.width for c in children_list), default=0.0)
    height = sum(c.size.height for c in children_list) + max(0, len(children_list) - 1) * gap
    size = Size(width, height)

    def draw_at(d: Canvas, origin: Point) -> None:
        cursor_y = origin.y
        for c in children_list:
            x_off = _align_offset(align, width, c.size.width)
            c.draw_at(d, Point(origin.x + x_off, cursor_y))
            cursor_y += c.size.height + gap

    return BaseComponent(size=size, draw_fn=draw_at)


__all__ = [
    "BaseComponent",
    "Canvas",
    "Column",
    "Component",
    "DrawFn",
    "MetricsComponent",
    "Padding",
    "Point",
    "Row",
    "Size",
    "Spacer",
    "align_within",
]

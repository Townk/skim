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
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar, overload, runtime_checkable

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


class CompassDirection(Enum):
    """Eight-compass direction primitive for the rendering layer.

    Used wherever a 2D direction needs naming — layer-indicator
    placement around a Svalboard key, the heading of an
    overview-connector path, the offset side of an inline badge,
    etc. Lives here next to :class:`Point` because it's a
    presentational value type with no domain semantics; the
    domain-side :class:`~skim.domain.KeyDirection` (cardinals only,
    "physical finger position") stays separate.

    String values use kebab-case (``"north-east"``) — the
    presentational kebab convention you'd see in CSS / map data —
    rather than the snake_case the Python member name uses.
    Existing single-word direction enums in the codebase
    (e.g. :class:`~skim.domain.KeyboardSide`) didn't have a
    multi-word case to set precedent; this is the first.
    """

    NORTH = "north"
    NORTH_EAST = "north-east"
    EAST = "east"
    SOUTH_EAST = "south-east"
    SOUTH = "south"
    SOUTH_WEST = "south-west"
    WEST = "west"
    NORTH_WEST = "north-west"

    @property
    def mirrored_horizontal(self) -> CompassDirection:
        """Reflection across a vertical axis — east ↔ west.

        ``NORTH`` and ``SOUTH`` stay put (they're on the axis);
        the eastern half (``E``, ``NE``, ``SE``) swaps with the
        western half (``W``, ``NW``, ``SW``). Used by the Svalboard
        key composables to flip indicator placement for the
        opposite-hand cluster — the right hand's outward-facing
        ``EAST`` becomes the left hand's outward-facing ``WEST``.
        """
        return _HORIZONTAL_MIRROR[self]

    @property
    def unit_vector(self) -> tuple[float, float]:
        """``(dx, dy)`` unit vector pointing in this compass direction.

        SVG screen coords — y grows downward — so ``SOUTH`` is
        ``(0, 1)`` and ``NORTH`` is ``(0, -1)``. The diagonal
        directions return a normalised ``±1/√2`` on each axis so
        the magnitude is unit-length. Useful for translating an
        anchor point in a given direction by a known distance:
        ``anchor.offset(dist * dx, dist * dy)``.
        """
        return _UNIT_VECTOR[self]


_HORIZONTAL_MIRROR: dict[CompassDirection, CompassDirection] = {
    CompassDirection.NORTH: CompassDirection.NORTH,
    CompassDirection.NORTH_EAST: CompassDirection.NORTH_WEST,
    CompassDirection.EAST: CompassDirection.WEST,
    CompassDirection.SOUTH_EAST: CompassDirection.SOUTH_WEST,
    CompassDirection.SOUTH: CompassDirection.SOUTH,
    CompassDirection.SOUTH_WEST: CompassDirection.SOUTH_EAST,
    CompassDirection.WEST: CompassDirection.EAST,
    CompassDirection.NORTH_WEST: CompassDirection.NORTH_EAST,
}

# 1 / sqrt(2) — diagonal unit-vector component. Cached as a constant
# so the lookup table below stays a plain dict literal rather than a
# computed-at-import expression.
_DIAG = 0.7071067811865476

_UNIT_VECTOR: dict[CompassDirection, tuple[float, float]] = {
    CompassDirection.NORTH: (0.0, -1.0),
    CompassDirection.NORTH_EAST: (_DIAG, -_DIAG),
    CompassDirection.EAST: (1.0, 0.0),
    CompassDirection.SOUTH_EAST: (_DIAG, _DIAG),
    CompassDirection.SOUTH: (0.0, 1.0),
    CompassDirection.SOUTH_WEST: (-_DIAG, _DIAG),
    CompassDirection.WEST: (-1.0, 0.0),
    CompassDirection.NORTH_WEST: (-_DIAG, -_DIAG),
}


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
# Child-collector plumbing for `with`-block tree building
# ---------------------------------------------------------------------------


# Stack of active container builders — when a composable executes inside a
# ``with Row(...)`` / ``with Column(...)`` block, the freshly-built component
# auto-attaches to the topmost builder. Tuple instead of list so the
# ContextVar default doesn't accidentally share mutable state across contexts.
_collector_stack: ContextVar[tuple[_ContainerBuilder, ...]] = ContextVar(
    "_skim_collector_stack",
    default=(),
)


def _push_collector(c: _ContainerBuilder):
    """Push ``c`` onto the active-collector stack; returns a ContextVar token."""
    return _collector_stack.set(_collector_stack.get() + (c,))


def _pop_collector(token) -> None:
    """Pop the top collector via the token returned by :func:`_push_collector`."""
    _collector_stack.reset(token)


def _current_collector() -> _ContainerBuilder | None:
    """Return the topmost active collector, or ``None`` if no ``with`` block is open."""
    stack = _collector_stack.get()
    return stack[-1] if stack else None


def _maybe_register(component: Component) -> None:
    """Register ``component`` with the active collector if one is open.

    Called by the ``@Composable`` decorator after building a component, and
    by the layout primitives below after assembling a child list. No-op
    when there's no active ``with`` block — the component is just returned
    to the caller as a value.
    """
    parent = _current_collector()
    if parent is not None:
        parent._add(component)


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

    component = BaseComponent(size=size, draw_fn=draw_at)
    _maybe_register(component)
    return component


def _build_row(children: list[Component], gap: float, align: str) -> BaseComponent:
    width = sum(c.size.width for c in children) + max(0, len(children) - 1) * gap
    height = max((c.size.height for c in children), default=0.0)
    size = Size(width, height)

    def draw_at(d: Canvas, origin: Point) -> None:
        cursor_x = origin.x
        for c in children:
            y_off = _align_offset(align, height, c.size.height)
            c.draw_at(d, Point(cursor_x, origin.y + y_off))
            cursor_x += c.size.width + gap

    return BaseComponent(size=size, draw_fn=draw_at)


def _build_column(children: list[Component], gap: float, align: str) -> BaseComponent:
    width = max((c.size.width for c in children), default=0.0)
    height = sum(c.size.height for c in children) + max(0, len(children) - 1) * gap
    size = Size(width, height)

    def draw_at(d: Canvas, origin: Point) -> None:
        cursor_y = origin.y
        for c in children:
            x_off = _align_offset(align, width, c.size.width)
            c.draw_at(d, Point(origin.x + x_off, cursor_y))
            cursor_y += c.size.height + gap

    return BaseComponent(size=size, draw_fn=draw_at)


def _noop_draw(d: Canvas, origin: Point) -> None:
    """Default ``draw_fn`` for a :class:`_ContainerBuilder` before its ``__exit__``."""
    del d, origin


class _ContainerBuilder:
    """Lazily-built :func:`Row` / :func:`Column` for ``with``-block trees.

    Returned when ``Row(...)`` / ``Column(...)`` is called WITHOUT a
    ``children`` arg — the child list is collected from composables
    invoked inside the ``with`` block, then the actual component is
    built on ``__exit__``. After exit the builder's ``size`` /
    ``draw_fn`` / ``draw_at`` mirror the built component, so it
    satisfies the :class:`Component` Protocol and can be passed
    anywhere a Component is expected.

    Usage::

        with Column(gap=10) as document:
            Header(title=..., min_gap=..., max_width=...)
            MacroSection(macros=..., content_width=..., scale=...)
            if has_footer:
                Footer(text=..., max_width=...)
        # ``document`` now satisfies Component — pass to KeymapDocument /
        # render / further composition.

    ``size`` and ``draw_fn`` are real (mutable) attributes — not
    properties — so they're structurally compatible with the
    :class:`Component` Protocol's invariant ``size: Size`` /
    ``draw_fn: DrawFn`` declarations. Pre-``__exit__`` they hold
    placeholder zero values; ``draw_at`` raises a clearer error
    when called before the with-block closes.
    """

    __slots__ = (
        "_kind",
        "_gap",
        "_align",
        "_collected",
        "_built",
        "_token",
        "size",
        "draw_fn",
    )

    def __init__(self, kind: str, gap: float, align: str) -> None:
        self._kind = kind
        self._gap = gap
        self._align = align
        self._collected: list[Component] = []
        self._built: BaseComponent | None = None
        self._token = None
        # Placeholder values until ``__exit__`` builds the real component.
        self.size: Size = Size(0.0, 0.0)
        self.draw_fn: DrawFn = _noop_draw

    def _add(self, child: Component) -> None:
        if self._built is not None:
            raise RuntimeError(
                "Cannot add a child to a closed container builder; "
                "make sure the composable runs inside the matching ``with`` block."
            )
        self._collected.append(child)

    def add(self, child: Component) -> None:
        """Attach a pre-built ``Component`` as a child of this container.

        Composables called as functions inside a ``with`` block
        auto-attach via the ``@Composable`` decorator's collector
        wiring; this method handles the case where the caller built
        a component OUTSIDE the block (typically because they need
        to read the component's :attr:`metrics` to drive a layout
        decision like the parent's gap value) and now wants to
        attach it explicitly.
        """
        self._add(child)

    def __enter__(self) -> _ContainerBuilder:
        self._token = _push_collector(self)
        return self

    def __exit__(self, *exc) -> None:
        _pop_collector(self._token)
        if self._kind == "row":
            built = _build_row(self._collected, self._gap, self._align)
        else:
            built = _build_column(self._collected, self._gap, self._align)
        self._built = built
        self.size = built.size
        self.draw_fn = built.draw_fn
        # The completed container itself auto-attaches if we're nested
        # inside an outer ``with``.
        _maybe_register(built)

    def draw_at(self, d: Canvas, origin: Point) -> None:
        if self._built is None:
            raise RuntimeError(
                "Container builder hasn't been built yet — call ``draw_at`` "
                "after the ``with`` block exits."
            )
        self._built.draw_at(d, origin)


@overload
def Row(
    children: None = None,
    gap: float = 0.0,
    align: str = "center",
) -> _ContainerBuilder: ...


@overload
def Row(
    children: Iterable[Component],
    gap: float = 0.0,
    align: str = "center",
) -> BaseComponent: ...


def Row(
    children: Iterable[Component] | None = None,
    gap: float = 0.0,
    align: str = "center",
) -> BaseComponent | _ContainerBuilder:
    """Lay children out horizontally, left-to-right.

    Two call shapes:

    * ``Row([a, b, c], gap=...)`` — builds and returns the row component
      directly. Auto-registers with any active ``with``-block parent.
    * ``with Row(gap=...) as row:`` — opens a ``with`` block; composables
      called inside the block auto-attach as the row's children, and the
      row component is built on ``__exit__``. After exit ``row`` exposes
      ``size`` / ``draw_at`` / ``draw_fn`` and can be passed anywhere a
      :class:`Component` is expected.

    ``align`` controls the y-position of children that are shorter than
    the row: ``"top"``, ``"center"``, or ``"bottom"``.
    """
    if children is None:
        return _ContainerBuilder("row", gap, align)
    component = _build_row(list(children), gap, align)
    _maybe_register(component)
    return component


@overload
def Column(
    children: None = None,
    gap: float = 0.0,
    align: str = "start",
) -> _ContainerBuilder: ...


@overload
def Column(
    children: Iterable[Component],
    gap: float = 0.0,
    align: str = "start",
) -> BaseComponent: ...


def Column(
    children: Iterable[Component] | None = None,
    gap: float = 0.0,
    align: str = "start",
) -> BaseComponent | _ContainerBuilder:
    """Lay children out vertically, top-to-bottom.

    Two call shapes — see :func:`Row` for the full description.

    ``align`` controls the x-position of children that are narrower
    than the column: ``"start"``, ``"center"``, or ``"end"``.
    """
    if children is None:
        return _ContainerBuilder("column", gap, align)
    component = _build_column(list(children), gap, align)
    _maybe_register(component)
    return component


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

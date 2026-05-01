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
from typing import Any, Concatenate, Generic, Literal, ParamSpec, Protocol, TypeVar, overload

import drawsvg as draw

from .render_context import RenderContext, current_render_context

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


_M = TypeVar("_M")


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricsComponent(BaseComponent, Generic[_M]):
    """A :class:`BaseComponent` that exposes its component-specific metrics.

    Convention: every "real" composable (anything beyond a layout
    primitive) returns a :class:`MetricsComponent` parameterised by a
    frozen dataclass that captures everything its parent might want to
    read — resolved widths, dynamic truncation outcomes, per-row
    heights, anchor points, etc. Layout primitives (``Spacer``,
    ``Row``, ``Column``, ``BorderedFrame``) keep returning plain
    :class:`BaseComponent` since they have no component-specific
    metrics worth exposing.

    The two-tier surface keeps ``component.size`` and
    ``component.draw_at`` on the protocol contract while
    component-specific data lives behind a single, predictable
    namespace::

        @dataclass(frozen=True, slots=True, kw_only=True)
        class TapDanceTableMetrics:
            cell_width: float
            name_column_width: float
            ...


        @CtxComposable
        def TapDanceTable(ctx, *, tap_dances) -> MetricsComponent[TapDanceTableMetrics]:
            metrics = TapDanceTableMetrics.compute(ctx, tap_dances)
            ...
            return MetricsComponent(size=..., draw_fn=..., metrics=metrics)
    """

    metrics: _M


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


_P = ParamSpec("_P")
_C = TypeVar("_C", bound=BaseComponent)
_BuilderResult = tuple[Size, DrawFn]


# Inner-decorator Protocols used in the typing of ``Composable(...)`` when
# called WITH parens. They overload ``__call__`` so pyright picks the right
# return type based on whether the decorated function returns a typed
# component subclass or a ``(size, draw_fn)`` tuple.
class _NoCtxDecorator(Protocol):
    @overload
    def __call__(self, builder: Callable[_P, _C], /) -> Callable[_P, _C]: ...
    @overload
    def __call__(self, builder: Callable[_P, _BuilderResult], /) -> Callable[_P, BaseComponent]: ...


class _CtxDecorator(Protocol):
    @overload
    def __call__(
        self, builder: Callable[Concatenate[RenderContext, _P], _C], /
    ) -> Callable[_P, _C]: ...
    @overload
    def __call__(
        self, builder: Callable[Concatenate[RenderContext, _P], _BuilderResult], /
    ) -> Callable[_P, BaseComponent]: ...


@overload
def Composable(builder: Callable[_P, _C], /) -> Callable[_P, _C]: ...


@overload
def Composable(builder: Callable[_P, _BuilderResult], /) -> Callable[_P, BaseComponent]: ...


@overload
def Composable(*, use_context: Literal[False] = ...) -> _NoCtxDecorator: ...


@overload
def Composable(*, use_context: Literal[True]) -> _CtxDecorator: ...


def Composable(builder: Any = None, *, use_context: bool = False) -> Any:
    """Mark a function as a composable.

    Two call shapes:

    * ``@Composable`` (no parens) — the function takes its own props
      as kwargs and returns either a ``(size, draw_fn)`` tuple
      (auto-wrapped into :class:`BaseComponent`) or a
      :class:`BaseComponent` instance / subclass (passed through
      unchanged so typed subclasses keep their extra metadata).
    * ``@Composable(use_context=True)`` — the function declares
      ``ctx: RenderContext`` as its first positional parameter
      (equivalent of ``self`` on a method). Callers don't pass
      ``ctx`` — the decorator pulls the active
      :class:`RenderContext` from the :func:`using_render_context`
      block and prepends it to every call. The :class:`Concatenate`
      typing on the public-facing signature drops the first param so
      pyright sees the call shape as the function MINUS the context.

    Calling a context-aware composable outside of a
    :func:`using_render_context` block raises ``LookupError`` at the
    very first lookup — failure is loud and obvious rather than
    silently producing a degenerate render.

    Composition is just calling decorated functions and using the
    components they produce as children of other composables.
    """
    if builder is not None:
        # @Composable used without parens — delegate as if
        # ``use_context=False``.
        return _make_factory(builder, inject_ctx=False)

    def decorator(b):
        return _make_factory(b, inject_ctx=use_context)

    return decorator


def _make_factory(
    builder: Callable[..., BaseComponent | _BuilderResult],
    *,
    inject_ctx: bool,
) -> Callable[..., BaseComponent]:
    """Build the runtime factory shared by both decorator shapes."""

    @wraps(builder)
    def factory(*args, **kwargs) -> BaseComponent:
        if inject_ctx:
            ctx = current_render_context()
            result = builder(ctx, *args, **kwargs)
        else:
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


def align_within(
    outer: Size,
    inner: Size,
    *,
    horizontal: str = "start",
    vertical: str = "start",
) -> Point:
    """Return the offset placing ``inner`` inside ``outer`` per alignment.

    Pure helper used by composables that need to position one rect
    inside another — replaces the previous ``Align`` wrap composable.
    Alignment is the parent's concern (it owns the layout decision),
    so the helper hands back a :class:`Point` and the caller paints
    accordingly.

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

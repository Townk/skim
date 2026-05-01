# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""The ``@Composable`` decorator.

Built on top of :mod:`primitives` (which owns :class:`Component`,
:class:`BaseComponent`, :class:`MetricsComponent`, the layout
primitives and the value types). This module adds the workflow on
top:

* :func:`Composable` — decorator that wraps a function so its
  ``(size, draw_fn)`` tuple return is auto-converted into a
  :class:`BaseComponent`. With ``use_context=True`` it also injects
  the active :class:`RenderContext` as the first positional argument.

Why this exists
---------------

Image renderers used to compute their own sizes inline, position
children inline, and append shapes directly to the ``Drawing``.
Every new image variant duplicated that same scaffolding, so a fix
in one place often had to be re-applied in others. With composables,
every piece of the rendered output (a label, a row, a section, the
whole image) is a self-contained element that knows its own extent
and how to paint itself — a parent only ever queries ``size`` and
calls ``draw_at`` to lay it out.

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

When a composable needs to expose extra information beyond ``size``
/ ``draw_at`` (e.g. a thumb cluster surfacing per-indicator anchor
points to the connector router), define a typed subclass of
:class:`BaseComponent` (typically a :class:`MetricsComponent`) and
return an instance directly::

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

from collections.abc import Callable
from functools import wraps
from typing import Any, Concatenate, Literal, ParamSpec, Protocol, TypeVar, overload

from .primitives import BaseComponent, DrawFn, Size
from .render_context import RenderContext, current_render_context

# ---------------------------------------------------------------------------
# @Composable decorator
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


__all__ = ["Composable"]

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.composable."""

from dataclasses import dataclass

import drawsvg as draw
import pytest

from skim.application.render.composable import Composable
from skim.application.render.primitives import (
    BaseComponent,
    Column,
    Component,
    MetricsComponent,
    Padding,
    Point,
    Row,
    Size,
    Spacer,
)
from skim.application.render.render_context import (
    RenderContext,
    current_render_context,
    using_render_context,
)

# ---------------------------------------------------------------------------
# Helpers — minimal fake components for layout assertions
# ---------------------------------------------------------------------------


@Composable
def _Rect(width: float, height: float, color: str = "red"):
    """A solid-coloured rectangle component used as a stand-in for real content."""
    size = Size(width, height)

    def draw_at(d, origin):
        d.append(draw.Rectangle(x=origin.x, y=origin.y, width=width, height=height, fill=color))

    return size, draw_at


def _draw_to_drawing(component: Component, origin: Point = Point(0, 0)) -> draw.Drawing:
    d = draw.Drawing(max(component.size.width, 1), max(component.size.height, 1))
    component.draw_at(d, origin)
    return d


# ---------------------------------------------------------------------------
# Decorator behaviour
# ---------------------------------------------------------------------------


class TestComposableDecorator:
    def test_tuple_shortcut_wraps_to_base_component(self):
        """``(size, draw_fn)`` returns are auto-wrapped into ``BaseComponent``."""
        rect = _Rect(10.0, 20.0)
        assert isinstance(rect, BaseComponent)
        assert rect.size == Size(10.0, 20.0)

    def test_subclass_pass_through(self):
        """Composables can return typed ``BaseComponent`` subclasses directly."""

        @dataclass(frozen=True, slots=True, kw_only=True)
        class TaggedComponent(BaseComponent):
            tag: str

        @Composable
        def Tagged(width: float, height: float, tag: str) -> TaggedComponent:
            size = Size(width, height)

            def draw(d, origin):
                del d, origin

            return TaggedComponent(size=size, draw_fn=draw, tag=tag)

        result = Tagged(5.0, 6.0, tag="hello")
        assert isinstance(result, TaggedComponent)
        assert result.tag == "hello"
        assert result.size == Size(5.0, 6.0)

    def test_subclass_typed_metadata_survives_composition(self):
        """Typed metadata stays accessible after composing with primitives."""

        @dataclass(frozen=True, slots=True, kw_only=True)
        class AnchoredComponent(BaseComponent):
            anchor: Point

        @Composable
        def Anchored(width: float, height: float) -> AnchoredComponent:
            size = Size(width, height)
            anchor = Point(width / 2.0, 0.0)

            def draw(d, origin):
                del d, origin

            return AnchoredComponent(size=size, draw_fn=draw, anchor=anchor)

        # The metadata is read from the typed component directly.
        anchored = Anchored(40.0, 10.0)
        assert anchored.anchor == Point(20.0, 0.0)
        # And the typed component is still a Component, so it composes
        # with primitives like Row / Padding without extra ceremony.
        row = Row([anchored, _Rect(5.0, 5.0)])
        assert row.size.width == 45.0
        assert row.size.height == 10.0


# ---------------------------------------------------------------------------
# Layout primitives
# ---------------------------------------------------------------------------


class TestRow:
    def test_size_sums_widths_and_takes_max_height(self):
        row = Row([_Rect(10, 5), _Rect(20, 8), _Rect(15, 3)])
        assert row.size == Size(45.0, 8.0)

    def test_gap_adds_to_total_width(self):
        row = Row([_Rect(10, 5), _Rect(10, 5), _Rect(10, 5)], gap=4.0)
        assert row.size.width == 38.0  # 30 + 2 * 4

    def test_empty_row_is_zero_sized(self):
        row = Row([])
        assert row.size == Size(0.0, 0.0)

    def test_center_alignment_offsets_shorter_children(self):
        @Composable
        def _Probe():
            size = Size(0.0, 0.0)
            captured: list[Point] = []

            def draw(d, origin):
                del d
                captured.append(origin)

            return size, draw

        # Build a row with a tall child and a probe; tracks where the
        # probe was painted to verify centering.
        captured: list[Point] = []

        @Composable
        def _Capture(width: float, height: float):
            sz = Size(width, height)

            def draw(d, origin):
                del d
                captured.append(origin)

            return sz, draw

        row = Row([_Rect(5, 20), _Capture(5, 4)], gap=0, align="center")
        d = _draw_to_drawing(row)
        del d
        # First child was a Rect (paints itself but not into ``captured``);
        # the Capture probe sits at x=5 and should be vertically centred
        # within the 20-tall row -> y_off = (20 - 4) / 2 = 8.
        assert captured == [Point(5.0, 8.0)]


class TestColumn:
    def test_size_sums_heights_and_takes_max_width(self):
        col = Column([_Rect(10, 5), _Rect(20, 8), _Rect(15, 3)])
        assert col.size == Size(20.0, 16.0)

    def test_gap_adds_to_total_height(self):
        col = Column([_Rect(10, 5), _Rect(10, 5), _Rect(10, 5)], gap=4.0)
        assert col.size.height == 23.0  # 15 + 2 * 4


class TestPadding:
    def test_zero_default(self):
        p = Padding()
        assert (p.top, p.right, p.bottom, p.left) == (0.0, 0.0, 0.0, 0.0)
        assert p.horizontal == 0.0
        assert p.vertical == 0.0

    def test_one_positional_sets_all_sides(self):
        p = Padding(10)
        assert (p.top, p.right, p.bottom, p.left) == (10.0, 10.0, 10.0, 10.0)

    def test_two_positional_is_vertical_horizontal(self):
        p = Padding(10, 20)
        assert (p.top, p.right, p.bottom, p.left) == (10.0, 20.0, 10.0, 20.0)

    def test_four_positional_top_right_bottom_left(self):
        p = Padding(1, 2, 3, 4)
        assert (p.top, p.right, p.bottom, p.left) == (1.0, 2.0, 3.0, 4.0)

    def test_keyword_all(self):
        assert Padding(all=10) == Padding(10, 10, 10, 10)

    def test_keyword_symmetric(self):
        assert Padding(vertical=10, horizontal=20) == Padding(10, 20, 10, 20)

    def test_per_side_keyword_overrides(self):
        # Start from ``all=4`` then override individual sides.
        p = Padding(all=4, top=2, bottom=6)
        assert (p.top, p.right, p.bottom, p.left) == (2.0, 4.0, 6.0, 4.0)

    def test_horizontal_vertical_totals(self):
        p = Padding(top=1, right=2, bottom=3, left=4)
        assert p.horizontal == 6.0
        assert p.vertical == 4.0

    def test_too_many_positional_args_raises(self):
        import pytest

        with pytest.raises(TypeError):
            Padding(1, 2, 3)  # type: ignore[call-overload]


class TestSpacer:
    def test_takes_specified_size(self):
        s = Spacer(width=10, height=20)
        assert s.size == Size(10.0, 20.0)

    def test_paints_nothing(self):
        s = Spacer(width=10, height=20)
        d = draw.Drawing(50, 50)
        before = len(d.elements)
        s.draw_at(d, Point(0, 0))
        assert len(d.elements) == before


# ---------------------------------------------------------------------------
# MetricsComponent[M] — typed-subclass with a metrics namespace
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class _FakeMetrics:
    cell_width: float
    rows: int


class TestMetricsComponent:
    def test_exposes_metrics_field(self):
        m = MetricsComponent(
            size=Size(10, 20),
            draw_fn=lambda _d, _o: None,
            metrics=_FakeMetrics(cell_width=5.0, rows=3),
        )
        assert m.metrics.cell_width == 5.0
        assert m.metrics.rows == 3
        assert m.size == Size(10, 20)

    def test_satisfies_component_protocol(self):
        m: Component = MetricsComponent(
            size=Size(10, 20),
            draw_fn=lambda _d, _o: None,
            metrics=_FakeMetrics(cell_width=5.0, rows=3),
        )
        # `Component` Protocol only sees size + draw_at; the metrics
        # field is invisible through that view but accessible on the
        # concrete subclass.
        assert m.size == Size(10, 20)
        d = draw.Drawing(50, 50)
        m.draw_at(d, Point(0, 0))


# ---------------------------------------------------------------------------
# RenderContext + ContextVar plumbing
# ---------------------------------------------------------------------------


def _build_ctx() -> RenderContext:
    """Construct a RenderContext for tests without going through a real config."""
    from skim.application.render.render_context import (
        DocumentMetrics,
        TextStyle,
        Theme,
        Typography,
    )
    from skim.application.render.text import Font
    from skim.data import SkimConfig, SvalboardKeymap

    config = SkimConfig()
    keymap = SvalboardKeymap(layers={})
    palette = config.output.style.palette
    return RenderContext(
        config=config,
        keymap=keymap,
        theme=Theme(
            palette=palette,
            typography=Typography(
                title=TextStyle(font=Font.TITLE, size=24.0, color=palette.text_color),
                copyright=TextStyle(font=Font.FINGER_KEY, size=12.0, color=palette.text_color),
            ),
        ),
        document_metrics=DocumentMetrics(
            doc_width=1600.0,
            margin=10.0,
            border_width=2.0,
            inset=20.0,
            border_radius=8.0,
            column_gap=24.0,
        ),
    )


class TestRenderContext:
    def test_using_render_context_sets_active_ctx(self):
        ctx = _build_ctx()
        with using_render_context(ctx) as scoped:
            assert scoped is ctx
            assert current_render_context() is ctx

    def test_outside_context_raises(self):
        with pytest.raises(LookupError):
            current_render_context()

    def test_context_restored_after_block(self):
        outer = _build_ctx()
        inner = _build_ctx()
        with using_render_context(outer):
            assert current_render_context() is outer
            with using_render_context(inner):
                assert current_render_context() is inner
            assert current_render_context() is outer

    def test_context_cleared_after_block(self):
        ctx = _build_ctx()
        with using_render_context(ctx):
            pass
        with pytest.raises(LookupError):
            current_render_context()


# ---------------------------------------------------------------------------
# @Composable(use_context=True) — context auto-injected as first positional argument
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def _CtxRect(ctx, *, width: float, height: float, color: str = "blue"):
    """A composable that reads doc_width from ctx.document_metrics."""
    # Touch ctx so the test can verify it was passed in.
    assert ctx.document_metrics.doc_width > 0
    size = Size(width, height)

    def draw_at(d, origin):
        d.append(draw.Rectangle(x=origin.x, y=origin.y, width=width, height=height, fill=color))

    return size, draw_at


class TestComposableWithContext:
    def test_injects_ctx_from_active_context(self):
        ctx = _build_ctx()
        with using_render_context(ctx):
            rect = _CtxRect(width=10, height=20)
        assert rect.size == Size(10.0, 20.0)

    def test_raises_outside_context(self):
        with pytest.raises(LookupError):
            _CtxRect(width=10, height=20)

    def test_caller_does_not_pass_ctx_explicitly(self):
        """Public signature drops the ctx parameter via Concatenate typing."""
        ctx = _build_ctx()
        with using_render_context(ctx):
            # Calling with positional `ctx` would be wrong; the public
            # API only accepts the keyword args after ``ctx``.
            rect = _CtxRect(width=5, height=5)
        assert rect.size == Size(5.0, 5.0)

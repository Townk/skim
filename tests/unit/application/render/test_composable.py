# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.composable."""

from dataclasses import dataclass

import drawsvg as draw

from skim.application.render.composable import (
    BaseComponent,
    BorderedFrame,
    Column,
    Component,
    Composable,
    Padding,
    Point,
    Row,
    Size,
    Spacer,
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
    def test_pads_all_sides(self):
        padded = Padding(_Rect(10, 20), all=4)
        assert padded.size == Size(18.0, 28.0)

    def test_per_side_overrides(self):
        padded = Padding(_Rect(10, 20), all=4, top=2, bottom=6)
        # 4 (left) + 10 (child) + 4 (right) = 18; 2 (top) + 20 (child) + 6 (bottom) = 28
        assert padded.size == Size(18.0, 28.0)


class TestBorderedFrame:
    def test_size_matches_child(self):
        frame = BorderedFrame(_Rect(10, 20), border_radius=4, background="white")
        assert frame.size == Size(10.0, 20.0)


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

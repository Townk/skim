# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.adjustable_text."""

from contextlib import contextmanager

from skim.application.render.adjustable_text import AdjustableText, measure_text_width
from skim.application.render.render_context import (
    RenderContext,
    TextStyle,
    using_render_context,
)
from skim.application.render.text import Font
from skim.data import SkimConfig, SvalboardKeymap

_ELLIPSIS = "…"


@contextmanager
def _ctx():
    """Push a default :class:`RenderContext` for tests that build
    :func:`AdjustableText` directly.
    """
    config = SkimConfig()
    keymap = SvalboardKeymap(layers={})
    with using_render_context(RenderContext.build(config, keymap)) as render_ctx:
        yield render_ctx


def _style(size: float = 12.0, color: str = "#000") -> TextStyle:
    return TextStyle(font=Font.FINGER_KEY, size=size, color=color)


def _measure(text: str, font_size: float) -> float:
    """PIL-accurate rendered width — the same path AdjustableText uses
    internally for its truncation / shrink loop.
    """
    return measure_text_width(text, Font.FINGER_KEY, font_size)


# ---------------------------------------------------------------------------
# Truncation behaviour
# ---------------------------------------------------------------------------


class TestTruncation:
    """Triggered when ``max_width`` is set and ``min_font_size`` either
    isn't supplied or doesn't open enough headroom for the shrink pass
    to fit the text.
    """

    def test_returns_full_text_when_already_fits(self):
        with _ctx():
            el = AdjustableText(text="short", style=_style(), max_width=10_000)
        assert el.metrics.rendered_text == "short"
        assert el.metrics.truncated is False

    def test_empty_text_yields_zero_size_noop(self):
        with _ctx():
            el = AdjustableText(text="", style=_style(), max_width=100)
        assert el.metrics.rendered_text == ""
        assert el.metrics.truncated is False
        assert el.size.width == 0
        assert el.size.height == 0

    def test_zero_max_width_truncates_to_empty(self):
        with _ctx():
            el = AdjustableText(text="anything", style=_style(), max_width=0)
        # Zero budget: nothing fits, not even the ellipsis.
        assert el.metrics.rendered_text == ""

    def test_appends_ellipsis_when_overflow(self):
        text = "the quick brown fox jumps over the lazy dog"
        natural = _measure(text, 12.0)
        # Cap at half the natural width to force truncation.
        with _ctx():
            el = AdjustableText(text=text, style=_style(12.0), max_width=natural / 2)
        assert el.metrics.truncated is True
        assert el.metrics.rendered_text.endswith(_ELLIPSIS)
        assert len(el.metrics.rendered_text) < len(text) + len(_ELLIPSIS)

    def test_truncated_output_fits_within_max_width(self):
        text = "the quick brown fox jumps over the lazy dog"
        natural = _measure(text, 12.0)
        cap = natural / 2
        with _ctx():
            el = AdjustableText(text=text, style=_style(12.0), max_width=cap)
        assert _measure(el.metrics.rendered_text, 12.0) <= cap

    def test_returns_just_ellipsis_when_only_room_for_it(self):
        # Pick a max_width that's larger than the ellipsis itself but
        # smaller than ellipsis + any real glyph.
        ellipsis_w = _measure(_ELLIPSIS, 12.0)
        with _ctx():
            el = AdjustableText(text="anything", style=_style(12.0), max_width=ellipsis_w + 0.1)
        assert el.metrics.rendered_text == _ELLIPSIS


# ---------------------------------------------------------------------------
# Shrink behaviour
# ---------------------------------------------------------------------------


class TestShrink:
    """When ``min_font_size`` is below ``style.size``, the resolution
    looks for the largest font in that interval that fits both
    constraints before falling back to truncation.
    """

    def test_no_shrink_when_text_fits(self):
        with _ctx():
            el = AdjustableText(
                text="short",
                style=_style(20.0),
                max_width=10_000,
                max_height=10_000,
                min_font_size=6.0,
            )
        assert el.metrics.font_size == 20.0
        assert el.metrics.truncated is False

    def test_shrinks_font_to_fit_height(self):
        with _ctx():
            el = AdjustableText(
                text="some text",
                style=_style(40.0),
                max_height=10.0,
                min_font_size=6.0,
            )
        # Resolved font must be smaller than the style ceiling and
        # bounded below by the floor.
        assert 6.0 <= el.metrics.font_size < 40.0
        assert el.metrics.truncated is False

    def test_clamps_min_font_size_to_style_size(self):
        # Passing ``min_font_size`` larger than ``style.size`` must
        # not enlarge the text past the requested style.
        with _ctx():
            el = AdjustableText(text="x", style=_style(12.0), min_font_size=24.0)
        assert el.metrics.font_size == 12.0


# ---------------------------------------------------------------------------
# Reference-line metrics
# ---------------------------------------------------------------------------


class TestReferenceLines:
    """``baseline``, ``meanline`` and ``ascender_line`` are y-offsets
    (in SVG units at the resolved font size) within the rendered
    text's bbox.
    """

    def test_lines_stack_correctly_for_caps_and_lowercase_text(self):
        with _ctx():
            el = AdjustableText(text="Copyright", style=_style(40.0))
        # ascender_line < meanline < baseline for any text containing
        # both ascenders and lowercase glyphs.
        assert el.metrics.ascender_line <= el.metrics.meanline
        assert el.metrics.meanline <= el.metrics.baseline

    def test_lowercase_only_text_pushes_ascender_above_bbox(self):
        # ``"xyz"`` has no ascenders — the bbox starts at the
        # meanline so the ascender line sits above ``y=0``.
        with _ctx():
            el = AdjustableText(text="xyz", style=_style(40.0))
        assert el.metrics.ascender_line < 0
        assert el.metrics.meanline == 0.0

    def test_zero_lines_for_empty_text(self):
        with _ctx():
            el = AdjustableText(text="", style=_style())
        assert el.metrics.baseline == 0.0
        assert el.metrics.meanline == 0.0
        assert el.metrics.ascender_line == 0.0


# ---------------------------------------------------------------------------
# Reported size — slot fill
# ---------------------------------------------------------------------------


class TestReportedSize:
    """``max_width`` does double duty: when set, the reported
    ``size.width`` equals it (slot fill), with ``text_anchor``
    controlling the horizontal alignment of the painted text inside
    the bbox.
    """

    def test_size_matches_max_width_when_set(self):
        with _ctx():
            el = AdjustableText(text="short", style=_style(), max_width=300.0)
        assert el.size.width == 300.0

    def test_size_matches_natural_width_when_max_width_omitted(self):
        with _ctx():
            el = AdjustableText(text="short", style=_style(12.0))
        assert abs(el.size.width - _measure("short", 12.0)) < 0.01

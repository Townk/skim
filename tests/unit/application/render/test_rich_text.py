# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.rich_text."""

from contextlib import contextmanager

from skim.application.render.adjustable_text import measure_text_width
from skim.application.render.render_context import (
    RenderContext,
    TextStyle,
    using_render_context,
)
from skim.application.render.rich_text import (
    RichText,
    TextSpan,
    resolve_nerd_font_glyphs,
)
from skim.application.render.text import Font
from skim.data import SkimConfig, SvalboardKeymap


@contextmanager
def _ctx():
    config = SkimConfig()
    keymap = SvalboardKeymap(layers={})
    with using_render_context(RenderContext.build(config, keymap)) as render_ctx:
        yield render_ctx


def _style(size: float = 12.0, color: str = "#000") -> TextStyle:
    return TextStyle(font=Font.FINGER_KEY, size=size, color=color)


# ---------------------------------------------------------------------------
# Glyph resolver
# ---------------------------------------------------------------------------


class TestResolveNerdFontGlyphs:
    def test_passes_plain_text_through(self):
        assert resolve_nerd_font_glyphs("hello world") == "hello world"

    def test_replaces_known_token_with_glyph(self):
        # ``%%md-keyboard;`` is a real Material Design token in the
        # Nerd Font glyph dictionary; the resolver should swap it for
        # the corresponding single Unicode character.
        out = resolve_nerd_font_glyphs("X %%md-keyboard; Y")
        assert "%%" not in out
        # Glyph chars sit in the Private Use Area — high codepoints.
        glyph_present = any(ord(ch) >= 0xE000 for ch in out)
        assert glyph_present

    def test_nf_prefix_is_optional(self):
        # ``%%md-keyboard;`` and ``%%nf-md-keyboard;`` resolve to the
        # same glyph.
        with_prefix = resolve_nerd_font_glyphs("%%nf-md-keyboard;")
        without_prefix = resolve_nerd_font_glyphs("%%md-keyboard;")
        assert with_prefix == without_prefix

    def test_unknown_token_passes_through_unchanged(self):
        # No glyph for ``%%totally-not-a-token;`` — kept literal.
        out = resolve_nerd_font_glyphs("%%totally-not-a-token;")
        assert out == "%%totally-not-a-token;"

    def test_handles_unterminated_token(self):
        # Missing terminating ``;`` — the parser should not consume
        # arbitrary text; just emit the leading ``%%`` and continue.
        out = resolve_nerd_font_glyphs("%%md-keyboard rest")
        assert "rest" in out


# ---------------------------------------------------------------------------
# RichText core behaviour
# ---------------------------------------------------------------------------


class TestRichTextEmpty:
    def test_no_spans_yields_zero_size(self):
        with _ctx():
            el = RichText(spans=[])
        assert el.size.width == 0
        assert el.size.height == 0
        assert el.metrics.span_font_sizes == ()
        assert el.metrics.rendered_spans == ()


class TestRichTextLayout:
    def test_total_width_sums_per_span_widths_with_separator(self):
        # Each span (except the last) carries a trailing space, so
        # the row's natural width = ``measure(s1+" ") + measure(s2)``.
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(style=_style(12.0), text="alpha"),
                    TextSpan(style=_style(12.0), text="beta"),
                ]
            )
        expected = measure_text_width("alpha ", Font.FINGER_KEY, 12.0) + measure_text_width(
            "beta", Font.FINGER_KEY, 12.0
        )
        assert abs(el.size.width - expected) < 0.5

    def test_no_shrink_when_natural_fits(self):
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(style=_style(12.0), text="alpha"),
                    TextSpan(style=_style(16.0), text="beta"),
                ],
                max_width=10_000,
            )
        assert el.metrics.font_scale == 1.0
        assert el.metrics.span_font_sizes == (12.0, 16.0)

    def test_uniform_shrink_when_overflow(self):
        # Build a wide pair, cap at half their natural width, expect a
        # ~0.5 scale and proportionally smaller per-span sizes.
        with _ctx():
            natural = RichText(
                spans=[
                    TextSpan(style=_style(20.0), text="quick brown"),
                    TextSpan(style=_style(20.0), text="fox jumps"),
                ]
            )
            cap = natural.size.width / 2
            shrunk = RichText(
                spans=[
                    TextSpan(style=_style(20.0), text="quick brown"),
                    TextSpan(style=_style(20.0), text="fox jumps"),
                ],
                max_width=cap,
            )
        assert shrunk.metrics.font_scale < 1.0
        # Both spans scale by the same factor → equal resolved sizes.
        a, b = shrunk.metrics.span_font_sizes
        assert abs(a - b) < 0.001
        # Total rendered width should fit (modulo PIL rounding).
        assert shrunk.size.width <= cap + 1.0

    def test_relative_proportions_preserved_after_shrink(self):
        # Two spans of different style sizes shrink in lockstep, so
        # their RATIO is preserved.
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(style=_style(12.0), text="alpha"),
                    TextSpan(style=_style(24.0), text="beta"),
                ],
                max_width=20.0,  # very tight, forces shrink
            )
        a, b = el.metrics.span_font_sizes
        # Original ratio 12:24 = 0.5; resolved ratio should match.
        assert abs((a / b) - 0.5) < 0.01

    def test_min_font_size_pins_floor(self):
        # Tight budget that would force scale below the floor: the
        # resolved sizes pin at ``min_font_size`` even though that
        # breaks the uniform-scale invariant.
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(style=_style(20.0), text="long text here"),
                    TextSpan(style=_style(20.0), text="more long text"),
                ],
                max_width=10.0,  # so tight even the floor overflows
                min_font_size=8.0,
            )
        assert all(size >= 8.0 for size in el.metrics.span_font_sizes)


class TestRichTextSlotFill:
    def test_size_matches_max_width_when_set(self):
        with _ctx():
            el = RichText(
                spans=[TextSpan(style=_style(12.0), text="alpha")],
                max_width=300.0,
            )
        assert el.size.width == 300.0

    def test_size_matches_natural_when_max_width_omitted(self):
        with _ctx():
            el = RichText(spans=[TextSpan(style=_style(12.0), text="alpha")])
        # ``"alpha"`` is the only span and it's the last — no trailing
        # separator. The width should match the natural rendered width.
        natural = measure_text_width("alpha", Font.FINGER_KEY, 12.0)
        assert abs(el.size.width - natural) < 0.5


class TestRichTextBaselineAlignment:
    def test_height_accommodates_taller_span(self):
        # Mixed-size spans baseline-align — the row's height is
        # determined by the tallest span (plus any descender/ascender
        # offsets from baseline alignment).
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(style=_style(12.0), text="alpha"),
                    TextSpan(style=_style(40.0), text="BETA"),
                ]
            )
        # The taller span dominates the row height.
        assert el.size.height >= 30.0  # ~bbox of "BETA" at 40pt

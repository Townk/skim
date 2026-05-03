# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.rich_text."""

from contextlib import contextmanager

from skim.application.render.adjustable_text import measure_text_width
from skim.application.render.font import Font
from skim.application.render.primitives import Point
from skim.application.render.render_context import (
    RenderContext,
    TextStyle,
    using_render_context,
)
from skim.application.render.rich_text import (
    RichText,
    _parse_into_spans,
    _relax_sizes,
    _truncate_with_ellipses,
    resolve_nerd_font_glyphs,
)
from skim.data import SkimConfig, SvalboardKeymap

_ELLIPSIS = "…"


@contextmanager
def _ctx():
    config = SkimConfig()
    keymap = SvalboardKeymap(layers={})
    with using_render_context(RenderContext.build(config, keymap)) as render_ctx:
        yield render_ctx


def _style(size: float = 12.0, color: str = "#000", font: Font = Font.FINGER_KEY) -> TextStyle:
    return TextStyle(font=font, size=size, color=color)


# ---------------------------------------------------------------------------
# Glyph resolver
# ---------------------------------------------------------------------------


class TestResolveNerdFontGlyphs:
    def test_passes_plain_text_through(self):
        assert resolve_nerd_font_glyphs("hello world") == "hello world"

    def test_replaces_known_token_with_glyph(self):
        out = resolve_nerd_font_glyphs("X %%md-keyboard; Y")
        assert "%%" not in out
        # Glyph chars sit in the Private Use Area — high codepoints.
        glyph_present = any(ord(ch) >= 0xE000 for ch in out)
        assert glyph_present

    def test_nf_prefix_is_optional(self):
        with_prefix = resolve_nerd_font_glyphs("%%nf-md-keyboard;")
        without_prefix = resolve_nerd_font_glyphs("%%md-keyboard;")
        assert with_prefix == without_prefix

    def test_unknown_token_passes_through_unchanged(self):
        out = resolve_nerd_font_glyphs("%%totally-not-a-token;")
        assert out == "%%totally-not-a-token;"

    def test_handles_unterminated_token(self):
        out = resolve_nerd_font_glyphs("%%md-keyboard rest")
        assert "rest" in out


# ---------------------------------------------------------------------------
# Parser — _parse_into_spans splits a string into per-font _TextSpans
# ---------------------------------------------------------------------------


class TestParseIntoSpans:
    def test_plain_text_yields_single_span_with_default_style(self):
        default = _style(12.0)
        spans = _parse_into_spans("hello world", default)
        assert len(spans) == 1
        assert spans[0].text == "hello world"
        assert spans[0].style == default

    def test_token_yields_symbols_span_with_default_size_and_color(self):
        default = _style(20.0, color="#FF0000")
        spans = _parse_into_spans("%%md-keyboard;", default)
        assert len(spans) == 1
        # Symbols span keeps the default size + colour but switches font.
        assert spans[0].style is not None
        assert spans[0].style.font == Font.SYMBOLS
        assert spans[0].style.size == 20.0
        assert spans[0].style.color == "#FF0000"
        # Text is the resolved single-character glyph.
        assert len(spans[0].text) == 1

    def test_mixed_input_splits_into_separate_spans(self):
        default = _style(12.0)
        spans = _parse_into_spans("Foo %%md-keyboard; bar", default)
        # ``Foo `` and `` bar`` get their leading/trailing whitespace
        # stripped at flush time — RichText's default separator puts
        # the visual gap between adjacent spans, so any whitespace the
        # input encoded between tokens would double up otherwise.
        assert len(spans) == 3
        assert spans[0].text == "Foo"
        assert spans[0].style == default
        assert spans[1].style is not None
        assert spans[1].style.font == Font.SYMBOLS
        assert spans[2].text == "bar"
        assert spans[2].style == default

    def test_unknown_token_kept_literal_in_text_span(self):
        default = _style(12.0)
        spans = _parse_into_spans("foo %%not-a-token; bar", default)
        # No split because the token doesn't resolve — single text span.
        assert len(spans) == 1
        assert spans[0].text == "foo %%not-a-token; bar"
        assert spans[0].style == default

    def test_separator_char_yields_dedicated_span_when_background_passed(self):
        """The separator character ``│`` splits into its own span when
        ``separator_background`` is supplied. The span paints in
        :attr:`Font.UNICODE_SYMBOLS` (DejaVu Sans Mono — has the
        box-drawing block) with a ghost-style colour derived from
        the background (darkened via ``adjust_luminance(bg, 0.7)``).
        Because the render font matches the measurement font no
        paint-time offset is needed — the bar lands exactly where
        PIL placed it. Weight stays inherited so a Black-face
        thumb label doesn't trigger synthetic-bold smearing on top
        of the separator face.
        """
        default = _style(12.0, color="#FFFFFF")
        spans = _parse_into_spans("ab│cd", default, separator_background="#888888")
        # 3 spans: "ab", "│", "cd".
        assert len(spans) == 3
        assert spans[0].text == "ab"
        assert spans[0].style == default
        assert spans[1].text == "│"
        assert spans[1].style is not None
        assert spans[1].style.font == Font.UNICODE_SYMBOLS
        assert spans[1].style.weight == default.weight
        assert spans[1].style.color != "#888888"
        # No paint-time offset — DejaVu's ``│`` advance matches the
        # rendered glyph so the cursor lands the bar correctly.
        assert spans[1].offset.x == 0.0
        assert spans[2].text == "cd"
        assert spans[2].style == default

    def test_separator_char_routed_via_unicode_symbols_when_no_background(self):
        """Without ``separator_background`` the separator still gets
        its own span — the parser routes characters missing from the
        default font through :attr:`Font.UNICODE_SYMBOLS`, which has
        the box-drawing block, so the rendered bar lands at its
        measured cursor position. The span carries the default
        style's colour (no ghost fill) since no background was
        supplied."""
        default = _style(12.0)
        spans = _parse_into_spans("ab│cd", default)
        assert len(spans) == 3
        assert spans[0].text == "ab"
        assert spans[1].text == "│"
        assert spans[1].style is not None
        assert spans[1].style.font == Font.UNICODE_SYMBOLS
        assert spans[1].style.color == default.color
        assert spans[1].offset.x == 0.0
        assert spans[2].text == "cd"

    def test_separator_with_surrounding_nerd_font_tokens(self):
        """Separator splitting interleaves correctly with Nerd Font
        token splitting: ``%%kb;│%%kb;`` produces three spans (glyph,
        separator, glyph) — the typical layer-tap label shape."""
        default = _style(12.0)
        spans = _parse_into_spans(
            "%%md-keyboard;│%%md-keyboard;", default, separator_background="#888"
        )
        assert len(spans) == 3
        assert spans[0].style is not None and spans[0].style.font == Font.SYMBOLS
        assert spans[1].text == "│"
        assert spans[1].style is not None
        assert spans[2].style is not None and spans[2].style.font == Font.SYMBOLS

    def test_plain_text_segments_strip_whitespace(self):
        """Plain-text fragments are stripped of leading/trailing
        whitespace at flush time — :func:`RichText` uses its default
        ``separator=" "`` to put the gap between adjacent spans, so
        any whitespace the input string encoded between tokens would
        double up if we kept it. Stripping at the parser keeps the
        span list clean and the inter-span gap uniformly one space."""
        default = _style(12.0)
        # Input has explicit whitespace around the token; the parser
        # drops the spaces from the text fragments so the rendered
        # output relies solely on RichText's separator.
        spans = _parse_into_spans("Foo %%md-keyboard; bar", default)
        assert len(spans) == 3
        assert spans[0].text == "Foo"  # was "Foo " before stripping
        assert spans[1].style is not None and spans[1].style.font == Font.SYMBOLS
        assert spans[2].text == "bar"  # was " bar"

    def test_pure_whitespace_segment_is_dropped_entirely(self):
        """A text fragment that is ONLY whitespace (e.g. between two
        adjacent Nerd Font tokens) gets dropped — the spans on either
        side are adjacent and :func:`RichText`'s default separator
        provides the visual gap."""
        default = _style(12.0)
        spans = _parse_into_spans("%%md-keyboard; %%md-keyboard;", default)
        # Only the two glyph spans — the lone " " between them is dropped.
        assert len(spans) == 2
        assert all(s.style is not None and s.style.font == Font.SYMBOLS for s in spans)


# ---------------------------------------------------------------------------
# Separator parameter — passing ``""`` disables the auto-inserted gap.
#
# To exercise multi-span behaviour through the public ``text=`` API we
# use a Nerd Font token: the parser produces a glyph span (Font.SYMBOLS)
# followed by a plain-text span, so the separator's effect is observable
# in the rendered width.
# ---------------------------------------------------------------------------


class TestSeparator:
    def test_default_separator_inserts_space_between_spans(self):
        with _ctx():
            el = RichText(text="%%md-keyboard;X", style=_style(12.0))
        # Default separator " " — the glyph span gets a trailing
        # " " in its render text. Width = measure(glyph + " ") at
        # SYMBOLS + measure("X") at FINGER_KEY.
        glyphs = resolve_nerd_font_glyphs("%%md-keyboard;")
        expected = measure_text_width(glyphs + " ", Font.SYMBOLS, 12.0) + measure_text_width(
            "X", Font.FINGER_KEY, 12.0
        )
        assert abs(el.size.width - expected) < 0.5

    def test_empty_separator_omits_the_gap(self):
        with _ctx():
            el = RichText(text="%%md-keyboard;X", style=_style(12.0), separator="")
        # No separator appended — width is the sum of the per-span
        # natural widths.
        glyphs = resolve_nerd_font_glyphs("%%md-keyboard;")
        expected = measure_text_width(glyphs, Font.SYMBOLS, 12.0) + measure_text_width(
            "X", Font.FINGER_KEY, 12.0
        )
        assert abs(el.size.width - expected) < 0.5


# ---------------------------------------------------------------------------
# Empty-input behaviour
# ---------------------------------------------------------------------------


class TestRichTextEmpty:
    def test_empty_text_yields_zero_size(self):
        with _ctx():
            el = RichText(text="", style=_style())
        assert el.size.width == 0
        assert el.size.height == 0
        assert el.metrics.span_font_sizes == ()
        assert el.metrics.rendered_spans == ()
        assert el.metrics.truncated is False


# ---------------------------------------------------------------------------
# Layout & sizing — single-span cases via the public API
# ---------------------------------------------------------------------------


class TestSlotFill:
    def test_size_matches_max_width_when_set(self):
        with _ctx():
            el = RichText(text="alpha", style=_style(12.0), max_width=300.0)
        assert el.size.width == 300.0

    def test_size_matches_natural_when_max_width_omitted(self):
        with _ctx():
            el = RichText(text="alpha", style=_style(12.0))
        natural = measure_text_width("alpha", Font.FINGER_KEY, 12.0)
        assert abs(el.size.width - natural) < 0.5


# ---------------------------------------------------------------------------
# Multi-span behaviour exercised through the public API. Nerd Font
# tokens are the natural way to produce multi-span output via ``text=``.
# ---------------------------------------------------------------------------


class TestMultiSpanRendering:
    def test_token_plus_text_resolves_two_spans_at_parent_size(self):
        """Plain-text fragments inherit the parent style; token spans
        switch font but inherit size + colour. Both spans should
        render at the parent's font size."""
        with _ctx():
            el = RichText(text="X %%md-keyboard;", style=_style(20.0))
        assert el.metrics.span_font_sizes == (20.0, 20.0)

    def test_height_scales_with_parent_size(self):
        """Bigger parent size → bigger rendered row height. Rough
        sanity check that the bbox tracks the painted text."""
        with _ctx():
            small = RichText(text="X %%md-keyboard;", style=_style(12.0))
            big = RichText(text="X %%md-keyboard;", style=_style(40.0))
        assert big.size.height > small.size.height


# ---------------------------------------------------------------------------
# Relaxation algorithm — synchronised shrink with proportional floors.
# Tested against the internal ``_relax_sizes`` function so we can
# inject mixed per-span styles (the parser doesn't have syntax for
# arbitrary per-span size overrides).
# ---------------------------------------------------------------------------


class TestRelaxSizes:
    def test_no_shrink_when_natural_fits(self):
        sizes = _relax_sizes(
            styles=[_style(12.0), _style(16.0)],
            mins=[12.0, 16.0],
            rendered=["alpha", "beta"],
            max_width=10_000.0,
            max_height=None,
            separator=" ",
        )
        assert sizes == [12.0, 16.0]

    def test_uniform_shrink_preserves_proportions(self):
        # Two spans at 12 and 24 — under tight budget the relaxation
        # scales both by the same factor so their RATIO holds.
        sizes = _relax_sizes(
            styles=[_style(12.0), _style(24.0)],
            mins=[2.0, 4.0],  # proportional from parent ratio 2/12
            rendered=["alpha", "beta"],
            max_width=20.0,
            max_height=None,
            separator=" ",
        )
        a, b = sizes
        # Relative ratio 12:24 = 0.5 is preserved post-shrink.
        assert abs((a / b) - 0.5) < 0.01

    def test_proportional_floors_preserve_ratio_under_pressure(self):
        # Parent (size=12, min=6) → ratio 0.5. Spans declared at
        # 12 and 24 inherit floors 6 and 12 respectively. With
        # proportional floors both spans share the same shrink
        # factor (the floor is reached at the same factor for
        # every span), so the resolved 12:24 ratio is preserved
        # whether the relaxation converges naturally or pins
        # everyone at their respective floors.
        sizes = _relax_sizes(
            styles=[_style(12.0), _style(24.0)],
            mins=[6.0, 12.0],
            rendered=["alpha", "beta"],
            max_width=50.0,
            max_height=None,
            separator=" ",
        )
        a, b = sizes
        # Both shrink by the same factor — original 12:24 = 0.5 holds.
        assert abs((a / b) - 0.5) < 0.05

    def test_floor_equal_to_size_means_no_shrink(self):
        # When the floor coincides with the natural size, no shrinking
        # is allowed — sizes equal the input styles' sizes regardless
        # of the budget.
        sizes = _relax_sizes(
            styles=[_style(20.0), _style(20.0)],
            mins=[20.0, 20.0],
            rendered=["alpha", "beta"],
            max_width=None,
            max_height=None,
            separator=" ",
        )
        assert sizes == [20.0, 20.0]


# ---------------------------------------------------------------------------
# Truncation — synthetic ``…`` spans inserted automatically when the
# relaxed set still doesn't fit. Tested against ``_truncate_with_ellipses``
# directly so we can construct a multi-span trial set without going
# through markup.
# ---------------------------------------------------------------------------


def _five_span_setup(*, text_anchor: str, max_width: float):
    """Build the inputs for a 5-span truncation test at parent style 20."""
    rendered = ["alpha", "beta", "gamma", "delta", "epsilon"]
    styles = [_style(20.0)] * 5
    mins = [12.0] * 5
    offsets = [Point(0.0, 0.0)] * 5
    return _truncate_with_ellipses(
        styles=styles,
        mins=mins,
        rendered=rendered,
        offsets=offsets,
        max_width=max_width,
        max_height=None,
        text_anchor=text_anchor,
        ellipsis_style=_style(20.0),
        ellipsis_min=12.0,
        separator=" ",
    )


class TestTruncationStartAnchor:
    def test_appends_ellipsis_at_end(self):
        # Default ``text_anchor="start"``. Truncation drops from the
        # end and appends ``…`` once.
        _styles, _mins, rendered, _sizes, _offsets = _five_span_setup(
            text_anchor="start", max_width=40.0
        )
        assert _ELLIPSIS in rendered
        assert rendered[-1] == _ELLIPSIS

    def test_no_truncation_when_relaxation_fits(self):
        # Roomy budget, headroom in the floor — relaxation alone gets
        # the rendered text in. Tested through the public API since
        # the integration with the relaxation phase matters.
        with _ctx():
            el = RichText(
                text="alpha beta",
                style=_style(20.0),
                min_font_size=6.0,
                max_width=10_000.0,
            )
        assert el.metrics.truncated is False
        assert _ELLIPSIS not in el.metrics.rendered_spans


class TestTruncationEndAnchor:
    def test_prepends_ellipsis_at_start(self):
        _styles, _mins, rendered, _sizes, _offsets = _five_span_setup(
            text_anchor="end", max_width=40.0
        )
        assert rendered[0] == _ELLIPSIS


class TestTruncationMiddleAnchor:
    def test_inserts_ellipsis_on_both_sides(self):
        _styles, _mins, rendered, _sizes, _offsets = _five_span_setup(
            text_anchor="middle", max_width=80.0
        )
        assert rendered[0] == _ELLIPSIS
        assert rendered[-1] == _ELLIPSIS


# ---------------------------------------------------------------------------
# Letter spacing — paint-time attribute forwarded to per-span SVG text.
# ---------------------------------------------------------------------------


class TestLetterSpacing:
    def test_letter_spacing_does_not_change_measured_width(self):
        # ``letter_spacing`` is paint-time only — measurement uses raw
        # PIL widths. The bbox should match the natural width whether
        # or not letter_spacing is set.
        with _ctx():
            without = RichText(text="alpha", style=_style(12.0))
            with_spacing = RichText(text="alpha", style=_style(12.0), letter_spacing=2.0)
        assert abs(without.size.width - with_spacing.size.width) < 0.5

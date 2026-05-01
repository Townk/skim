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
# RichText core behaviour
# ---------------------------------------------------------------------------


class TestRichTextEmpty:
    def test_no_spans_yields_zero_size(self):
        with _ctx():
            el = RichText(spans=[], style=_style())
        assert el.size.width == 0
        assert el.size.height == 0
        assert el.metrics.span_font_sizes == ()
        assert el.metrics.rendered_spans == ()
        assert el.metrics.truncated is False


# ---------------------------------------------------------------------------
# Style inheritance — TextSpan.style is optional and falls back to
# the parent RichText's ``style``
# ---------------------------------------------------------------------------


class TestStyleInheritance:
    def test_span_without_style_inherits_parent(self):
        # Two spans, neither with a style — both render at the
        # parent's style.size.
        with _ctx():
            el = RichText(
                spans=[TextSpan(text="alpha"), TextSpan(text="beta")],
                style=_style(20.0),
            )
        assert el.metrics.span_font_sizes == (20.0, 20.0)

    def test_span_with_style_overrides_parent(self):
        # Span 1 inherits the parent (size=12); span 2 overrides
        # with size=24 — the resolved sizes reflect each span's
        # effective style.
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(text="alpha"),
                    TextSpan(text="beta", style=_style(24.0)),
                ],
                style=_style(12.0),
            )
        assert el.metrics.span_font_sizes == (12.0, 24.0)


# ---------------------------------------------------------------------------
# Layout & sizing
# ---------------------------------------------------------------------------


class TestLayout:
    def test_total_width_sums_per_span_widths_with_separator(self):
        # Each span (except the last) carries a trailing separator,
        # so the natural width = ``measure(s1+" ") + measure(s2)``.
        with _ctx():
            el = RichText(
                spans=[TextSpan(text="alpha"), TextSpan(text="beta")],
                style=_style(12.0),
            )
        expected = measure_text_width(
            "alpha ", Font.FINGER_KEY, 12.0
        ) + measure_text_width("beta", Font.FINGER_KEY, 12.0)
        assert abs(el.size.width - expected) < 0.5

    def test_no_shrink_when_natural_fits(self):
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(text="alpha"),
                    TextSpan(text="beta", style=_style(16.0)),
                ],
                style=_style(12.0),
                max_width=10_000,
            )
        assert el.metrics.span_font_sizes == (12.0, 16.0)
        assert el.metrics.truncated is False

    def test_uniform_shrink_preserves_proportions(self):
        # Two spans at 12 and 24 — under tight budget the relaxation
        # scales both by the same factor so their RATIO holds.
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(text="alpha"),
                    TextSpan(text="beta", style=_style(24.0)),
                ],
                style=_style(12.0),
                min_font_size=2.0,  # generous floor so neither span pins
                max_width=20.0,
            )
        a, b = el.metrics.span_font_sizes
        # Relative ratio 12:24 = 0.5 is preserved post-shrink.
        assert abs((a / b) - 0.5) < 0.01


class TestSlotFill:
    def test_size_matches_max_width_when_set(self):
        with _ctx():
            el = RichText(
                spans=[TextSpan(text="alpha")],
                style=_style(12.0),
                max_width=300.0,
            )
        assert el.size.width == 300.0

    def test_size_matches_natural_when_max_width_omitted(self):
        with _ctx():
            el = RichText(
                spans=[TextSpan(text="alpha")], style=_style(12.0)
            )
        natural = measure_text_width("alpha", Font.FINGER_KEY, 12.0)
        assert abs(el.size.width - natural) < 0.5


class TestBaselineAlignment:
    def test_height_accommodates_taller_span(self):
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(text="alpha"),
                    TextSpan(text="BETA", style=_style(40.0)),
                ],
                style=_style(12.0),
            )
        # The taller span dominates the row height.
        assert el.size.height >= 30.0


# ---------------------------------------------------------------------------
# Per-span proportional min_font_size — every span's floor scales with its
# own style.size by the parent ``min_font_size / style.size`` ratio.
# ---------------------------------------------------------------------------


class TestProportionalFloors:
    def test_ratio_preserved_after_shrink(self):
        # Parent (size=12, min=6) → ratio 0.5. Spans declared at
        # 12 and 24 inherit floors 6 and 12 respectively. With
        # proportional floors both spans share the same shrink
        # factor (the floor is reached at the same factor for
        # every span), so the resolved 12:24 ratio is preserved
        # whether the relaxation converges naturally or pins
        # everyone at their respective floors.
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(text="alpha"),
                    TextSpan(text="beta", style=_style(24.0)),
                ],
                style=_style(12.0),
                min_font_size=6.0,
                max_width=50.0,  # tight enough to shrink, loose enough to fit
            )
        a, b = el.metrics.span_font_sizes
        # Both shrink by the same factor — original 12:24 = 0.5
        # ratio holds.
        assert abs((a / b) - 0.5) < 0.05

    def test_no_min_font_size_means_no_shrink(self):
        # When ``min_font_size`` is None, every span's floor equals
        # its own style.size — no shrinking allowed. With no width
        # budget the spans render at their natural sizes; the
        # ``font_size`` resolution short-circuits because the floor
        # coincides with the natural size.
        with _ctx():
            el = RichText(
                spans=[
                    TextSpan(text="alpha"),
                    TextSpan(text="beta"),
                ],
                style=_style(20.0),
            )
        assert el.metrics.span_font_sizes == (20.0, 20.0)
        assert el.metrics.truncated is False


# ---------------------------------------------------------------------------
# Truncation — synthetic ``…`` spans inserted automatically when
# the relaxed set still doesn't fit
# ---------------------------------------------------------------------------


class TestTruncationStartAnchor:
    def test_appends_ellipsis_at_end(self):
        # Many spans, tight budget, default ``text_anchor="start"``.
        # Truncation drops from the end and appends ``…`` once.
        spans = [TextSpan(text=word) for word in ("alpha", "beta", "gamma", "delta", "epsilon")]
        with _ctx():
            el = RichText(
                spans=spans,
                style=_style(20.0),
                min_font_size=12.0,  # not enough headroom to fit at floor
                max_width=40.0,  # very tight
            )
        assert el.metrics.truncated is True
        # An ellipsis appears in the rendered output.
        assert _ELLIPSIS in el.metrics.rendered_spans
        # The ellipsis sits at the END of the rendered span list.
        assert el.metrics.rendered_spans[-1] == _ELLIPSIS

    def test_no_truncation_when_relaxation_fits(self):
        # Roomy budget, headroom in the floor — relaxation alone
        # gets the rendered text in.
        with _ctx():
            el = RichText(
                spans=[TextSpan(text="alpha"), TextSpan(text="beta")],
                style=_style(20.0),
                min_font_size=6.0,
                max_width=10_000,
            )
        assert el.metrics.truncated is False
        assert _ELLIPSIS not in el.metrics.rendered_spans


class TestTruncationEndAnchor:
    def test_prepends_ellipsis_at_start(self):
        spans = [TextSpan(text=word) for word in ("alpha", "beta", "gamma", "delta", "epsilon")]
        with _ctx():
            el = RichText(
                spans=spans,
                style=_style(20.0),
                min_font_size=12.0,
                max_width=40.0,
                text_anchor="end",
            )
        assert el.metrics.truncated is True
        # The ellipsis sits at the START of the rendered span list.
        assert el.metrics.rendered_spans[0] == _ELLIPSIS


class TestTruncationMiddleAnchor:
    def test_inserts_ellipsis_on_both_sides(self):
        spans = [TextSpan(text=word) for word in ("alpha", "beta", "gamma", "delta", "epsilon")]
        with _ctx():
            el = RichText(
                spans=spans,
                style=_style(20.0),
                min_font_size=12.0,
                max_width=80.0,
                text_anchor="middle",
            )
        assert el.metrics.truncated is True
        # Both first and last entries are the ellipsis.
        assert el.metrics.rendered_spans[0] == _ELLIPSIS
        assert el.metrics.rendered_spans[-1] == _ELLIPSIS

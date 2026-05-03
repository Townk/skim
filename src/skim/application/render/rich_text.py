# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Multi-span text composable, built on :func:`AdjustableText`.

A :func:`RichText` is a left-to-right concatenation of
:class:`TextSpan` objects, each carrying its own (optional)
:class:`TextStyle`. Spans without an explicit style inherit the
:func:`RichText`'s default ``style`` argument. Spans are separated
by a single space character — the separator is appended to a span's
text so it picks up that span's font / size / colour, which keeps
the rendered SVG predictable when adjacent spans have different
fonts.

Layering
--------

This is the **multi-span layer** of the text composable stack:

* :func:`AdjustableText` — single-style base. Owns the PIL
  measurement primitives.
* :func:`RichText` (this module) — composes ``AdjustableText``
  per span and keeps font sizes synchronised when shrinking, with
  per-span proportional ``min_font_size`` floors. Resolves Nerd
  Font tokens (``%%nf-...;``) into glyph characters before
  measurement / rendering. Adds ``…`` ellipsis spans automatically
  when the natural extent overflows the budget even at the floor.
* ``KeyLabel`` (future) — key-specific concerns built on
  ``RichText``.

Synchronised shrink (relaxation)
--------------------------------

When the natural extent overflows ``max_width`` / ``max_height``,
all span font sizes are scaled by a single uniform factor so visual
proportions between spans are preserved. Each span has its own
floor — derived proportionally from the ratio
``min_font_size / style.size`` so a span declared at size 14 with
a parent style of (size=12, min=8) gets a floor of ``14 * 8/12 ≈
9.33``. The relaxation loop pins spans at their floor as the scale
shrinks, redistributes the remaining budget to the still-free
spans, and repeats until either the rendered text fits or all
spans are pinned.

Truncation
----------

If the relaxed sizes still don't fit, :func:`RichText` enters a
truncation phase: drop spans from the trailing end (or both ends
for ``text_anchor="middle"``) and prepend / append a synthetic
``…`` :class:`TextSpan` painted with the parent ``style``. The
truncated set is re-relaxed each iteration so the ellipsis span
participates in the floor-pinning math. Truncation stops when the
set fits or only the ellipsis spans remain.

Baseline alignment
------------------

Spans of different sizes paint with different bbox heights. They
are vertically aligned on a common alphabetic baseline so the text
reads naturally — each span's ``AdjustableTextMetrics.baseline``
drives a per-span vertical offset within the row.
"""

from __future__ import annotations

from dataclasses import dataclass

from skim.application.loaders import load_nerdfont_glyphs
from skim.domain import SEPARATOR_CHAR

from .adjustable_text import (
    AdjustableText,
    measure_text_height,
    measure_text_width,
)
from .composable import Composable
from .primitives import MetricsComponent, Point, Size
from .render_context import TextStyle
from .styling import adjust_luminance
from .text import Font, _font_cmap

# Luminance multiplier applied to the key's background colour to
# derive the separator's stroke colour — mirrors legacy
# ``SeparatorPart.SEPARATOR_DARKEN_FACTOR``. The result is a darker
# version of the background, like the ghost label colour, so the
# bar reads as a faint divider rather than a glyph in its own right.
_SEPARATOR_LUMINANCE_FACTOR = 0.7

# Default inter-span separator. Appended to every span's text except
# the last so the gap between spans is rendered with the preceding
# span's font / size / colour and naturally contributes to that
# span's measured width. Internal note: the parser strips trailing /
# leading whitespace from text fragments at flush time, so the
# default separator is what reintroduces the inter-span gap with
# correct typography.
_DEFAULT_SEPARATOR = " "

# Single-character ellipsis used when truncation appends an extra
# span. Painted with the parent :func:`RichText`'s ``style`` so the
# ``…`` consistently matches the document voice rather than the
# style of whichever span happened to land next to it.
_ELLIPSIS = "…"


@dataclass(frozen=True, slots=True)
class TextSpan:
    """One run within a :func:`RichText`.

    ``text`` may include Nerd Font tokens (``%%nf-md-keyboard;``);
    they're resolved to their glyph characters before measurement
    and rendering.

    ``style`` is optional — when omitted the span inherits the
    parent :func:`RichText`'s ``style``. Setting it explicitly
    overrides font / size / colour for this span only and lets the
    parent style remain the document's "voice" while individual
    spans diverge as needed (e.g. an icon span using
    ``Font.SYMBOLS``).

    ``offset`` is a paint-time shift applied to where the span
    actually renders, in absolute SVG units. Layout — cursor
    advance, bbox, relaxation, truncation — proceeds as if the
    offset weren't there; only the call to ``draw_at`` adds the
    offset to the span's origin. Use it to compensate for glyphs
    whose font advance doesn't match the visible ink position
    (e.g. the box-drawing separator ``│`` U+2502 sits at the right
    edge of its advance box in Roboto, swallowing the trailing
    space — a negative ``offset.x`` shifts the visible bar back
    into the centre of its advance and lets the space breathe).
    """

    text: str
    style: TextStyle | None = None
    offset: Point = Point(0.0, 0.0)


@dataclass(frozen=True, slots=True, kw_only=True)
class RichTextMetrics:
    """Outcome of a :func:`RichText` resolution."""

    span_font_sizes: tuple[float, ...]
    """Resolved font size for each span actually painted, in order.

    Length matches ``rendered_spans`` — when truncation kicks in,
    this includes the synthetic ``…`` span(s) at the relevant end.
    """

    rendered_spans: tuple[str, ...]
    """The text actually painted for each span, in order.

    Each entry is the input span's text after Nerd Font glyph
    resolution. The inter-span ``" "`` separator is NOT folded into
    these strings (it's appended at measurement / render time
    instead). When truncation kicks in, ``"…"`` entries appear at
    the appropriate end(s).
    """

    truncated: bool
    """True when one or more input spans were dropped to fit the
    budget and at least one ``…`` span was inserted.
    """


# ---------------------------------------------------------------------------
# Glyph resolver
# ---------------------------------------------------------------------------


def resolve_nerd_font_glyphs(text: str) -> str:
    """Replace ``%%[nf-]<class>;`` tokens with their glyph characters.

    Tokens that don't map to a known glyph in the Nerd Font glyph
    dictionary are left as-is. The ``nf-`` prefix is optional —
    ``%%md-keyboard;`` and ``%%nf-md-keyboard;`` resolve to the
    same character. Mirrors the parser :class:`Label` uses
    internally so a span containing a token resolves to the same
    glyph the legacy ``Label.build_text`` path would paint.
    """
    glyphs = load_nerdfont_glyphs()
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if i + 2 < n and text[i] == "%" and text[i + 1] == "%":
            j = i + 2
            cls = ""
            while j < n and text[j] != ";":
                cls += text[j]
                j += 1
            if j < n and text[j] == ";":
                if not cls.startswith("nf-"):
                    cls = f"nf-{cls}"
                glyph = glyphs.get(cls)
                if glyph is not None:
                    out.append(glyph)
                    i = j + 1
                    continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _parse_into_spans(
    text: str,
    default_style: TextStyle,
    *,
    separator_background: str | None = None,
) -> list[TextSpan]:
    """Split ``text`` into a list of :class:`TextSpan` objects.

    Plain-text fragments become a span carrying ``default_style``;
    every Nerd Font token (``%%[nf-]<class>;``) becomes a single-
    character span carrying a style identical to ``default_style``
    except for the font, which switches to :attr:`Font.SYMBOLS` so
    the glyph renders correctly. The size and colour are inherited
    so the icon scales with the surrounding text.

    Tokens that don't resolve to a known glyph stay literal in
    their text span — the same fallback :func:`resolve_nerd_font_glyphs`
    applies. Adjacent text fragments don't merge across token
    boundaries; the returned list mirrors the structural break.

    Plain-text fragments are **stripped of leading and trailing
    whitespace** at flush time and a fragment that contains only
    whitespace is dropped entirely. This keeps the span list clean
    so the caller can rely on :func:`RichText`'s default
    ``separator=" "`` mechanism to put exactly one space between
    every pair of adjacent spans — without doubling up on whitespace
    that the input string happened to encode between tokens.

    When ``separator_background`` is supplied (typically the key's
    fill colour) the parser splits on the separator character (``│``,
    :data:`skim.domain.SEPARATOR_CHAR`) and emits a dedicated span
    for each separator with bold weight and a ghost colour derived
    from the background (via :func:`adjust_luminance` matching the
    legacy ``SeparatorPart.SEPARATOR_DARKEN_FACTOR``). The visual
    breathing room around the bar comes from :func:`RichText`'s
    inter-span separator just like every other adjacent span pair —
    that's the whole point of stripping whitespace here. Without a
    background colour the separator stays in the same span as the
    surrounding text and renders with the default style.

    Intended for callers that have a single string with mixed
    plain-text and icon content (e.g. a key label like
    ``"Foo %%nf-md-arrow-up;"``). Pair with the default
    ``RichText(separator=" ")`` so adjacent spans get a clean
    one-space gap without the caller having to reason about which
    fragments brought their own whitespace and which didn't.
    """
    glyphs = load_nerdfont_glyphs()
    symbols_style = TextStyle(
        font=Font.SYMBOLS,
        size=default_style.size,
        weight=default_style.weight,
        color=default_style.color,
    )
    # Unicode-symbols fallback: routes characters missing from the
    # default font through DejaVu Sans Condensed, which carries the
    # keyboard-symbol block (⎇, ⌘, ⌥, ⌃, ⇧, ↹, ⏎, ␣, ⌫, ⌦) plus
    # the box-drawing separator (│). The condensed variant covers
    # ⎇ (U+2387) at a regular stroke weight, which most UI /
    # programming fonts (Roboto, Cascadia, DejaVu Sans Mono) lack.
    # The visible glyph then renders with the SAME font we measure
    # against, so the cursor-based layout positions it correctly
    # without a paint-time offset.
    unicode_symbols_style = TextStyle(
        font=Font.UNICODE_SYMBOLS,
        size=default_style.size,
        weight=default_style.weight,
        color=default_style.color,
    )
    separator_style: TextStyle | None = None
    if separator_background is not None:
        # The separator paints in the Unicode-symbols font (DejaVu
        # has the box-drawing block) so the rendered bar lands
        # exactly where PIL measures it. Earlier Roboto-only
        # versions of this code carried a paint-time offset to
        # compensate for the browser's silent fallback to a wider
        # glyph; with DejaVu in the loop the offset is no longer
        # needed. The separator inherits the default style's weight
        # rather than forcing ``700`` so a Black-face thumb label
        # doesn't trigger synthetic-bold smearing on top of the
        # already-bold separator face.
        separator_style = TextStyle(
            font=Font.UNICODE_SYMBOLS,
            size=default_style.size,
            weight=default_style.weight,
            color=adjust_luminance(separator_background, _SEPARATOR_LUMINANCE_FACTOR),
        )
    default_cmap = _font_cmap(default_style.font)
    unicode_symbols_cmap = _font_cmap(Font.UNICODE_SYMBOLS)
    spans: list[TextSpan] = []
    text_buffer: list[str] = []

    def _flush_text() -> None:
        if not text_buffer:
            return
        text_segment = "".join(text_buffer).strip()
        text_buffer.clear()
        if text_segment:
            spans.append(TextSpan(text=text_segment, style=default_style))

    def _emit_centred_fallback(ch: str, style: TextStyle) -> None:
        """Emit ``ch`` as its own span with a centring paint-time offset.

        Last-resort path for characters present in NEITHER the
        requesting span's font nor :attr:`Font.UNICODE_SYMBOLS` —
        PIL measures their advance via the font's ``.notdef``
        glyph but the browser silently falls back to a different
        font with a wider visible glyph. Shifting the paint origin
        left by half the measured advance re-centres the rendered
        glyph in its measured advance box. With DejaVu Sans Condensed in
        the Unicode-symbols slot this branch fires only for the
        rare ``⎈`` (U+2388 HELM SYMBOL) and any other esoteric
        glyphs that DejaVu doesn't carry.
        """
        adv = measure_text_width(ch, style.font, style.size)
        spans.append(TextSpan(text=ch, style=style, offset=Point(-adv / 2.0, 0.0)))

    i = 0
    n = len(text)
    while i < n:
        if i + 2 < n and text[i] == "%" and text[i + 1] == "%":
            j = i + 2
            cls = ""
            while j < n and text[j] != ";":
                cls += text[j]
                j += 1
            if j < n and text[j] == ";":
                if not cls.startswith("nf-"):
                    cls = f"nf-{cls}"
                glyph = glyphs.get(cls)
                if glyph is not None:
                    _flush_text()
                    spans.append(TextSpan(text=glyph, style=symbols_style))
                    i = j + 1
                    continue
        if separator_style is not None and text[i] == SEPARATOR_CHAR:
            _flush_text()
            # The separator (``│`` U+2502) is missing from Roboto
            # but present in DejaVu Sans Condensed — emit it as a
            # :attr:`Font.UNICODE_SYMBOLS` span with the ghost colour
            # so the rendered bar lands exactly where PIL measures
            # it. No paint-time offset needed.
            spans.append(TextSpan(text=SEPARATOR_CHAR, style=separator_style))
            i += 1
            continue
        if ord(text[i]) not in default_cmap and not text[i].isspace():
            _flush_text()
            if ord(text[i]) in unicode_symbols_cmap:
                # Route through DejaVu Sans Condensed — the rendered glyph
                # uses the SAME font we measure against, so the
                # cursor-based layout positions it correctly.
                spans.append(TextSpan(text=text[i], style=unicode_symbols_style))
            else:
                # Last-ditch: PIL measures via ``.notdef`` while the
                # browser falls back silently. Centre the visible
                # glyph in its measured advance box. Triggers only
                # for code points missing from both Roboto and DejaVu
                # — primarily ``⎈`` (U+2388 HELM SYMBOL) and the
                # rare emoji.
                _emit_centred_fallback(text[i], default_style)
            i += 1
            continue
        text_buffer.append(text[i])
        i += 1
    _flush_text()
    return spans


def measure_rich_text_width(text: str, style: TextStyle) -> float:
    """Natural rendered width of a Nerd-Font-tokenised label.

    Splits ``text`` on Nerd Font tokens (matching what
    :func:`RichText` would render) and sums the per-span PIL-measured
    widths at each span's effective font and size. Plain-text
    fragments use ``style.font`` / ``style.size``; token spans
    switch to :attr:`Font.SYMBOLS` at the same size — the same
    routing :func:`RichText` applies.

    Use this when a caller needs the natural width of a marked-up
    label *before* deciding the layout slot to give to a
    :func:`RichText` (e.g. pill-rectangle sizing, glyph-cell width
    pre-pass). Saves the caller from instantiating a composable
    just to read off a measurement.
    """
    spans = _parse_into_spans(text, style)
    return sum(
        measure_text_width(
            span.text,
            (span.style or style).font,
            (span.style or style).size,
        )
        for span in spans
    )


# ---------------------------------------------------------------------------
# Internal: relaxation + truncation
# ---------------------------------------------------------------------------


def _texts_with_separators(raw: list[str], separator: str) -> list[str]:
    """Append ``separator`` to all entries except the last.

    Built fresh each time the trial set changes (e.g. when a span
    is dropped during truncation) so the right span always gets the
    trailing separator regardless of how the list was assembled.
    Pass ``separator=""`` to disable (callers that have explicit
    spacing baked into their input strings).
    """
    if not separator:
        return list(raw)
    n = len(raw)
    return [r + (separator if i < n - 1 else "") for i, r in enumerate(raw)]


def _measure_widths(
    styles: list[TextStyle],
    rendered: list[str],
    sizes: list[float],
    separator: str,
) -> list[float]:
    """Measure each span's painted width at its current font size."""
    seps = _texts_with_separators(rendered, separator)
    return [measure_text_width(seps[i], styles[i].font, sizes[i]) for i in range(len(seps))]


def _relax_sizes(
    *,
    styles: list[TextStyle],
    mins: list[float],
    rendered: list[str],
    max_width: float | None,
    max_height: float | None,
    separator: str,
) -> list[float]:
    """Run the synchronised-shrink relaxation loop on a trial set.

    Starts at each span's natural ``style.size``. If the rendered
    extent overflows, computes a uniform shrink factor for the
    "free" (un-pinned) spans and applies it. Spans that would fall
    below their floor pin at ``min``; the loop redistributes the
    remaining budget to the still-free spans. Repeats until the
    set fits, no progress is made, or every span is pinned.

    The loop iterates more than once for two reasons: PIL's
    ``getlength`` is mildly non-linear in font size due to glyph
    hinting (e.g. ``"alpha"`` at 12pt = 31 units, at 24pt = 58 —
    ratio 1.87, not 2.0). The closed-form factor undershoots; we
    re-measure and re-apply until the rendered total lands inside
    the budget. As scale shrinks, spans hit their floor and pin;
    each iteration may pin one or more new spans and redistribute.

    Termination: rendered set fits within a half-pixel tolerance
    (PIL widths are typically integer-valued), every span pinned,
    no measurable progress in one iteration, or a hard iteration
    cap as a safety net.
    """
    n = len(styles)
    if n == 0:
        return []
    sizes = [s.size for s in styles]
    pinned = [False] * n

    # Initial height check — all spans scale by the same factor
    # against the tallest natural height, so pinning isn't relevant
    # here. The width pass below also clamps against this factor.
    if max_height is not None:
        natural_heights = [
            measure_text_height(rendered[i], styles[i].font, styles[i].size) for i in range(n)
        ]
        tallest = max(natural_heights, default=0.0)
        if tallest > max_height and tallest > 0:
            height_factor = max_height / tallest
            sizes = [max(mins[i], sizes[i] * height_factor) for i in range(n)]
            for i in range(n):
                if sizes[i] <= mins[i] + 1e-9:
                    pinned[i] = True

    if max_width is None:
        return sizes

    # Half-pixel slack — PIL widths come in at integer-ish values
    # so anything within 0.5 of the budget is effectively a fit.
    tolerance = 0.5
    # ``2 * (n + 1)`` is a safety cap; convergence usually happens
    # in 2–3 iterations even with non-linear hinting.
    for _ in range(2 * (n + 1)):
        widths = _measure_widths(styles, rendered, sizes, separator)
        total = sum(widths)
        if total <= max_width + tolerance:
            return sizes

        free = [i for i in range(n) if not pinned[i]]
        if not free:
            return sizes  # no headroom anywhere

        free_w = sum(widths[i] for i in free)
        pinned_w = total - free_w
        budget = max_width - pinned_w

        if budget <= 0 or free_w == 0:
            for i in free:
                sizes[i] = mins[i]
                pinned[i] = True
            continue

        factor = budget / free_w
        if factor >= 1.0:
            return sizes  # numerical edge — already at-or-under

        progressed = False
        for i in free:
            new_size = sizes[i] * factor
            if new_size <= mins[i] + 1e-9:
                new_size = mins[i]
                pinned[i] = True
            if abs(new_size - sizes[i]) > 1e-6:
                progressed = True
            sizes[i] = new_size
        if not progressed:
            return sizes  # converged within tolerance

    return sizes


def _fits_at_sizes(
    styles: list[TextStyle],
    rendered: list[str],
    sizes: list[float],
    max_width: float,
    separator: str,
) -> bool:
    """Whether the rendered set fits inside ``max_width`` at ``sizes``.

    Uses the same half-pixel tolerance as :func:`_relax_sizes` so
    the relaxation's "converged" exit and the truncation-trigger
    "doesn't fit" check agree on what counts as fitting.
    """
    return sum(_measure_widths(styles, rendered, sizes, separator)) <= max_width + 0.5


def _truncate_with_ellipses(
    *,
    styles: list[TextStyle],
    mins: list[float],
    rendered: list[str],
    offsets: list[Point],
    max_width: float,
    max_height: float | None,
    text_anchor: str,
    ellipsis_style: TextStyle,
    ellipsis_min: float,
    separator: str,
) -> tuple[list[TextStyle], list[float], list[str], list[float], list[Point]]:
    """Drop spans + insert ellipsis span(s) until the trial set fits.

    For ``text_anchor`` of ``"start"`` (default), the ellipsis is
    appended once at the end and spans are dropped from the trailing
    end. For ``"end"`` the ellipsis is prepended and spans are
    dropped from the leading end. For ``"middle"`` an ellipsis is
    inserted at both ends and spans are dropped symmetrically (the
    drop alternates between ends each iteration).

    Returns the trimmed ``(styles, mins, rendered, sizes)`` for the
    surviving spans plus the inserted ellipsis span(s).
    """
    if text_anchor == "end":
        prefix_count, suffix_count = 1, 0
    elif text_anchor == "middle":
        prefix_count, suffix_count = 1, 1
    else:  # "start" — the default
        prefix_count, suffix_count = 0, 1

    kept = list(range(len(styles)))
    # Alternate dropping between ends for "middle" so truncation
    # stays roughly symmetric across iterations.
    drop_from_end = True

    zero_offset = Point(0.0, 0.0)
    while True:
        trial_styles: list[TextStyle] = []
        trial_mins: list[float] = []
        trial_rendered: list[str] = []
        trial_offsets: list[Point] = []
        for _ in range(prefix_count):
            trial_styles.append(ellipsis_style)
            trial_mins.append(ellipsis_min)
            trial_rendered.append(_ELLIPSIS)
            trial_offsets.append(zero_offset)
        for k in kept:
            trial_styles.append(styles[k])
            trial_mins.append(mins[k])
            trial_rendered.append(rendered[k])
            trial_offsets.append(offsets[k])
        for _ in range(suffix_count):
            trial_styles.append(ellipsis_style)
            trial_mins.append(ellipsis_min)
            trial_rendered.append(_ELLIPSIS)
            trial_offsets.append(zero_offset)

        sizes = _relax_sizes(
            styles=trial_styles,
            mins=trial_mins,
            rendered=trial_rendered,
            max_width=max_width,
            max_height=max_height,
            separator=separator,
        )
        if _fits_at_sizes(trial_styles, trial_rendered, sizes, max_width, separator):
            return trial_styles, trial_mins, trial_rendered, sizes, trial_offsets

        if not kept:
            # Only the ellipsis span(s) remain — return them even if
            # they overflow; nothing more can be dropped.
            return trial_styles, trial_mins, trial_rendered, sizes, trial_offsets

        if text_anchor == "middle":
            if drop_from_end:
                kept.pop()
            else:
                kept.pop(0)
            drop_from_end = not drop_from_end
        elif text_anchor == "end":
            kept.pop(0)
        else:  # "start"
            kept.pop()


# ---------------------------------------------------------------------------
# Composable
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def RichText(
    ctx,
    *,
    text: str | None = None,
    spans: list[TextSpan] | None = None,
    style: TextStyle,
    max_width: float | None = None,
    max_height: float | None = None,
    min_font_size: float | None = None,
    text_anchor: str = "start",
    dominant_baseline: str = "text-before-edge",
    opacity: float = 1.0,
    separator: str = _DEFAULT_SEPARATOR,
    separator_background: str | None = None,
):
    """Multi-span text with synchronised shrink-to-fit and ellipsis truncation.

    Accepts ``text`` containing Nerd Font tokens
    (``%%[nf-]<class>;``) and the optional inline separator
    character. Internally splits the input into per-span runs:
    plain-text fragments adopt the document's ``style``, Nerd Font
    tokens become single-character spans on :attr:`Font.SYMBOLS` so
    the glyph renders correctly while inheriting size and colour.
    Each run is then painted as an :func:`AdjustableText`, laid out
    left-to-right and baseline-aligned.

    ``style`` is the document's default — applied to every plain-text
    span and as the inheritance base for token spans. ``min_font_size``
    is the floor for the parent ``style``; per-span floors derive
    proportionally from the ratio ``min_font_size / style.size``,
    so a span at size 14 under a parent of (size=12, min=8) gets a
    floor of ``14 * 8/12 ≈ 9.33``.

    ``separator`` is auto-appended to every span's text except the
    last (rendered with that span's font, so it picks up the right
    metrics). Default is a single space — the parser strips
    leading / trailing whitespace from text fragments at flush time
    and the separator reintroduces the inter-span gap with correct
    typography.

    ``separator_background`` opts into the box-drawing-bar
    rendering for the ``│`` separator character: the parser
    additionally splits on ``│``, picks a darker shade derived from
    the supplied background colour, and paints a vertical bar in
    that colour. Used by the Svalboard key composables when a
    label embeds the ``│`` separator (e.g. ``LT(N, KC_A)`` →
    ``"A│N"``).

    When the natural extent overflows the budget, the relaxation
    loop shrinks all spans by a single factor (preserving
    proportions); spans hitting their floor pin and the remaining
    budget redistributes to the rest. If the set still doesn't fit
    after pinning, ``RichText`` enters truncation: it drops spans
    from the trailing end (or symmetrically for
    ``text_anchor="middle"``) and inserts ``…`` spans painted with
    the parent ``style``. The truncated set is re-relaxed each
    iteration.

    Empty ``text`` (or empty ``spans``) yields a zero-sized noop.

    Test / advanced callers may pass ``spans`` directly to bypass the
    parser — exactly one of ``text`` or ``spans`` must be supplied.
    Production code should always use ``text``.
    """
    del ctx  # AdjustableText reads its own context; nothing here.

    if (text is None) == (spans is None):
        raise TypeError("RichText: provide exactly one of `text` or `spans`")
    if spans is None:
        spans = _parse_into_spans(text or "", style, separator_background=separator_background)
    if not spans:
        size = Size(0.0, 0.0)

        def _noop(d, origin):
            del d, origin

        return MetricsComponent(
            size=size,
            draw_fn=_noop,
            metrics=RichTextMetrics(
                span_font_sizes=(),
                rendered_spans=(),
                truncated=False,
            ),
        )

    # 1. Resolve effective per-span style. Spans without a style
    #    inherit the parent's. Resolve glyphs in the same pass.
    effective_styles = [span.style if span.style is not None else style for span in spans]
    rendered = [resolve_nerd_font_glyphs(span.text) for span in spans]
    span_offsets = [span.offset for span in spans]

    # 2. Resolve per-span min_font_size proportionally from the
    #    parent ratio. ``min_font_size`` is clamped to ``style.size``
    #    (a higher floor would enlarge the text — not allowed).
    parent_min = min(min_font_size, style.size) if min_font_size is not None else style.size
    parent_ratio = parent_min / style.size if style.size > 0 else 1.0
    span_mins = [es.size * parent_ratio for es in effective_styles]

    # 3. Run relaxation on the original span set.
    sizes = _relax_sizes(
        styles=effective_styles,
        mins=span_mins,
        rendered=rendered,
        max_width=max_width,
        max_height=max_height,
        separator=separator,
    )

    # 4. If the relaxed sizes still overflow ``max_width``, enter
    #    the truncation phase. Inserts ``…`` span(s) painted with
    #    the parent style and drops original spans iteratively.
    truncated = False
    if max_width is not None and not _fits_at_sizes(
        effective_styles, rendered, sizes, max_width, separator
    ):
        effective_styles, span_mins, rendered, sizes, span_offsets = _truncate_with_ellipses(
            styles=effective_styles,
            mins=span_mins,
            rendered=rendered,
            offsets=span_offsets,
            max_width=max_width,
            max_height=max_height,
            text_anchor=text_anchor,
            ellipsis_style=style,
            ellipsis_min=parent_min,
            separator=separator,
        )
        truncated = True

    # 5. Build an ``AdjustableText`` per (resolved) span. Each
    #    span's style is replaced with the resolved size; no
    #    per-span ``max_width`` since the relaxation already
    #    sized them to fit.
    sep_rendered = _texts_with_separators(rendered, separator)
    span_elements = [
        AdjustableText(
            text=text,
            style=TextStyle(font=es.font, size=size_, weight=es.weight, color=es.color),
            text_anchor="start",
            dominant_baseline=dominant_baseline,
            opacity=opacity,
        )
        for es, size_, text in zip(effective_styles, sizes, sep_rendered, strict=True)
    ]

    # 6. Baseline-aligned layout. Pick the largest baseline as the
    #    common reference so every span's bbox top sits at a
    #    non-negative offset from the row's bbox top.
    span_widths = [el.size.width for el in span_elements]
    span_heights = [el.size.height for el in span_elements]
    span_baselines = [el.metrics.baseline for el in span_elements]
    common_baseline = max(span_baselines, default=0.0)
    span_top_offsets = [common_baseline - b for b in span_baselines]
    rich_natural_w = sum(span_widths)
    rich_h = max(
        (top + h for top, h in zip(span_top_offsets, span_heights, strict=True)),
        default=0.0,
    )

    # 7. Slot fill via ``max_width``: the bbox reports ``max_width``
    #    when set, with ``text_anchor`` controlling where inside the
    #    slot the painted row lands.
    bbox_w = max_width if max_width is not None else rich_natural_w
    size = Size(bbox_w, rich_h)

    if text_anchor == "end":
        x_offset = bbox_w - rich_natural_w
    elif text_anchor == "middle":
        x_offset = (bbox_w - rich_natural_w) / 2.0
    else:
        x_offset = 0.0

    def draw_at(d, origin: Point) -> None:
        # ``cursor_x`` advances by the span's natural width — the
        # per-span ``offset`` is applied ONLY to the paint position,
        # so a span shifted left by its offset doesn't drag the
        # following spans with it. That keeps layout / centering
        # math independent of any paint-time tweaks (used by the
        # separator span to pull the ``│`` glyph back into the
        # centre of its advance box without disturbing the rest of
        # the row).
        cursor_x = origin.x + x_offset
        for el, w, top, off in zip(
            span_elements, span_widths, span_top_offsets, span_offsets, strict=True
        ):
            el.draw_at(d, Point(cursor_x + off.x, origin.y + top + off.y))
            cursor_x += w

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=RichTextMetrics(
            span_font_sizes=tuple(sizes),
            rendered_spans=tuple(rendered),
            truncated=truncated,
        ),
    )


__all__ = ["RichText", "measure_rich_text_width"]

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Multi-span text composable, built on :func:`AdjustableText`.

A :func:`RichText` is a left-to-right concatenation of
:class:`TextSpan` objects, each carrying its own :class:`TextStyle`
(font, size, colour). Spans are separated by a single space
character — the separator is appended to a span's text so it picks
up that span's font / size / colour, which keeps the shape of the
rendered SVG predictable when adjacent spans have different fonts.

Layering
--------

This is the **multi-span layer** of the text composable stack:

* :func:`AdjustableText` — single-style base. Owns the PIL
  measurement primitives.
* :func:`RichText` (this module) — composes ``AdjustableText``
  per span and keeps font sizes synchronised when shrinking.
  Resolves Nerd Font tokens (``%%nf-...;``) into glyph
  characters before measurement / rendering.
* ``KeyLabel`` (future) — key-specific concerns built on
  ``RichText``.

Synchronised shrink
-------------------

When a width / height budget is set and the natural extent
overflows, all span font sizes are scaled by a single uniform
factor so visual proportions between spans are preserved. The
optional ``min_font_size`` is a global floor — when scaling would
push a span below it, that span pins at the floor (which may break
the uniform scaling and cause the rendered text to overflow the
budget at that point). Truncation isn't supported at this layer
yet; if you need it, pre-truncate the input or wait for the
truncation pass to land.

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

from .adjustable_text import (
    AdjustableText,
    measure_text_height,
    measure_text_width,
)
from .composable import Composable
from .primitives import MetricsComponent, Point, Size
from .render_context import TextStyle

# Inter-span separator. Appended to every span's text except the
# last so the gap between spans is rendered with the preceding
# span's font / size / colour and naturally contributes to that
# span's measured width.
_SEPARATOR = " "


@dataclass(frozen=True, slots=True)
class TextSpan:
    """One single-style run within a :func:`RichText`.

    Carries the typography (:class:`TextStyle`) and the literal text
    for this span. The text may include Nerd Font tokens
    (``%%nf-md-keyboard_close;`` etc.); they are resolved to their
    glyph characters when the span is laid out — the resolved
    text is what the underlying :func:`AdjustableText` renders.
    """

    style: TextStyle
    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RichTextMetrics:
    """Outcome of a :func:`RichText` resolution.

    Exposes the resolved per-span font sizes and the uniform shrink
    factor that produced them so a parent can align siblings or
    drive follow-up layout decisions.
    """

    font_scale: float
    """Uniform shrink factor applied to every span's ``style.size``.

    ``1.0`` means no shrinking was needed; smaller values mean the
    natural extent overflowed the budget.
    """

    span_font_sizes: tuple[float, ...]
    """Resolved font size for each span, in input order.

    Equal to ``span.style.size * font_scale`` when no floor was hit;
    raised to ``min_font_size`` for any span the uniform scale would
    have pushed below the floor.
    """

    rendered_spans: tuple[str, ...]
    """The text actually painted for each span, in input order.

    Equal to each span's input text after Nerd Font glyph resolution
    (and with a trailing separator on every span except the last).
    """


# ---------------------------------------------------------------------------
# Glyph resolver
# ---------------------------------------------------------------------------


def resolve_nerd_font_glyphs(text: str) -> str:
    """Replace ``%%[nf-]<class>;`` tokens with their glyph characters.

    Tokens that don't map to a known glyph in the Nerd Font glyph
    dictionary are left as-is. The ``nf-`` prefix is optional in the
    token — ``%%md-keyboard_close;`` and ``%%nf-md-keyboard_close;``
    resolve identically. Mirrors the parser :class:`Label` uses
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


# ---------------------------------------------------------------------------
# Composable
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def RichText(
    ctx,
    *,
    spans: list[TextSpan],
    max_width: float | None = None,
    max_height: float | None = None,
    min_font_size: float | None = None,
    text_anchor: str = "start",
    dominant_baseline: str = "text-before-edge",
    opacity: float = 1.0,
):
    """Multi-span text with synchronised shrink-to-fit.

    Each span renders as an :func:`AdjustableText` with its own
    style; they're laid out left-to-right and baseline-aligned.
    Inter-span separators (``" "``) are appended to every span's
    text except the last so the gap takes on the preceding span's
    font.

    When ``max_width`` is set the bbox occupies that full width and
    the row of spans is anchored within it via ``text_anchor``
    (``"start"``, ``"middle"`` or ``"end"``). When omitted the
    bbox snug-fits the rendered spans.

    Empty ``spans`` yields a zero-sized noop. Currently no
    truncation pass — if the natural extent overflows even after
    shrinking, the painted text overflows the budget. (A future
    pass can add ellipsis truncation across spans.)
    """
    del ctx  # ``AdjustableText`` reads its own context; nothing here.

    if not spans:
        size = Size(0.0, 0.0)

        def _noop(d, origin):
            del d, origin

        return MetricsComponent(
            size=size,
            draw_fn=_noop,
            metrics=RichTextMetrics(
                font_scale=1.0, span_font_sizes=(), rendered_spans=()
            ),
        )

    # 1. Resolve Nerd Font glyphs and append the inter-span separator
    #    to every span except the last. The separator picks up the
    #    preceding span's typography so its width contributes to that
    #    span's measured width naturally.
    n = len(spans)
    rendered = tuple(
        resolve_nerd_font_glyphs(span.text) + (_SEPARATOR if i < n - 1 else "")
        for i, span in enumerate(spans)
    )

    # 2. Measure each span at its natural ``style.size``.
    natural_widths = [
        measure_text_width(text, span.style.font, span.style.size)
        for span, text in zip(spans, rendered)
    ]
    natural_heights = [
        measure_text_height(text, span.style.font, span.style.size)
        for span, text in zip(spans, rendered)
    ]
    total_natural_w = sum(natural_widths)
    tallest_natural_h = max(natural_heights, default=0.0)

    # 3. Compute the uniform shrink factor. Width and height both
    #    scale linearly with font size for plain text, so taking the
    #    smaller of the two budget-driven factors is the largest scale
    #    that satisfies both.
    scale = 1.0
    if max_width is not None and total_natural_w > max_width and total_natural_w > 0:
        scale = min(scale, max_width / total_natural_w)
    if (
        max_height is not None
        and tallest_natural_h > max_height
        and tallest_natural_h > 0
    ):
        scale = min(scale, max_height / tallest_natural_h)

    # 4. Apply the uniform scale per span; floor at ``min_font_size``
    #    when set. Spans pinned at the floor break the uniform scaling
    #    — accept that here; the rendered output may overflow at that
    #    point. Truncation across spans is a future pass.
    floor = min_font_size if min_font_size is not None else 0.0
    span_font_sizes = tuple(
        max(floor, span.style.size * scale) for span in spans
    )

    # 5. Build an ``AdjustableText`` per span with the resolved size
    #    baked into a fresh ``TextStyle``. No per-span ``max_width`` —
    #    each span renders at its natural rendered width given the
    #    resolved font size.
    span_elements = [
        AdjustableText(
            text=text,
            style=TextStyle(
                font=span.style.font, size=size, color=span.style.color
            ),
            text_anchor="start",
            dominant_baseline=dominant_baseline,
            opacity=opacity,
        )
        for span, text, size in zip(spans, rendered, span_font_sizes)
    ]

    # 6. Baseline-aligned layout. ``AdjustableTextMetrics.baseline``
    #    is each span's y-offset from its own bbox top to the
    #    alphabetic baseline. Picking the largest baseline as the
    #    common reference puts every span's bbox top at a
    #    non-negative offset from the row's bbox top.
    span_widths = [el.size.width for el in span_elements]
    span_heights = [el.size.height for el in span_elements]
    span_baselines = [el.metrics.baseline for el in span_elements]
    common_baseline = max(span_baselines, default=0.0)
    span_top_offsets = [common_baseline - b for b in span_baselines]
    rich_natural_w = sum(span_widths)
    rich_h = max(
        (top + h for top, h in zip(span_top_offsets, span_heights)),
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
        cursor_x = origin.x + x_offset
        for el, w, top in zip(span_elements, span_widths, span_top_offsets):
            el.draw_at(d, Point(cursor_x, origin.y + top))
            cursor_x += w

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=RichTextMetrics(
            font_scale=scale,
            span_font_sizes=span_font_sizes,
            rendered_spans=rendered,
        ),
    )


__all__ = [
    "RichText",
    "RichTextMetrics",
    "TextSpan",
    "resolve_nerd_font_glyphs",
]

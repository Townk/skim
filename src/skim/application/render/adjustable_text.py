# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Auto-sizing / truncating text composable — single-style base layer.

Pulls together the font-measurement, shrink-to-fit and ellipsis-
truncate logic that used to live inline in :mod:`header`,
:mod:`footer` and :mod:`tap_dance`. The behaviour matrix:

* ``min_font_size`` (defaulted to ``style.size``) sets how far the
  font can shrink. When the default applies there's no headroom to
  shrink, so the composable goes straight to truncation.
* ``max_height`` shrinks the font to fit when the natural rendered
  glyph bbox would be taller than the budget.
* ``max_width`` shrinks the font to fit when the natural rendered
  width exceeds the budget. If shrinking bottoms out at
  ``min_font_size`` and the rendered text still doesn't fit, the
  text is trimmed with an ``…`` ellipsis (PIL-accurate).

Truncation only ever applies when ``max_width`` is set — height is
purely a function of the font size, so an over-tall text never has
an ``…`` answer.

Single-style scope
------------------

This is the **base layer** of the text-rendering composable stack:
the input ``text`` is treated as a single style — one font, one
size, one colour — and the rendered SVG is a flat ``<text>``
element. The module deliberately doesn't import :class:`Label`;
multi-format text (mixed fonts, Nerd Font icon glyphs alongside
text glyphs, per-span colour) is the next layer up: a future
``RichText`` composable will compose multiple ``AdjustableText``
elements (or use the same primitives) to handle spans, and a
``KeyLabel`` composable on top of that will own key-specific
rendering.

The PIL-driven measurement primitives (``getlength`` for width,
``getbbox`` for height and reference lines) all live here so this
module is the canonical measurement source for any text-aware
composable to build on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import drawsvg as draw

from .composable import Composable
from .font import Font, register_font_usage
from .primitives import MetricsComponent, Point, Size
from .render_context import TextStyle

# Single-character ellipsis used when truncating. PIL's ``getlength``
# is character-sensitive, so the measurement helper and the trim
# loop must agree on the same glyph.
_ELLIPSIS = "…"


@dataclass(frozen=True, slots=True, kw_only=True)
class AdjustableTextMetrics:
    """Outcome of an :func:`AdjustableText` resolution.

    Exposed so callers that need to size or align a sibling element
    based on the resolved text (e.g. the header sizing the logo to
    the title's resolved height, or a tap-dance row using the
    resolved font size for cell label positioning) can read the
    final values directly off the component.
    """

    font_size: float
    """Resolved font size after the shrink pass.

    Equals ``style.size`` when no shrinking was needed; otherwise
    bounded below by ``min_font_size``.
    """

    rendered_text: str
    """The text actually painted.

    Equal to the input ``text`` unless ``max_width`` forced a trim,
    in which case it ends with ``…``.
    """

    truncated: bool
    """True when the painted text has been ellipsized."""

    baseline: float
    """Y-offset from the bbox top to the alphabetic baseline.

    The line on which ``H``, ``x``, ``a`` rest. Useful for aligning
    decorations (an underline, a strike-through anchor) to the
    rendered text. Same reference frame as the component's
    :attr:`size` — add ``origin.y + baseline`` to land on the
    baseline in the parent's coordinate space.
    """

    meanline: float
    """Y-offset from the bbox top to the x-height (lowercase ceiling).

    The line that the tops of ``x``, ``a``, ``c`` sit on. Useful
    for aligning a sibling element (icon, chip, glyph) to the
    visual centre of lowercase text via
    ``(baseline + meanline) / 2``.
    """

    ascender_line: float
    """Y-offset from the bbox top to the ascender / cap-height line.

    The line that the tops of ``H``, ``b``, ``l`` reach. May be
    negative when the rendered text contains no ascenders or
    capitals — e.g. ``"x"`` alone has its bbox top at the meanline,
    so the ascender line sits above ``y=0``. The bbox itself is
    sized to the rendered text, not to the full font cell.
    """


# ---------------------------------------------------------------------------
# Measurement helpers (PIL-accurate, single-style)
# ---------------------------------------------------------------------------


def _pil_size_factor(font_size: float) -> tuple[int, float]:
    """The integer size :class:`Font` loads PIL at, plus the linear-scale
    factor that converts a measurement at that int size back to
    ``font_size``.

    PIL operates on integer point sizes; :meth:`Font.load` ``ceil``s
    the requested ``font_size`` so the loaded font is at-or-above
    the requested size (otherwise widths underestimate when
    ``font_size`` falls between two ints, leaving long labels to
    overflow the slot the layout reserved for them). Scaling the
    raw measurement by ``font_size / int_size`` brings it back to
    the requested size — closer to what an SVG renderer paints at
    the float ``font_size`` than just using the int-size width.
    """
    int_size = max(int(math.ceil(font_size)), 1)
    return int_size, font_size / int_size


def measure_text_width(text: str, font: Font, font_size: float) -> float:
    """Rendered width of ``text`` at ``font_size`` in SVG units.

    The canonical "measure single-style text as it'll be painted"
    primitive for the composable layer — the actual PIL
    ``getlength`` call lives here. Higher-level composables (a
    future ``RichText`` for multi-span text, ``KeyLabel`` for
    key-specific rendering) build on this.

    The text is treated as a single font / size run; mixed-format
    input (e.g. plain text alongside Nerd Font icon tokens) is a
    higher-layer concern. Use a multi-span composable for that.
    """
    if not text or font_size <= 0:
        return 0.0
    _, factor = _pil_size_factor(font_size)
    return float(font.load(font_size).getlength(text)) * factor


def measure_text_height(text: str, font: Font, font_size: float) -> float:
    """Rendered glyph-bbox height of ``text`` at ``font_size`` in SVG units.

    Companion to :func:`measure_text_width`. PIL's ``getbbox``
    reports the tight bounding box of the rendered text, which is
    what the SVG renderer ends up painting (regardless of the
    font's full ascent / descent extent).
    """
    if not text or font_size <= 0:
        return 0.0
    _, factor = _pil_size_factor(font_size)
    pil_font = font.load(font_size)
    _, top, _, bottom = pil_font.getbbox(text)
    return float(bottom - top) * factor


def _reference_lines(text: str, font: Font, font_size: float) -> tuple[float, float, float]:
    """Return ``(baseline, meanline, ascender_line)`` y-offsets within
    the rendered text's bbox.

    All three are offsets (in SVG units at ``font_size``) from the
    bbox top — the same reference frame as the bbox itself, so a
    parent can add ``origin.y + baseline`` to land on the rendered
    alphabetic baseline. The reference characters ``"x"`` (top at
    meanline, bottom at baseline) and ``"H"`` (top at cap height /
    ascender) are measured at the same font size and translated
    into the rendered text's bbox-local coords by subtracting the
    rendered text's bbox top.

    Values may be negative when the reference line sits above the
    bbox top — e.g. for a string of ``"x"`` alone, the ascender
    line is above the rendered glyph.
    """
    if not text:
        return 0.0, 0.0, 0.0
    _, factor = _pil_size_factor(font_size)
    pil_font = font.load(font_size)
    _, x_top, _, x_bottom = pil_font.getbbox("x")
    _, h_top, _, _ = pil_font.getbbox("H")
    _, text_top, _, _ = pil_font.getbbox(text)
    baseline = float(x_bottom - text_top) * factor
    meanline = float(x_top - text_top) * factor
    ascender_line = float(h_top - text_top) * factor
    return baseline, meanline, ascender_line


def _truncate_to_fit(text: str, font: Font, font_size: float, max_width: float) -> tuple[str, bool]:
    """Trim ``text`` so its rendered width fits inside ``max_width``.

    Returns ``(trimmed_text, was_truncated)``. When the natural
    rendered width already fits, ``text`` is returned unchanged with
    ``was_truncated=False``. Otherwise the longest prefix that —
    once an ellipsis is appended — still fits within ``max_width``
    is selected via binary search. When ``max_width`` is so tight
    that not even the ellipsis fits, the ellipsis is returned alone.
    """
    if max_width <= 0 or not text:
        return "", False
    natural = measure_text_width(text, font, font_size)
    if natural <= max_width:
        return text, False
    ellipsis_w = measure_text_width(_ELLIPSIS, font, font_size)
    if ellipsis_w >= max_width:
        return _ELLIPSIS, True
    target = max_width - ellipsis_w
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if measure_text_width(text[:mid], font, font_size) <= target:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + _ELLIPSIS, True


def _resolve_font_size(
    *,
    text: str,
    font: Font,
    style_size: float,
    max_width: float | None,
    max_height: float | None,
    min_font_size: float,
) -> float:
    """Largest font size in ``[min_font_size, style_size]`` that fits.

    "Fits" means the rendered text's natural width is at most
    ``max_width`` (when set) and its rendered height is at most
    ``max_height`` (when set). When both budgets are met at the
    style's natural size, returns ``style_size``. When neither is
    set, returns ``style_size`` directly.
    """
    if not text:
        return min_font_size
    target = style_size
    if max_height is not None:
        natural_h = measure_text_height(text, font, style_size)
        if natural_h > max_height and natural_h > 0:
            target = min(target, style_size * (max_height / natural_h))
    if max_width is not None:
        natural_w = measure_text_width(text, font, style_size)
        if natural_w > max_width and natural_w > 0:
            target = min(target, style_size * (max_width / natural_w))
    return max(target, min_font_size)


# ---------------------------------------------------------------------------
# Composable
# ---------------------------------------------------------------------------


@Composable(use_context=True)
def AdjustableText(
    ctx,
    *,
    text: str,
    style: TextStyle,
    max_width: float | None = None,
    max_height: float | None = None,
    min_font_size: float | None = None,
    text_anchor: str = "start",
    dominant_baseline: str = "text-before-edge",
    opacity: float = 1.0,
    letter_spacing: float | None = None,
):
    """Render ``text`` as big as it fits inside the given budget.

    The resolution runs in two passes:

    1. **Shrink pass.** Pick the largest font size in
       ``[min_font_size, style.size]`` such that the rendered text
       fits within ``max_width`` (when supplied) and ``max_height``
       (when supplied). When ``min_font_size`` is omitted (or
       coincides with ``style.size``) there's no headroom to
       shrink — the composable goes straight to the truncate pass.
    2. **Truncate pass.** If ``max_width`` is set and the rendered
       text at the resolved font size still exceeds it, trim with
       an ``…`` ellipsis via PIL-accurate measurement.

    ``max_width`` does double duty: it's the budget for shrink/
    truncate AND the slot width the bbox occupies. When set, the
    reported ``size.width`` equals ``max_width`` and ``text_anchor``
    controls where inside that slot the text paints — passing
    ``text_anchor="end"`` with ``max_width`` gives right-aligned-
    in-slot behaviour with no extra layout wrapping. When
    ``max_width`` is ``None`` the bbox snug-fits the rendered text.

    ``min_font_size`` is silently clamped to ``style.size`` so a
    caller passing a higher floor doesn't accidentally enlarge the
    text. Empty text yields a zero-sized no-op so hosts don't need
    to special-case "no string here".
    """
    if not text:
        size = Size(0.0, 0.0)

        def _noop(d, origin):
            del d, origin

        return MetricsComponent(
            size=size,
            draw_fn=_noop,
            metrics=AdjustableTextMetrics(
                font_size=0.0,
                rendered_text="",
                truncated=False,
                baseline=0.0,
                meanline=0.0,
                ascender_line=0.0,
            ),
        )

    # Clamp the floor to the ceiling so a misuse doesn't enlarge the
    # text past the requested style.
    floor = min(min_font_size if min_font_size is not None else style.size, style.size)

    font_size = _resolve_font_size(
        text=text,
        font=style.font,
        style_size=style.size,
        max_width=max_width,
        max_height=max_height,
        min_font_size=floor,
    )

    if max_width is not None:
        rendered_text, truncated = _truncate_to_fit(text, style.font, font_size, max_width)
    else:
        rendered_text, truncated = text, False

    # Register the actually-painted characters with the active
    # font-usage collector so :func:`render` can subset embedded
    # fonts to just the glyphs the document paints. No-op outside
    # a render pass (e.g. tests that build composables in
    # isolation).
    register_font_usage(style.font, rendered_text)

    rendered_w = measure_text_width(rendered_text, style.font, font_size)
    rendered_h = measure_text_height(rendered_text, style.font, font_size)
    baseline, meanline, ascender_line = _reference_lines(rendered_text, style.font, font_size)
    # ``max_width`` is the slot the parent allocates — when supplied,
    # the bbox occupies that full width and ``text_anchor`` controls
    # where inside the bbox the text paints. When omitted, the bbox
    # snug-fits the rendered text.
    bbox_w = max_width if max_width is not None else rendered_w
    size = Size(bbox_w, rendered_h)

    use_system_fonts = ctx.config.output.style.use_system_fonts
    family = style.font.get_system_font_family() if use_system_fonts else style.font.value

    # Y-offset within the bbox depends on which baseline the SVG
    # renderer anchors to. The default ``text-before-edge`` paints
    # the bbox top at ``y``; ``text-after-edge`` paints the bbox
    # bottom at ``y``; ``central``/``middle`` paints the visual
    # centre at ``y``. Map each to a y_offset so the painted glyphs
    # land inside the reported bbox regardless of which baseline
    # the parent picks.
    if dominant_baseline in ("text-after-edge", "alphabetic", "ideographic"):
        y_offset = rendered_h
    elif dominant_baseline in ("central", "middle"):
        y_offset = rendered_h / 2.0
    else:  # "text-before-edge", "hanging", default
        y_offset = 0.0

    # X-offset within the bbox depends on text_anchor. ``start`` puts
    # the bbox left at ``x``; ``end`` puts the bbox right at ``x``;
    # ``middle`` puts the bbox centre at ``x``. When ``max_width`` is
    # set the bbox width is the full slot, so right-/centre-anchored
    # text lands at the slot's right/centre — a parent passing
    # ``text_anchor="end"`` with ``max_width`` gets right-aligned-in-
    # slot behaviour for free.
    if text_anchor == "end":
        x_offset = bbox_w
    elif text_anchor == "middle":
        x_offset = bbox_w / 2.0
    else:
        x_offset = 0.0

    def draw_at(d, origin: Point) -> None:
        # Single-style render — flat ``<text>`` element with one
        # font family, one fill, no tspans. Multi-format text (mixed
        # fonts, Nerd Font icon glyphs) is the next layer's concern;
        # this base layer paints a single style end-to-end.
        text_el = draw.Text(
            rendered_text,
            font_size=font_size,
            x=origin.x + x_offset,
            y=origin.y + y_offset,
            text_anchor=text_anchor,
            dominant_baseline=dominant_baseline,
            font_family=family,
            fill=style.color,
            opacity=opacity,
        )
        # ``letter_spacing`` and non-default ``font-weight`` are set as
        # post-build attributes since ``drawsvg.Text`` doesn't accept
        # them positionally; passing them via ``args`` keeps the
        # constructor call type-clean while still emitting the
        # attribute on the SVG element. Weight is omitted when it
        # matches the default 400 so we don't bloat the SVG with a
        # redundant attribute on every text element.
        if letter_spacing is not None:
            text_el.args["letter_spacing"] = letter_spacing
        if style.weight != 400:
            text_el.args["font-weight"] = str(style.weight)
        d.append(text_el)

    return MetricsComponent(
        size=size,
        draw_fn=draw_at,
        metrics=AdjustableTextMetrics(
            font_size=font_size,
            rendered_text=rendered_text,
            truncated=truncated,
            baseline=baseline,
            meanline=meanline,
            ascender_line=ascender_line,
        ),
    )


__all__ = ["AdjustableText", "AdjustableTextMetrics"]

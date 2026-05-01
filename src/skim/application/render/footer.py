# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reusable footer component for keymap images.

The footer renders a right-aligned text line (typically the copyright
notice). Hosts can pass an optional ``max_height`` that caps the
rendered text height — used by the standalone special-keys images so
the copyright never reads taller than the ``MACROS`` / ``TAP-DANCE``
section title above the body.

This module exposes the rendering pipeline both as a composable
(:func:`Footer`) and as legacy imperative helpers
(:func:`append_footer` and :func:`footer_layout_height`) for call
sites that haven't yet been ported to the composable API.
"""

from dataclasses import dataclass

import drawsvg as draw

from .adjustable_text import AdjustableText
from .composable import Composable
from .primitives import DrawFn, Point, Row, Size, Spacer
from .text import Font

# Floor on the footer font size when shrinking under ``max_height`` so
# tight ceilings still produce something legible (and never produce a
# degenerate ``0``).
_MIN_FONT_SIZE = 6.0

# Opacity used when stamping the copyright string — matches the
# previous inline rendering in the per-layer / overview images.
_FOOTER_OPACITY = 0.6


# ---------------------------------------------------------------------------
# Backward-compatible result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FooterRenderResult:
    """Outcome of an :func:`append_footer` render."""

    height: float
    """Rendered glyph bbox height (``0`` when no text was supplied)."""

    font_size: float
    """Final font size used (``0`` when no text was supplied)."""


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------


def _measure_text_size(text: str, font_size: float) -> Size:
    """Rendered glyph-bbox of ``text`` at ``font_size`` (in SVG units).

    Mirrors :func:`header._title_rendered_size` so footer and header
    use the same metric — ``getbbox()`` returns the tight bounding box
    that the SVG renderer paints, regardless of font ascent / descent
    slack.
    """
    if not text:
        return Size(0.0, 0.0)
    pil_font = Font.FINGER_KEY.load(int(round(max(font_size, 1.0))))
    left, top, right, bottom = pil_font.getbbox(text)
    return Size(width=float(right - left), height=float(bottom - top))


def _resolve_font_size(
    text: str,
    font_max_size: float,
    max_height: float | None,
) -> float:
    """Return the font size that fits ``text`` within ``max_height``.

    When ``max_height`` is ``None`` or the natural rendered text
    already fits below it, ``font_max_size`` is returned as-is.
    """
    if not text:
        return 0.0
    if max_height is None:
        return font_max_size
    natural_h = _measure_text_size(text, font_max_size).height
    if natural_h <= max_height or natural_h <= 0:
        return font_max_size
    scaled = font_max_size * (max_height / natural_h)
    return max(_MIN_FONT_SIZE, scaled)


# ---------------------------------------------------------------------------
# Composable
# ---------------------------------------------------------------------------


def _footer_size_and_draw(
    text: str,
    *,
    font_max_size: float,
    color: str,
    family: str,
    max_height: float | None,
    max_width: float | None = None,
) -> tuple[Size, DrawFn]:
    """Pure helper that builds the size + draw closure for a footer line.

    Shared between the :func:`Footer` composable (ctx-aware) and the
    legacy :func:`append_footer` imperative wrapper so both produce
    pixel-identical output. Empty ``text`` yields a zero-sized no-op
    element so hosts don't need to special-case "no copyright".

    When ``max_width`` is given the returned size's ``width`` matches
    it (the element fills the slot) and the text is right-anchored
    at that slot's right edge — Footer is conceptually always
    right-aligned, so it owns its alignment instead of asking a
    parent ``Align`` wrapper to do it. When ``max_width`` is
    ``None`` the size matches the text's natural bbox.
    """
    if not text:
        return Size(0.0, 0.0), lambda _d, _o: None

    font_size = _resolve_font_size(text, font_max_size, max_height)
    text_size = _measure_text_size(text, font_size)
    size = Size(max_width if max_width is not None else text_size.width, text_size.height)

    def draw_at(d, origin):
        # Text right-anchored at the slot's right edge with
        # ``after-edge`` baseline so the glyph bbox sits flush at the
        # bottom-right corner of the reported size.
        d.append(
            draw.Text(
                text,
                font_size=font_size,
                x=origin.x + size.width,
                y=origin.y + size.height,
                text_anchor="end",
                dominant_baseline="text-after-edge",
                font_family=family,
                fill=color,
                opacity=_FOOTER_OPACITY,
            )
        )

    return size, draw_at


@Composable(use_context=True)
def Footer(
    ctx,
    *,
    text: str,
    max_width: float | None = None,
    max_height: float | None = None,
):
    """A right-aligned line of footer text (typically a copyright notice).

    Delegates the text-fitting concern (shrink under ``max_height``,
    truncate under ``max_width``) to :func:`AdjustableText`. Owns
    only the slot-fill + right-align layout: when ``max_width`` is
    set the returned component's width fills the slot exactly and
    the text right-anchors against the right edge.

    Reads typography from ``ctx.theme.typography.copyright``. Empty
    ``text`` yields a zero-sized noop so hosts don't need to
    special-case "no copyright". ``max_height`` shrinks the font
    when the natural text would otherwise be taller; the floor on
    that shrink is the local ``_MIN_FONT_SIZE`` constant.
    """
    if not text:
        return Spacer()

    text_el = AdjustableText(
        text=text,
        style=ctx.theme.typography.copyright,
        max_width=max_width,
        max_height=max_height,
        min_font_size=_MIN_FONT_SIZE,
        text_anchor="end",
        dominant_baseline="text-after-edge",
        opacity=_FOOTER_OPACITY,
    )
    if max_width is None:
        return text_el

    # Right-align inside the slot — pad the leading edge with a
    # ``Spacer`` so the row reports ``max_width`` as its total width
    # and the painted text right-anchors at the slot's right edge.
    leading = max(0.0, max_width - text_el.size.width)
    return Row([Spacer(width=leading), text_el], gap=0.0, align="end")


# ---------------------------------------------------------------------------
# Backward-compatible imperative helpers
# ---------------------------------------------------------------------------


def footer_layout_height(
    text: str,
    font_max_size: float,
    max_height: float | None = None,
) -> float:
    """Predicted footer height for use in canvas-height calculations.

    Independent of any active :class:`RenderContext` so the legacy
    per-layer / overview imperative paths can call it before they're
    migrated to a context-aware pipeline.
    """
    if not text:
        return 0.0
    size, _ = _footer_size_and_draw(
        text,
        font_max_size=font_max_size,
        color="#000",
        family=Font.FINGER_KEY.value,
        max_height=max_height,
    )
    return size.height


def append_footer(
    d: draw.Drawing,
    *,
    canvas_w: float,
    canvas_h: float,
    padding: float,
    bottom_inset: float,
    text: str,
    text_color: str,
    font_max_size: float,
    use_system_fonts: bool,
    max_height: float | None = None,
) -> FooterRenderResult:
    """Imperative wrapper around :func:`_footer_size_and_draw`.

    Built directly from the pure helper (not the :func:`Footer`
    composable) so call sites that haven't yet been migrated to a
    :class:`RenderContext`-aware pipeline can keep working without
    setting up a context first.
    """
    if not text:
        return FooterRenderResult(height=0.0, font_size=0.0)

    family = Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value
    size, draw_at = _footer_size_and_draw(
        text,
        font_max_size=font_max_size,
        color=text_color,
        family=family,
        max_height=max_height,
    )
    origin = Point(
        canvas_w - padding - size.width,
        canvas_h - bottom_inset - size.height,
    )
    draw_at(d, origin)

    final_font_size = _resolve_font_size(text, font_max_size, max_height)
    return FooterRenderResult(height=size.height, font_size=final_font_size)


__all__ = [
    "Footer",
    "FooterRenderResult",
    "append_footer",
    "footer_layout_height",
]

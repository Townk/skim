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
"""

from .adjustable_text import AdjustableText
from .composable import Composable

# Floor on the footer font size when shrinking under ``max_height`` so
# tight ceilings still produce something legible (and never produce a
# degenerate ``0``).
_MIN_FONT_SIZE = 6.0

# Opacity used when stamping the copyright string — matches the
# previous inline rendering in the per-layer / overview images.
_FOOTER_OPACITY = 0.6


@Composable(use_context=True)
def Footer(
    ctx,
    *,
    text: str,
    max_width: float | None = None,
    max_height: float | None = None,
):
    """A right-aligned line of footer text (typically a copyright notice).

    Thin wrapper around :func:`AdjustableText` that pins the
    copyright typography preset and the right-anchored / after-edge
    layout. When ``max_width`` is set the bbox fills the slot and
    the text right-anchors at its right edge — no extra layout
    wrapping needed since :func:`AdjustableText` handles the slot
    fill internally. Empty ``text`` yields a zero-sized noop via
    :func:`AdjustableText`. ``max_height`` shrinks the font when
    the natural text would otherwise be taller; the floor is the
    local ``_MIN_FONT_SIZE`` constant.
    """
    return AdjustableText(
        text=text,
        style=ctx.theme.typography.copyright,
        max_width=max_width,
        max_height=max_height,
        min_font_size=_MIN_FONT_SIZE,
        text_anchor="end",
        dominant_baseline="text-after-edge",
        opacity=_FOOTER_OPACITY,
    )


__all__ = ["Footer"]

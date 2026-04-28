# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""On-key marks for macro and tap-dance keys.

This module provides drawsvg primitives that paint a small accent-coloured
mark on a host key — a triangular fold cut from one corner for rectangular
and curved-bottom hosts (``MacroTapDanceCorner``), and a curved wedge in
the upper-right of the home circle (``MacroTapDanceCircleBadge``, added in
Task 3.2). Both helpers paint only the mark; the host's base shape, edge
band, and label are owned by the caller.

Geometry references the design exploration:
- Satellite/double-south/thumb keys: ``docs/design/keymap.jsx:260-301``.
- Home circle wedge:                ``docs/design/CenterKeyBadge.svg``.
"""

from typing import Literal

import drawsvg as draw

Corner = Literal["tl", "tr", "bl", "br"]
"""Corner identifier — top-left, top-right, bottom-left, bottom-right."""


SATELLITE_FOLD_CORNER: dict[str, Corner] = {
    "bottom": "tr",  # north (top) key — edge band is on the bottom
    "left":   "br",  # east  (right) key — edge band is on the left
    "top":    "bl",  # south (bottom) key — edge band is on the top
    "right":  "tl",  # west  (left) key — edge band is on the right
}
"""Fold corner per ``edgeSide`` — clockwise rotation around the cluster home.

The fold always points "outward" from the home circle: north → top-right,
east → bottom-right, south → bottom-left, west → top-left.
"""


_SATELLITE_FOLD_LEG = 22.0
"""Default fold leg length for 54×54 satellite keys."""

_FOLD_LEG_CAP = 26.0
"""Maximum fold leg length, regardless of host size."""

_FOLD_LEG_RATIO = 0.42
"""Fold leg as a fraction of ``min(w, h)`` for non-satellite hosts."""


class MacroTapDanceCorner(draw.Group):
    """Triangular accent fold clipped to one corner of a rounded-rect host.

    The triangle is painted with the accent fill and clipped to the host's
    rounded outer shape so it never spills past a rounded corner. The
    helper is responsible for the triangle only — the host's base rect,
    edge band, and label are drawn separately by the caller.

    Attributes:
        fold_leg: Computed triangle leg length (px).
    """

    fold_leg: float

    def __init__(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        r: float,
        corner: Corner,
        fill: str,
        **kwargs,
    ):
        """Build the fold group.

        Args:
            x: Host rect's top-left x in the parent SVG coordinate system.
            y: Host rect's top-left y.
            w: Host rect's width.
            h: Host rect's height.
            r: Host rect's corner radius (used for the clip path so the
                fold hugs the host's rounded outer corner).
            corner: Which of the four corners the fold is cut from.
            fill: Hex colour of the fold triangle (the accent fill).
            **kwargs: Forwarded to ``drawsvg.Group``.
        """
        super().__init__(**kwargs)

        # Fold leg: 22 for standard 54×54 keys; otherwise min(w,h)*0.42 capped.
        if abs(w - 54.0) < 0.5 and abs(h - 54.0) < 0.5:
            fold = _SATELLITE_FOLD_LEG
        else:
            fold = min(min(w, h) * _FOLD_LEG_RATIO, _FOLD_LEG_CAP)
        self.fold_leg = fold

        # Triangle path — coordinates depend on which corner.
        if corner == "tl":
            tri_path = (
                f"M {x} {y} L {x + fold} {y} L {x} {y + fold} Z"
            )
        elif corner == "tr":
            tri_path = (
                f"M {x + w - fold} {y} L {x + w} {y} L {x + w} {y + fold} Z"
            )
        elif corner == "br":
            tri_path = (
                f"M {x + w} {y + h - fold} L {x + w} {y + h} L {x + w - fold} {y + h} Z"
            )
        else:  # "bl"
            tri_path = (
                f"M {x} {y + h - fold} L {x + fold} {y + h} L {x} {y + h} Z"
            )

        # Clip the triangle to the host's rounded shape so it does not poke
        # past a rounded outer corner.
        clip_id = f"mtd-corner-clip-{int(round(x * 100))}-{int(round(y * 100))}-{corner}"
        clip_path = draw.ClipPath(id=clip_id)
        clip_path.append(
            draw.Rectangle(x=x, y=y, width=w, height=h, rx=r, ry=r)
        )
        self.append(clip_path)

        clipped = draw.Group(clip_path=f"url(#{clip_id})")
        clipped.append(draw.Path(d=tri_path, fill=fill))
        self.append(clipped)

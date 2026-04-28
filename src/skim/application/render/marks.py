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


# --- Home-circle wedge badge ------------------------------------------------

# The wedge geometry is taken from docs/design/CenterKeyBadge.svg. That SVG
# lays the home circle at centre (450, 450) and radius 450 in its own
# coordinate system (after collapsing the two outer transforms). The path
# below is the wedge expressed on a unit circle (centre origin, radius 1)
# so a renderer can scale it to any home-circle size.
#
# Mapping from SVG path coords (px, py) to normalised (nx, ny):
#   nx = (px * 1.090909 + 11.181818 - 825 - 450) / 450
#   ny = (py * 1.090909 - 988.363636 - 1200 - 450) / 450
#
# Path elements (extracted from the source SVG, then normalised by the above):
#   M  1571,    2418.5
#   L  1557.403, 2418.5
#   C  1510.596, 2418.5  1469.748, 2386.761  1458.182, 2341.406
#   C  1430.283, 2232.594 1344.677, 2146.911 1235.913, 2118.89
#   C  1190.366, 2107.223 1158.511, 2066.18  1158.511, 2019.163
#   C  1158.5,   2011.156 1158.5,   2006     1158.5,   2006
#   C  1386.317, 2006     1571,     2190.683 1571,     2418.5
#   Z


def _norm(px: float, py: float) -> tuple[float, float]:
    return (
        (px * 1.090909 + 11.181818 - 825.0 - 450.0) / 450.0,
        (py * 1.090909 - 988.363636 - 1200.0 - 450.0) / 450.0,
    )


_BADGE_PATH_PTS_NORMALISED: list[tuple[str, list[tuple[float, float]]]] = [
    ("M", [_norm(1571, 2418.5)]),
    ("L", [_norm(1557.403, 2418.5)]),
    ("C", [_norm(1510.596, 2418.5), _norm(1469.748, 2386.761), _norm(1458.182, 2341.406)]),
    ("C", [_norm(1430.283, 2232.594), _norm(1344.677, 2146.911), _norm(1235.913, 2118.89)]),
    ("C", [_norm(1190.366, 2107.223), _norm(1158.511, 2066.18), _norm(1158.511, 2019.163)]),
    ("C", [_norm(1158.5, 2011.156), _norm(1158.5, 2006), _norm(1158.5, 2006)]),
    ("C", [_norm(1386.317, 2006), _norm(1571, 2190.683), _norm(1571, 2418.5)]),
    ("Z", []),
]
"""Wedge path in unit-circle space — list of (command, point list) tuples."""


_NORMALISED_BADGE_RIGHT_TIP: tuple[float, float] = _BADGE_PATH_PTS_NORMALISED[0][1][0]
"""The first M point — right-most tip of the wedge — on the unit circle."""


def _badge_path_d(cx: float, cy: float, r: float) -> str:
    """Build the SVG ``d`` attribute for a wedge sized to ``r`` and centred
    at ``(cx, cy)``."""
    parts: list[str] = []
    for cmd, pts in _BADGE_PATH_PTS_NORMALISED:
        if cmd == "Z":
            parts.append("Z")
            continue
        coords = " ".join(f"{cx + nx * r} {cy + ny * r}" for nx, ny in pts)
        parts.append(f"{cmd} {coords}")
    return " ".join(parts)


class MacroTapDanceCircleBadge(draw.Group):
    """Curved wedge badge in the NE quadrant of a home circle.

    The wedge geometry is taken from ``docs/design/CenterKeyBadge.svg`` and
    re-scaled to the renderer's home-circle radius. The host circle and any
    centred glyph are drawn separately by the caller — this helper paints
    only the wedge.
    """

    def __init__(self, cx: float, cy: float, r: float, fill: str, **kwargs):
        """Build the badge group.

        Args:
            cx: Home-circle centre x in the parent SVG coordinate system.
            cy: Home-circle centre y.
            r: Home-circle radius.
            fill: Hex colour of the wedge (the accent fill).
            **kwargs: Forwarded to ``drawsvg.Group``.
        """
        super().__init__(**kwargs)
        self.append(draw.Path(d=_badge_path_d(cx, cy, r), fill=fill))

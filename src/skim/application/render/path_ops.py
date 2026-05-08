# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Boolean operations on SVG path geometry.

Wraps :mod:`pathops` (Python bindings for Skia's PathOps) so callers can
do ``subject minus holes`` style subtraction on SVG path d-strings
without writing the parse / convert / pen plumbing each time. Skia
PathOps is the same path-Boolean engine Chrome and Flutter use; results
are exact (not polygon-approximated).

SVG arcs (``A`` commands) round-trip through Skia as cubic Béziers
since Skia stores quadratic / cubic / conic / line verbs internally.
The output is geometrically identical; the path d-string just ends
up using ``C`` commands where the input had ``A`` commands. Browsers
and rasterisers render the two interchangeably.
"""

from __future__ import annotations

import pathops
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.svgLib.path.parser import parse_path


def _to_skia(d: str) -> pathops.Path:
    path = pathops.Path()
    parse_path(d, path.getPen())
    return path


def _to_svg_d(path: pathops.Path) -> str:
    pen = SVGPathPen(None)
    path.draw(pen)
    return pen.getCommands()


def subtract(subject_d: str, *hole_ds: str) -> str:
    """Return ``subject_d`` with each ``hole`` removed via Skia PathOps.

    The result is the geometric set ``subject \\ (hole_1 ∪ hole_2 ∪
    …)`` — pure subtraction, with intersections handled correctly even
    when a hole extends past the subject's outline. The returned
    d-string uses ``M / L / C / Z`` (and ``Q`` if Skia chose
    quadratics); arcs are converted to cubic Béziers along the way.

    Empty ``hole_ds`` returns ``subject_d`` unchanged (after a
    round-trip through Skia, so the d-string may be reformatted but
    the geometry is identical).
    """
    subject = _to_skia(subject_d)
    if not hole_ds:
        return _to_svg_d(subject)
    result = subject
    for hd in hole_ds:
        result = pathops.op(result, _to_skia(hd), pathops.PathOp.DIFFERENCE)
    return _to_svg_d(result)

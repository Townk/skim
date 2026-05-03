# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Overview image — public entry point + shared header dimensions.

The overview render itself is fully on the composable framework:
:func:`draw_overview` is a thin wrapper over
:func:`keymap_overview.draw_overview_v2`. The legacy imperative
pipeline that used to live here has retired.

This module also exposes :func:`compute_header_dims`, used by
:meth:`render_context.Theme.resolve` to derive the title / copyright
font sizes that flow into every image — so per-layer, overview, and
special-keys renders share the same header typography. The helper
still goes through :class:`OverviewLayout` for now; folding its math
into the new composable pipeline is a follow-up.
"""

from dataclasses import dataclass

import drawsvg as draw

from skim.data import KeycodeMappings, SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey

from .geometry import AspectRatio
from .layout import KeymapLayoutMetrics
from .overview_layout import (
    _LOGO_WIDTH_TO_BADGE_WIDTH,
    BadgeDimensions,
    OverviewLayout,
    _badge_padding_left,
    _badge_padding_right,
    _outer_padding,
)
from .text import Font

_LOGO_ASPECT_RATIO = AspectRatio.from_dimensions(width=2333.333, height=458.333, precision=2)

# Finger cluster key proportions — match :func:`KeymapOverview` and
# :class:`FingerCluster` so the badge math here lines up with the
# composable rendering.
_OUTER_KEY_WIDTH_PROPORTION = 0.328

# Badge font size as a ratio of badge height.
_BADGE_FONT_SIZE_RATIO = 0.45

# Title font size relative to the badge font size.
_TITLE_FONT_SIZE_RATIO_OF_BADGE = 1.8

# Preliminary badge dimensions used as a seed for the OverviewLayout
# iteration (the real badge is recomputed once the cluster width is
# known). At the canonical 1600-unit width these reproduce the
# original 200/40/8 px values.
_PRELIM_BADGE_WIDTH_RATIO = 200 / 1600
_PRELIM_BADGE_HEIGHT_RATIO = 40 / 1600
_PRELIM_BADGE_RADIUS_RATIO = 8 / 1600


def _prelim_badge_dimensions(doc_width: float) -> BadgeDimensions:
    """Seed badge dimensions for the preliminary OverviewLayout pass."""
    return BadgeDimensions(
        width=doc_width * _PRELIM_BADGE_WIDTH_RATIO,
        height=doc_width * _PRELIM_BADGE_HEIGHT_RATIO,
        border_radius=doc_width * _PRELIM_BADGE_RADIUS_RATIO,
    )


def _badge_text(qmk_idx: int, name: str) -> str:
    """Compose a layer badge label, deduping the redundant ``Layer N`` case."""
    upper = name.upper()
    if upper == f"LAYER {qmk_idx}":
        return upper
    return f"{qmk_idx} {upper}"


def _compute_badge_dims(
    config: SkimConfig,
    render_layers: list[tuple[int, int]],
    finger_cluster_width: float,
) -> BadgeDimensions:
    """Compute uniform badge dimensions.

    Mirrors what :func:`keymap_overview._compute_badge_dims` produces
    so the header dims read off the same badge geometry the overview
    body actually paints.
    """
    badge_height = finger_cluster_width * _OUTER_KEY_WIDTH_PROPORTION
    badge_texts: list[str] = [
        _badge_text(qmk_idx, config.keyboard.layers[pos].name) for pos, qmk_idx in render_layers
    ]
    badge_texts.append("THUMBS")
    badge_font_size = badge_height * _BADGE_FONT_SIZE_RATIO
    ref_size = 100
    pil_font = Font.FINGER_KEY.load(ref_size)
    max_text_width_at_ref = max(pil_font.getlength(t) for t in badge_texts) if badge_texts else 50.0
    max_text_width = max_text_width_at_ref * (badge_font_size / ref_size)

    doc_width = config.output.layout.width
    badge_width = _badge_padding_left(doc_width) + max_text_width + _badge_padding_right(doc_width)
    return BadgeDimensions(
        width=badge_width,
        height=badge_height,
        border_radius=badge_height * 0.2,
    )


@dataclass(frozen=True, slots=True)
class HeaderDims:
    """Shared typography and spacing between overview and per-layer images.

    Per-layer keymap images reuse these so their header (and footer)
    typography matches the overview verbatim.

    Attributes:
        title_font_size: Font size in SVG units for the layer/keymap title.
        logo_width: Rendered logo width in SVG units.
        logo_height: Rendered logo height in SVG units.
        outer_padding: Gap from the canvas edge to the header content,
            matching the overview's outer padding so both images breathe alike.
        gap_below_header: Vertical gap between the header bottom and the top
            of the cluster content.
        copyright_font_size: Font size in SVG units for the copyright footer.
    """

    title_font_size: float
    logo_width: float
    logo_height: float
    outer_padding: float
    gap_below_header: float
    copyright_font_size: float


def compute_header_dims(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> HeaderDims:
    """Compute the title font size and logo dimensions used by the overview.

    Returned values flow into :class:`render_context.Theme` so per-layer,
    overview, and special-keys images all paint header typography at
    the same size.
    """
    render_layers: list[tuple[int, int]] = [
        (pos, layer_cfg.index)
        for pos, layer_cfg in enumerate(config.keyboard.layers)
        if layer_cfg.index in keymap.layers
    ]
    prelim_badge = _prelim_badge_dimensions(config.output.layout.width)
    prelim_layout = OverviewLayout(config, prelim_badge)
    badge_dims = _compute_badge_dims(config, render_layers, prelim_layout.finger_cluster_width)
    layout = OverviewLayout(config, badge_dims, routing_column_count=0)

    badge_h = layout.outer_key_size
    badge_font_size = badge_h * _BADGE_FONT_SIZE_RATIO
    title_font_size = badge_font_size * _TITLE_FONT_SIZE_RATIO_OF_BADGE
    logo_width = badge_dims.width * _LOGO_WIDTH_TO_BADGE_WIDTH
    logo_height = _LOGO_ASPECT_RATIO.height_from_width(logo_width)
    base_metrics = KeymapLayoutMetrics.from_config(config)
    outer_padding = _outer_padding(base_metrics)
    # Overview uses ``row_gap = finger_cluster_width * outer_key_proportion`` —
    # one N-key width — for the gap below the header and between rows. Reuse
    # it here so per-layer images have the same breathing room after the header.
    gap_below_header = layout.finger_cluster_width * _OUTER_KEY_WIDTH_PROPORTION
    return HeaderDims(
        title_font_size=title_font_size,
        logo_width=logo_width,
        logo_height=logo_height,
        outer_padding=outer_padding,
        gap_below_header=gap_below_header,
        copyright_font_size=badge_font_size,
    )


def draw_overview(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    raw_keymap: SvalboardKeymap[str] | None = None,
    keycode_mappings: KeycodeMappings | None = None,
) -> draw.Drawing:
    """Generate the full overview SVG image for a multi-layer keymap.

    Thin wrapper over :func:`keymap_overview.draw_overview_v2`. The
    legacy imperative pipeline retired with the composable migration.
    """
    from .keymap_overview import draw_overview_v2

    return draw_overview_v2(
        config,
        keymap,
        raw_keymap=raw_keymap,
        keycode_mappings=keycode_mappings,
    )


__all__ = [
    "HeaderDims",
    "compute_header_dims",
    "draw_overview",
]

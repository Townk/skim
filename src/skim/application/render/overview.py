# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Overview image rendering for multi-layer keymap visualization.

Generates a table-like overview SVG showing all keymap layers:
- Header row: Svalboard logo (col 1) + layout title (col 2)
- Layer rows: colored badge with "N NAME" (col 1) + 8 finger clusters (col 2)
- Thumb row: THUMBS badge (col 1) + thumb clusters for layer 0 (col 2)
- Dotted connector lines from layer indicator circles to target layer rows
"""

from collections.abc import Callable

import drawsvg as draw

from skim.assets import ASSETS
from skim.data import Palette, SkimConfig, SvalboardKeymap
from skim.domain import KeyboardSide, SvalboardTargetKey

from .components import FingerClusterComponent, ThumbClusterComponent
from .context import RenderContext
from .geometry import AspectRatio
from .indicators import (
    _THUMB_KEY_HEIGHT_RATIOS,
    _THUMB_KEY_NAMES,
    LayerIndicator,
    _thumb_cluster_offset,
)
from .layout import Boundary, KeymapLayoutMetrics
from .overview_layout import (
    _BADGE_PADDING_LEFT,
    _BADGE_PADDING_RIGHT,
    BadgeDimensions,
    OverviewLayout,
)
from .text import Font

_LOGO_ASPECT_RATIO = AspectRatio.from_dimensions(width=2333.333, height=458.333, precision=2)
_FINGER_CLUSTERS_PER_SIDE = 4
_CONNECTOR_ROUTING_MARGIN = 12.0

# Finger cluster key proportions (same as FingerClusterComponent)
_OUTER_KEY_WIDTH_PROPORTION = 0.328

# Badge font size as a ratio of badge height
_BADGE_FONT_SIZE_RATIO = 0.45


def _compute_badge_dims(
    config: SkimConfig,
    render_layers: list[tuple[int, int]],
    finger_cluster_width: float,
) -> BadgeDimensions:
    """Compute uniform badge dimensions.

    Height matches the E/W key size in the overview finger cluster.
    Width = 15px padding + widest badge text + 30px padding.
    """
    # Badge height = E/W key height = outer_key proportion * cluster_width
    badge_height = finger_cluster_width * _OUTER_KEY_WIDTH_PROPORTION

    # Build all badge texts to find the widest
    badge_texts: list[str] = []
    for pos, qmk_idx in render_layers:
        name = config.keyboard.layers[pos].name.upper()
        badge_texts.append(f"{qmk_idx} {name}")
    badge_texts.append("THUMBS")

    # Measure text width using PIL font for accuracy.
    # PIL font sizes map to SVG units approximately 1:1 when the SVG uses
    # the same coordinate scale, but we need to measure at the actual size
    # that will be used in the SVG. Use a high-res measurement then scale.
    badge_font_size = badge_height * _BADGE_FONT_SIZE_RATIO
    try:
        from .text import Font as SkimFont

        # Measure at a large reference size then scale proportionally
        ref_size = 100
        pil_font = SkimFont.FINGER_KEY.load(ref_size)
        max_text_width_at_ref = (
            max(pil_font.getlength(t) for t in badge_texts) if badge_texts else 50
        )
        max_text_width = max_text_width_at_ref * (badge_font_size / ref_size)
    except Exception:
        char_width = badge_font_size * 0.65
        max_text_width = max(len(t) * char_width for t in badge_texts) if badge_texts else 50

    badge_width = _BADGE_PADDING_LEFT + max_text_width + _BADGE_PADDING_RIGHT
    border_radius = badge_height * 0.2

    return BadgeDimensions(
        width=badge_width,
        height=badge_height,
        border_radius=border_radius,
    )


_IndicatorInfo = tuple[float, float, float, int, str, KeyboardSide]
"""(abs_cx, abs_cy, circle_radius, target_layer_idx, key_name, side)"""


# First-segment escape direction per thumb key name and side.
# "UP" = vertical up, "DOWN" = vertical down, "RIGHT" = horizontal right.
_THUMB_ESCAPE_DIRECTIONS: dict[tuple[str, KeyboardSide], str] = {
    # Left side
    ("pad_key", KeyboardSide.LEFT): "UP",
    ("nail_key", KeyboardSide.LEFT): "UP",
    ("up_key", KeyboardSide.LEFT): "DOWN",
    ("knuckle_key", KeyboardSide.LEFT): "DOWN",
    ("down_key", KeyboardSide.LEFT): "DOWN",
    ("double_down_key", KeyboardSide.LEFT): "UP",
    # Right side
    ("pad_key", KeyboardSide.RIGHT): "RIGHT",
    ("nail_key", KeyboardSide.RIGHT): "UP",
    ("up_key", KeyboardSide.RIGHT): "RIGHT",
    ("knuckle_key", KeyboardSide.RIGHT): "DOWN",
    ("down_key", KeyboardSide.RIGHT): "RIGHT",
    ("double_down_key", KeyboardSide.RIGHT): "RIGHT",
}


def _collect_finger_indicators(
    clusters: list[list[FingerClusterComponent]],
    keymap: SvalboardKeymap[SvalboardTargetKey],
    row_to_layer: list[tuple[int, int]],
) -> list[_IndicatorInfo]:
    """Collect indicator circle positions from finger clusters.

    Currently returns an empty list — finger cluster connector routing
    is not yet implemented (exception case requiring special handling).
    """
    return []


def _collect_thumb_indicators(
    left_thumb: ThumbClusterComponent,
    right_thumb: ThumbClusterComponent,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    config: SkimConfig,
) -> list[_IndicatorInfo]:
    """Collect indicator circle positions and directions from thumb clusters."""
    results: list[_IndicatorInfo] = []
    first_qmk_idx = config.keyboard.layers[0].index if config.keyboard.layers else 0
    if first_qmk_idx not in keymap.layers:
        return results
    layer0 = keymap.layers[first_qmk_idx]

    for thumb_comp, thumb_data, side in [
        (left_thumb, layer0.left.thumb, KeyboardSide.LEFT),
        (right_thumb, layer0.right.thumb, KeyboardSide.RIGHT),
    ]:
        metrics = thumb_comp._layout.metrics
        palette = thumb_comp._render_context.palette
        down_metrics = metrics.down_key
        circle_diameter = down_metrics.width * 0.4
        gap = down_metrics.width * 0.18

        for key_name in _THUMB_KEY_NAMES:
            key: SvalboardTargetKey = getattr(thumb_data, key_name)
            if key.layer_switch is None:
                continue

            layout_b = getattr(metrics, key_name)
            offset_dir, conn_type = _thumb_cluster_offset(key_name, side)

            if key_name == "double_down_key":
                ref_y = down_metrics.pos.y
                ref_height = layout_b.width * _THUMB_KEY_HEIGHT_RATIOS.get("down_key", 1.0)
                connector_target_y = layout_b.pos.y
            elif key_name == "down_key":
                # Same fix as in indicators.py: position circle at
                # up_cy + (up_cy - pad_cy) instead of key center
                up_layout = metrics.up_key
                up_h = up_layout.width * _THUMB_KEY_HEIGHT_RATIOS["up_key"]
                up_cy = up_layout.pos.y + up_h / 2.0
                pad_layout = metrics.pad_key
                pad_h = pad_layout.width * _THUMB_KEY_HEIGHT_RATIOS["pad_key"]
                pad_cy = pad_layout.pos.y + pad_h / 2.0
                down_target_cy = up_cy + (up_cy - pad_cy)
                ref_height = layout_b.width * _THUMB_KEY_HEIGHT_RATIOS["down_key"]
                ref_y = down_target_cy - ref_height / 2.0
                connector_target_y = None
            else:
                ref_y = layout_b.pos.y
                ref_height = layout_b.width * _THUMB_KEY_HEIGHT_RATIOS.get(key_name, 1.0)
                connector_target_y = None

            indicator = LayerIndicator(
                key_x=layout_b.pos.x,
                key_y=ref_y,
                key_width=layout_b.width,
                key_height=ref_height,
                target_layer=key.layer_switch,
                palette=palette,
                circle_diameter=circle_diameter,
                gap=gap,
                offset_direction=offset_dir,
                connector_type=conn_type,
                connector_target_y=connector_target_y,
            )

            results.append(
                (
                    thumb_comp.x + indicator.circle_center_x,
                    thumb_comp.y + indicator.circle_center_y,
                    circle_diameter / 2.0,
                    key.layer_switch,
                    key_name,
                    side,
                )
            )

    return results


def _compute_connector_paths(
    all_indicators: list[_IndicatorInfo],
    all_row_bounds: list[tuple[float, float, float, float]],
    layer_to_row: dict[int, int],
    nk: float,
    ew_offset: float,
    max_cluster_right: float,
    padding: float,
    thumb_bbox: tuple[float, float, float, float] | None = None,
) -> list[tuple[list[tuple[float, float]], int]]:
    """Compute connector line paths without drawing them.

    Returns list of (points, target_layer) for each connector line.
    Points start from the circle perimeter, not center.
    UP/DOWN escapes clear the entire thumb cluster area so horizontal
    segments don't cross any thumb keys.
    """
    lines = [
        (cx, cy, r, tgt, kn, sd) for cx, cy, r, tgt, kn, sd in all_indicators if tgt in layer_to_row
    ]
    if not lines:
        return []

    # Lines end at cluster right edge + document padding
    end_x = max_cluster_right + padding

    # Thumb cluster top/bottom for clearance
    if thumb_bbox:
        _tb_x, tb_y, _tb_w, tb_h = thumb_bbox
        thumb_top = tb_y
        thumb_bottom = tb_y + tb_h
    else:
        # Fallback: use circle positions
        all_cy = [cy for _, cy, _, _, _, _ in lines]
        thumb_top = min(all_cy) - nk
        thumb_bottom = max(all_cy) + nk

    # Routing columns staggered to the right
    target_layers_used = sorted({ln[3] for ln in lines})
    base_routing_x = end_x + padding + nk
    routing_x_by_layer = {
        layer: base_routing_x + i * nk for i, layer in enumerate(target_layers_used)
    }

    # Y-stagger: group by escape direction, assign increasing multipliers
    up_indices: list[tuple[int, float]] = []
    down_indices: list[tuple[int, float]] = []
    right_indices: list[tuple[int, float]] = []

    for i, (cx, cy, _r, _tgt, key_name, side) in enumerate(lines):
        escape = _THUMB_ESCAPE_DIRECTIONS.get((key_name, side), "RIGHT")
        if escape == "UP":
            up_indices.append((i, cy))
        elif escape == "DOWN":
            down_indices.append((i, cy))
        else:
            right_indices.append((i, cx))

    # UP: highest circle (largest cy) = smallest rank (closest to thumb_top)
    up_indices.sort(key=lambda t: t[1], reverse=True)
    # DOWN: lowest circle (smallest cy) = smallest rank (closest to thumb_bottom)
    down_indices.sort(key=lambda t: t[1])
    # RIGHT: leftmost = smallest escape
    right_indices.sort(key=lambda t: t[1])

    escape_mult: dict[int, int] = {}
    for rank, (idx, _) in enumerate(up_indices):
        escape_mult[idx] = rank + 1
    for rank, (idx, _) in enumerate(down_indices):
        escape_mult[idx] = rank + 1
    for rank, (idx, _) in enumerate(right_indices):
        escape_mult[idx] = rank + 1

    # Pre-compute all UP escape Y values so RIGHT lines can avoid them
    up_escape_ys: set[int] = set()
    for idx, _ in up_indices:
        mult_val = escape_mult[idx]
        up_escape_ys.add(round(thumb_top - mult_val * nk))

    # Also pre-compute DOWN escape Y values
    down_escape_ys: set[int] = set()
    for idx, _ in down_indices:
        mult_val = escape_mult[idx]
        down_escape_ys.add(round(thumb_bottom + mult_val * nk))

    # All reserved horizontal Y values (UP + DOWN escapes)
    reserved_ys = up_escape_ys | down_escape_ys

    result: list[tuple[list[tuple[float, float]], int]] = []

    for line_idx, (cx, cy, radius, target_layer, key_name, side) in enumerate(lines):
        target_row_idx = layer_to_row[target_layer]
        _tgt_x, tgt_y, _tgt_w, _tgt_h = all_row_bounds[target_row_idx]
        target_ew_center_y = tgt_y + ew_offset + nk / 2.0
        routing_x = routing_x_by_layer[target_layer]
        mult = escape_mult.get(line_idx, 1)

        escape = _THUMB_ESCAPE_DIRECTIONS.get((key_name, side), "RIGHT")

        if escape == "UP":
            start_y = cy - radius - 4.0  # 4px gap from circle perimeter
            escape_y = thumb_top - mult * nk
            pts = [(cx, start_y), (cx, escape_y), (routing_x, escape_y)]
            if abs(escape_y - target_ew_center_y) > 1.0:
                pts.append((routing_x, target_ew_center_y))
            pts.append((end_x, target_ew_center_y))

        elif escape == "DOWN":
            start_y = cy + radius + 4.0  # 4px gap from circle perimeter
            escape_y = thumb_bottom + mult * nk
            pts = [(cx, start_y), (cx, escape_y), (routing_x, escape_y)]
            if abs(escape_y - target_ew_center_y) > 1.0:
                pts.append((routing_x, target_ew_center_y))
            pts.append((end_x, target_ew_center_y))

        else:  # RIGHT
            start_x = cx + radius + 4.0  # 4px gap from circle perimeter
            escape_x = max(start_x + mult * nk, max_cluster_right + nk)

            # Check if this line's horizontal Y (cy) collides with any
            # reserved UP/DOWN escape Y. If so, the line's horizontal
            # segment at the routing area would overlap — avoid by going
            # UP to the next free slot above thumb_top.
            rounded_cy = round(cy)
            collides = any(abs(rounded_cy - ry) < nk for ry in reserved_ys)

            if collides:
                # Find the next free Y above thumb_top
                slot = max(len(up_escape_ys), len(down_escape_ys)) + 1
                escape_y = thumb_top - slot * nk
                reserved_ys.add(round(escape_y))
                pts = [(start_x, cy), (escape_x, cy), (escape_x, escape_y), (routing_x, escape_y)]
                if abs(escape_y - target_ew_center_y) > 1.0:
                    pts.append((routing_x, target_ew_center_y))
                pts.append((end_x, target_ew_center_y))
            else:
                pts = [(start_x, cy), (escape_x, cy)]
                if escape_x < routing_x:
                    pts.append((routing_x, cy))
                final_x = max(escape_x, routing_x)
                if abs(cy - target_ew_center_y) > 1.0:
                    pts.append((final_x, target_ew_center_y))
                    pts.append((end_x, target_ew_center_y))

        result.append((pts, target_layer))

    return result


def _draw_connector_paths(
    d: draw.Drawing,
    paths: list[tuple[list[tuple[float, float]], int]],
    palette: "Palette",
    qmk_index_to_position: "Callable[[int], int | None]",
) -> None:
    """Draw pre-computed connector line paths as dotted SVG paths."""
    for pts, target_layer in paths:
        pos = qmk_index_to_position(target_layer)
        if pos is not None and 0 <= pos < len(palette.layers):
            stroke_color = palette.layers[pos][4]
        else:
            stroke_color = "#808080"

        path_d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"
        for px, py in pts[1:]:
            path_d += f" L {px:.2f} {py:.2f}"

        d.append(
            draw.Raw(
                f'<path d="{path_d}"'
                f' stroke="{stroke_color}"'
                f' stroke-width="2.5"'
                f' stroke-dasharray="1 4"'
                f' stroke-linecap="round"'
                f' fill="none"'
                f' opacity="0.7"'
                f"/>"
            )
        )


def _build_thumb_clusters(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
    layout: OverviewLayout,
    use_system_fonts: bool,
) -> tuple[ThumbClusterComponent | None, ThumbClusterComponent | None]:
    """Build thumb cluster components at the layout's current thumb position."""
    if not keymap.layers:
        return None, None
    first_qmk_idx = config.keyboard.layers[0].index if config.keyboard.layers else 0
    if first_qmk_idx not in keymap.layers:
        return None, None
    layer0 = keymap.layers[first_qmk_idx]
    palette = config.output.style.palette
    thumb_ctx = RenderContext(
        palette=palette,
        layer_index=0,
        has_double_south=config.keyboard.features.double_south,
        use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
        hold_symbol_position=config.output.style.hold_symbol_position,
        use_system_fonts=use_system_fonts,
        show_layer_indicators=config.output.style.show_layer_indicators,
        qmk_index_to_position=config.keyboard.qmk_index_to_position,
    )
    thumb_w = layout.thumb_cluster_width
    left_pos, right_pos = layout.thumb_cluster_positions()
    left_thumb = ThumbClusterComponent(
        keymap_cluster=layer0.left.thumb,
        side=KeyboardSide.LEFT,
        layout=Boundary(width=thumb_w, pos=left_pos),
        render_context=thumb_ctx,
    )
    right_thumb = ThumbClusterComponent(
        keymap_cluster=layer0.right.thumb,
        side=KeyboardSide.RIGHT,
        layout=Boundary(width=thumb_w, pos=right_pos),
        render_context=thumb_ctx,
    )
    return left_thumb, right_thumb


def draw_overview(
    config: SkimConfig,
    keymap: SvalboardKeymap[SvalboardTargetKey],
) -> draw.Drawing:
    """Generate the full overview SVG image for a multi-layer keymap."""
    num_layers = len(config.keyboard.layers)
    render_layers: list[tuple[int, int]] = []  # (config_position, qmk_index)
    for pos, layer_cfg in enumerate(config.keyboard.layers):
        if layer_cfg.index in keymap.layers:
            render_layers.append((pos, layer_cfg.index))
    render_layer_count = len(render_layers)

    use_system_fonts = config.output.style.use_system_fonts
    palette = config.output.style.palette
    base_metrics = KeymapLayoutMetrics.from_config(config)

    # --- Phase 1: Compute layout dimensions ---
    prelim_badge = BadgeDimensions(width=200, height=40, border_radius=8)
    prelim_layout = OverviewLayout(config, prelim_badge)
    badge_dims = _compute_badge_dims(config, render_layers, prelim_layout.finger_cluster_width)
    routing_column_count = render_layer_count  # worst case
    layout = OverviewLayout(config, badge_dims, routing_column_count)

    nk = layout.finger_cluster_width * _OUTER_KEY_WIDTH_PROPORTION
    ew_offset = layout.ew_key_y_offset
    row_to_layer = list(reversed(render_layers))  # list of (pos, qmk_idx) tuples
    layer_to_row = {qmk_idx: ri for ri, (_pos, qmk_idx) in enumerate(row_to_layer)}

    # --- Phase 2: Build thumb clusters at preliminary position, collect indicators,
    #     compute connector paths to find clearance needed ---
    connector_paths: list[tuple[list[tuple[float, float]], int]] = []
    if config.output.style.show_layer_indicators and keymap.layers:
        left_thumb_prelim, right_thumb_prelim = _build_thumb_clusters(
            config, keymap, layout, use_system_fonts
        )
        if left_thumb_prelim and right_thumb_prelim:
            all_row_bounds = [layout.layer_row_bounding_box(i) for i in range(render_layer_count)]
            max_cluster_right = max(x + w for x, _y, w, _h in all_row_bounds)
            indicators = _collect_thumb_indicators(
                left_thumb_prelim, right_thumb_prelim, keymap, config
            )

            def _thumb_bb(lt: ThumbClusterComponent, rt: ThumbClusterComponent):
                bx = lt.x
                by = min(lt.y, rt.y)
                br = rt.x + rt.width
                bb = max(lt.y + lt.height, rt.y + rt.height)
                return (bx, by, br - bx, bb - by)

            tb = _thumb_bb(left_thumb_prelim, right_thumb_prelim)
            connector_paths = _compute_connector_paths(
                indicators,
                all_row_bounds,
                layer_to_row,
                nk,
                ew_offset,
                max_cluster_right,
                layout.padding,
                tb,
            )

            # Find clearance needed: only check the ESCAPE segment
            # (first 2 points of each path, near the thumb cluster area).
            # Don't include routing/target Y values which are at layer rows.
            last_row_bottom = layout.layer_row_y_positions[-1] + layout.layer_row_heights[-1]
            escape_ys: list[float] = []
            for pts, _ in connector_paths:
                # Escape points are the first 2 (start + first turn)
                for _, py in pts[:2]:
                    escape_ys.append(py)

            min_escape_y = min(escape_ys) if escape_ys else layout.thumb_row_y
            max_escape_y = max(escape_ys) if escape_ys else layout.thumb_row_y

            if min_escape_y < last_row_bottom + nk:
                needed_shift = (last_row_bottom + nk) - min_escape_y
                min_thumb_y = layout.thumb_row_y + needed_shift
            else:
                min_thumb_y = layout.thumb_row_y

            layout.adjust_for_connectors(min_thumb_y, max_escape_y)

            # Rebuild thumb clusters at adjusted position, recompute paths,
            # and re-adjust canvas height for the new DOWN extents
            left_thumb_final, right_thumb_final = _build_thumb_clusters(
                config, keymap, layout, use_system_fonts
            )
            if left_thumb_final and right_thumb_final:
                all_row_bounds = [
                    layout.layer_row_bounding_box(i) for i in range(render_layer_count)
                ]
                max_cluster_right = max(x + w for x, _y, w, _h in all_row_bounds)
                indicators = _collect_thumb_indicators(
                    left_thumb_final, right_thumb_final, keymap, config
                )
                tb = _thumb_bb(left_thumb_final, right_thumb_final)
                connector_paths = _compute_connector_paths(
                    indicators,
                    all_row_bounds,
                    layer_to_row,
                    nk,
                    ew_offset,
                    max_cluster_right,
                    layout.padding,
                    tb,
                )
                # Re-adjust canvas for the final escape extents
                final_escape_ys = [py for pts, _ in connector_paths for _, py in pts[:2]]
                final_max_y = max(final_escape_ys) if final_escape_ys else layout.thumb_row_y
                layout.adjust_for_connectors(layout.thumb_row_y, final_max_y)

                # Adjust canvas width to fit actual routing columns (+ padding)
                max_path_x = max(
                    (max(px for px, _ in pts) for pts, _ in connector_paths),
                    default=layout.canvas_width,
                )
                layout.adjust_canvas_width(max_path_x + layout.padding)

    # --- Phase 3: Render everything at final positions ---
    # Extend canvas to fit copyright text below all content
    copyright_extra = 0.0
    if config.output.copyright:
        # Reserve space: gap + text line + padding
        prelim_badge_font_size = badge_dims.height * _BADGE_FONT_SIZE_RATIO
        copyright_extra = prelim_badge_font_size + layout.padding

    canvas_w = layout.canvas_width
    canvas_h = layout.canvas_height + copyright_extra
    padding = layout.padding
    margin = base_metrics.margin

    d = draw.Drawing(canvas_w, canvas_h)

    if not use_system_fonts:
        for font in Font:
            d.append_css(font.css_style)

    border = config.output.style.border
    d.append(
        draw.Rectangle(
            x=margin,
            y=margin,
            width=canvas_w - margin * 2.0,
            height=canvas_h - margin * 2.0,
            rx=border.radius if border else None,
            ry=border.radius if border else None,
            fill=palette.background_color,
            stroke=palette.border_color if border else None,
            stroke_width=border.width if border else None,
        )
    )

    label_font = (
        Font.FINGER_KEY.get_system_font_family() if use_system_fonts else Font.FINGER_KEY.value
    )
    title_font = Font.TITLE.get_system_font_family() if use_system_fonts else Font.TITLE.value

    badge_w = badge_dims.width
    badge_h = badge_dims.height
    badge_r = badge_dims.border_radius
    badge_font_size = badge_h * _BADGE_FONT_SIZE_RATIO
    badge_x = padding

    # Header: logo + title
    logo_width = badge_w * 1.06
    logo_height = _LOGO_ASPECT_RATIO.height_from_width(logo_width)
    d.append(
        draw.Image(
            x=padding,
            y=padding,
            width=logo_width,
            height=logo_height,
            path=ASSETS.logo_svalboard,
            embed=True,
        )
    )

    if config.output.keymap_title:
        title_text = config.output.keymap_title
    elif num_layers > 0:
        first_layer = config.keyboard.layers[0]
        title_text = f"{(first_layer.variant or first_layer.name)} Layers Layout"
    else:
        title_text = "Keymap Layout"
    d.append(
        draw.Text(
            title_text,
            font_size=badge_font_size * 1.8,
            x=layout.right_column_x,
            y=padding + logo_height / 2.0,
            text_anchor="start",
            dominant_baseline="central",
            font_family=title_font,
            fill=palette.text_color,
        )
    )

    # LAYERS heading
    if row_to_layer:
        first_badge_y = layout.layer_row_y_positions[0] + ew_offset
        d.append(
            draw.Text(
                "LAYERS",
                font_size=badge_font_size,
                x=badge_x + _BADGE_PADDING_LEFT,
                y=first_badge_y - badge_font_size * 0.2,
                text_anchor="start",
                dominant_baseline="text-after-edge",
                font_family=label_font,
                fill=palette.neutral_color,
            )
        )

    # Layer badges
    for row_idx, (pos, qmk_idx) in enumerate(row_to_layer):
        row_y = layout.layer_row_y_positions[row_idx]
        layer_cfg = config.keyboard.layers[pos]
        layer_color = (
            palette.layers[pos].base_color if pos < len(palette.layers) else palette.neutral_color
        )
        badge_y = row_y + ew_offset
        d.append(
            draw.Rectangle(
                x=badge_x,
                y=badge_y,
                width=badge_w,
                height=badge_h,
                rx=badge_r,
                ry=badge_r,
                fill=layer_color,
            )
        )
        d.append(
            draw.Text(
                f"{qmk_idx} {layer_cfg.name.upper()}",
                font_size=badge_font_size,
                x=badge_x + _BADGE_PADDING_LEFT,
                y=badge_y + badge_h / 2.0,
                text_anchor="start",
                dominant_baseline="central",
                font_family=label_font,
                fill="white",
            )
        )
        if layer_cfg.variant:
            d.append(
                draw.Text(
                    layer_cfg.variant,
                    font_size=badge_font_size,
                    x=badge_x + _BADGE_PADDING_LEFT,
                    y=badge_y + badge_h + badge_font_size * 0.2,
                    text_anchor="start",
                    dominant_baseline="text-before-edge",
                    font_family=label_font,
                    fill=layer_color,
                )
            )

    # THUMBS badge
    d.append(
        draw.Rectangle(
            x=badge_x,
            y=layout.thumb_row_y,
            width=badge_w,
            height=badge_h,
            rx=badge_r,
            ry=badge_r,
            fill=palette.text_color,
        )
    )
    d.append(
        draw.Text(
            "THUMBS",
            font_size=badge_font_size,
            x=badge_x + _BADGE_PADDING_LEFT,
            y=layout.thumb_row_y + badge_h / 2.0,
            text_anchor="start",
            dominant_baseline="central",
            font_family=label_font,
            fill="white",
        )
    )

    # Finger clusters
    cluster_width = layout.finger_cluster_width
    for row_idx, (pos, qmk_idx) in enumerate(row_to_layer):
        layer_data = keymap.layers[qmk_idx]
        ctx = RenderContext(
            palette=palette,
            layer_index=pos,
            has_double_south=config.keyboard.features.double_south,
            use_layer_colors_on_keys=config.output.style.use_layer_colors_on_keys,
            hold_symbol_position=config.output.style.hold_symbol_position,
            use_system_fonts=use_system_fonts,
            show_layer_indicators=config.output.style.show_layer_indicators,
            qmk_index_to_position=config.keyboard.qmk_index_to_position,
        )
        positions = layout.finger_cluster_positions(row_idx)
        for i in range(_FINGER_CLUSTERS_PER_SIDE):
            c = FingerClusterComponent(
                keymap_cluster=layer_data.left.fingers[i],
                side=KeyboardSide.LEFT,
                layout=Boundary(width=cluster_width, pos=positions[i]),
                render_context=ctx,
            )
            d.append(c.build())
        for i in range(_FINGER_CLUSTERS_PER_SIDE):
            c = FingerClusterComponent(
                keymap_cluster=layer_data.right.fingers[i],
                side=KeyboardSide.RIGHT,
                layout=Boundary(width=cluster_width, pos=positions[_FINGER_CLUSTERS_PER_SIDE + i]),
                render_context=ctx,
            )
            d.append(c.build())

    # Thumb clusters at final position
    left_thumb, right_thumb = _build_thumb_clusters(config, keymap, layout, use_system_fonts)
    if left_thumb:
        d.append(left_thumb.build())
    if right_thumb:
        d.append(right_thumb.build())

    # Connector lines
    if connector_paths:
        _draw_connector_paths(d, connector_paths, palette, config.keyboard.qmk_index_to_position)

    # Copyright
    if config.output.copyright:
        d.append(
            draw.Text(
                config.output.copyright,
                font_size=badge_font_size,
                x=canvas_w - padding,
                y=canvas_h - padding,
                text_anchor="end",
                dominant_baseline="text-after-edge",
                font_family=label_font,
                fill=palette.text_color,
                opacity=0.6,
            )
        )

    return d

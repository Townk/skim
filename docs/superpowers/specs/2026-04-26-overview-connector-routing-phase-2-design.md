# Overview Connector Routing — Phase 2 Design Spec

## Goal

Extend the connector-routing algorithm with per-layer finger-cluster routing,
the South + Double-South (S+DS) special case, and a multi-layer composition
driver. Phase 1 (`2026-04-26-overview-connector-routing-design.md` plus the
implementation in `connectors.py`) handles the thumb cluster only; Phase 2
delivers the same algorithmic skeleton for finger clusters running once per
layer row, weaves all sources into a single global Phase 2 column allocation,
and replaces `route_thumb_connectors` with a top-level
`route_overview_connectors` orchestrator.

## Relationship to Phase 1

This document supplements the Phase 1 spec at
`2026-04-26-overview-connector-routing-design.md`. Read that first. Phase 2
inherits its dataclasses (`Direction`, `ConnectorStep`, `ConnectorRouting`),
its Phase 1 sub-step framework (LEFT→DOWN, UP→RIGHT, DOWN→RIGHT), and its
Phase 2 column allocator.

The Phase 1 implementation refined a few constants and formulas after the
original spec was written. Those refinements are normative for Phase 2:

| Item | Original spec | Implemented (carries forward) |
| --- | --- | --- |
| `KEYMAP_SPACING` | `finger_cluster.north_key.width` (≈ outer key width) | `0.6 × outer_key_width` (tighter, settled visually) |
| `extra_top_padding` | `(N_up + 1) × KEYMAP_SPACING` | `N_up × KEYMAP_SPACING` |
| `extra_bottom_padding` | `(N_down + 1) × KEYMAP_SPACING` | `(N_down + 0.5) × KEYMAP_SPACING` when N_down > 0, else 0 |
| `first_column_x` | `bbox.right + KEYMAP_SPACING` (= `target_point.x`) | `bbox.right + 2 × KEYMAP_SPACING` (so the innermost path has a real `KEYMAP_SPACING`-long final LEFT segment) |
| `extra_right_padding` | `cols_used × KEYMAP_SPACING` | `(cols_used + 1) × KEYMAP_SPACING` |
| `target_point.y` | `bbox.y + bbox.height / 2` | `row_y + ew_key_y_offset + outer_key_size / 2` (East-key center, correct in DS rows) |
| `path.col_X` | spec field name | `ConnectorStep.col_x` (snake_case) |

`ConnectorStep` carries the additional fields populated during Phase 1:
`current_point`, `indicator_rect`, `key_origin_attr`. These exist on the
dataclass already and are reused unchanged.

## Per-layer finger cluster algorithm

Run once per rendered layer row. For each layer, the algorithm produces a
per-layer `path_list`, an `extra_top_padding`, and an `extra_bottom_padding`.
The shifts they imply propagate downward through the layout (see
*Multi-layer composition*).

### Cluster iteration order

Across the layer's eight finger clusters (left side outer-to-inner, then
right side inner-to-outer):

```
L4, L3, L2, L1, R1, R2, R3, R4
```

(L4 = left pinky / `left.pinky`; L1 = left index / `left.index`;
R1 = right index / `right.index`; R4 = right pinky / `right.pinky`.)

This order determines the order of `ConnectorStep` insertion into the
per-layer `path_list`, which in turn governs the order paths are seen by
the global Phase 2 column allocator.

### Per-cluster key order and direction

Within each cluster, keys are added in the listed order with the listed
initial direction:

| Cluster        | Order               | Direction per key                          |
| -------------- | ------------------- | ------------------------------------------ |
| **R4**         | N, W, S, DS, E, C   | RIGHT, RIGHT, RIGHT, RIGHT, UP, DOWN       |
| **All others** | W, N, E, S, DS, C   | UP, UP, UP, DOWN, DOWN, DOWN               |

Rationale (unchanged from Phase 1 spec): R4 sits closest to the routing
columns so most keys exit RIGHT directly; its E key would cross itself if
routed RIGHT, so it escapes UP; C is buried in the cluster middle and exits
DOWN under it. All other clusters route N/E/W up over the cluster top and
S/DS/C below.

### S+DS special case — South RIGHT-DOWN-RIGHT

In a non-R4 cluster, South and DS would both drop straight down at the
same column X. Center is offset to the left of South's X (renderer
convention) so it doesn't enter this conflict.

- If only South triggers OR only DS triggers → both go DOWN normally.
- If **both** South AND DS trigger → South does RIGHT-DOWN-RIGHT instead:
  1. South's initial direction is `RIGHT` (overrides the table's `DOWN`).
  2. A new Phase 1 sub-step **2.1 Make `RIGHT` go `DOWN`**: for each
     RIGHT-direction step, find its DS partner via
     `key_origin_attr == "double_south_key"` AND same source cluster,
     extend east `KEYMAP_SPACING` past the partner's `current_point.x`,
     mark direction `DOWN`. This mirrors `phase1_redirect_left_to_down`
     from Phase 1.
  3. From there, South joins the regular DOWN→RIGHT processing.

> The first RIGHT segment may visually extend into the inter-cluster gap
> or the next cluster's space. **Pass A** (see *Open Work*) addresses this
> with a column-aligned inter-cluster pre-padding pre-scan; until Pass A
> lands the path is geometrically correct but may overlap a neighbour
> cluster — a documented limitation.

### Phase 1 sub-step ordering for finger clusters

Identical to Phase 1's thumb algorithm with one new sub-step at 2.1:

1. Set initial moveTo for every entry.
2. Sub-steps:
   - 2.1 **`RIGHT` → `DOWN`** (S+DS special case; new for finger clusters).
   - 2.2 **`LEFT` → `DOWN`** (no LEFT-direction keys in finger clusters
     today; kept for symmetry with thumb).
   - 2.3 **`UP` → `RIGHT`**.
   - 2.4 **`DOWN` → `RIGHT`** (after 2.1, includes RIGHT-converted-to-DOWN
     South paths).

`extra_top_padding` and `extra_bottom_padding` are computed using the same
formulas as the thumb algorithm (Phase 1 carry-forward values above).

## Multi-layer composition

The driver runs the per-cluster algorithms top-down, weaves their outputs,
then runs Phase 2 globally over the full combined path list.

### Phase 1 — per layer, top-down (two passes)

Two padding shapes flow through the orchestrator, each handled differently:

| Padding | Effect on layout | Effect on `ConnectorRouting` returned |
| --- | --- | --- |
| layer N's `extra_top` | shifts row N and every row below it (incl. thumb + canvas) down | not returned (consumed inline) |
| layer N's `extra_bottom` | shifts rows **strictly below** N (incl. thumb + canvas) down — i.e., reserves the inter-layer gap | not returned (consumed inline) |
| thumb's `extra_top` | shifts the thumb cluster down (incl. canvas) | not returned (consumed inline) |
| thumb's `extra_bottom` | not applied to layout — DOWN lanes extend below the thumb into uncommitted canvas space | **returned** as `ConnectorRouting.extra_bottom_padding`; caller grows `canvas_h` by this amount |

The `+ 0.5 × KEYMAP_SPACING` buffer from Phase 1's `phase1_down_to_right`
applies to every source with `N_down > 0`. For per-layer sources it
becomes a slightly wider inter-layer gap (harmless, slightly looser
visual spacing); for the thumb it lands at the canvas edge as intended.

Pseudocode:

```
# Pass 1: discover paddings and shift layout, no final paths kept.
for layer in layers (top-down):
    paths_layer = build_finger_path_list_for_layer(layer)
    attach_indicator_rects(paths_layer)
    set_initial_moveto_for_each(paths_layer)
    phase1_redirect_right_to_down(paths_layer)   # S+DS
    phase1_redirect_left_to_down(paths_layer)    # symmetry; no-op today
    layer.extra_top    = phase1_up_to_right(paths_layer, ...)
    layer.extra_bottom = phase1_down_to_right(paths_layer, ...)
    if layer.extra_top > 0:
        layout.shift_layer_row_and_below(layer.source_layer, layer.extra_top)
    if layer.extra_bottom > 0:
        layout.shift_below_layer_row(layer.source_layer, layer.extra_bottom)

# Pass 1 thumb (against the now-cascaded layout).
paths_thumb = build_thumb_path_list(thumb)
…
thumb.extra_top    = phase1_up_to_right(paths_thumb, ...)
thumb.extra_bottom = phase1_down_to_right(paths_thumb, ...)
if thumb.extra_top > 0:
    layout.shift_thumb_down(thumb.extra_top)
# thumb.extra_bottom is held for the return value — not applied here.

# Caller now rebuilds indicator_rects against the fully-shifted layout.

# Pass 2: route every source against the final layout for keeps.
for layer in layers (top-down):
    paths_layer = build_finger_path_list_for_layer(layer)  # against shifted layout
    … run Phase 1 sub-steps again (we know paddings already; values are the same) …
paths_thumb = build_thumb_path_list(thumb)
… same …

all_paths = sum(layer.paths for layer in layers) + paths_thumb

# Phase 2 — single global pass, unchanged from Phase 1.
cols_used = allocate_columns(all_paths, first_column_x, KEYMAP_SPACING)
phase2_route_to_targets(all_paths)

return ConnectorRouting(
    paths=…,
    extra_top_padding=0.0,                   # already applied via shifts
    extra_bottom_padding=thumb.extra_bottom, # caller grows canvas
    extra_right_padding=(cols_used + 1) × KEYMAP_SPACING,
)
```

`extra_top_padding` returned is always `0.0` — every source's top
padding has already been applied via `shift_*` methods. The field is
kept on `ConnectorRouting` for symmetry and for the (rare) future case
of a source whose top padding the caller must apply externally.

### Why two passes

Phase 1 of Plan 1 already discovered and adopted the two-pass strategy:
path coordinates are computed against the indicator positions in the
*current* layout; shifting the layout post-routing decouples them.
Pass 1 just sums paddings; Pass 2 routes against the fully-shifted
layout for the keeps. Phase 2 inherits this approach, with one cascade
step per layer instead of one for the thumb.

Path-segment translation (the alternative the original spec hinted at)
would require mutating `draw.Path` objects mid-construction. drawsvg's
public API doesn't expose this cleanly. Pass-1 cost is bounded by the
priority lists (~6 keys per cluster × 8 clusters × N layers + 13 thumb
keys); negligible for typical keymaps.

### Phase 2 — global

The column allocator and target-routing logic from Phase 1 are reused
verbatim. The only change: `all_paths` now spans every layer's finger
paths plus the thumb paths, in this stable order:

```
all_paths = layer_0.fingers + layer_1.fingers + … + layer_N.fingers + thumb
```

(Each layer's finger sub-list is itself in cluster/key priority order.)

Two paths can share a column if their vertical Y-spans don't overlap, so
column count is bounded by max-simultaneous-Y-overlap across all sources,
not total path count.

### Multi-target merge — unchanged

The Phase 1 multi-target merge (outermost path per target_layer emits the
final LEFT segment) applies across sources too: a finger trigger and a
thumb trigger both targeting the same layer share one final LEFT segment,
emitted by whichever has the largest `col_x`.

## API surface

### Public

```python
@dataclass(frozen=True, slots=True)
class OverviewLayerSource:
    source_layer: int
    left:  SplitSide[SvalboardTargetKey]
    right: SplitSide[SvalboardTargetKey]


@dataclass(frozen=True, slots=True)
class ThumbSource:
    source_layer: int
    left:  ThumbCluster[SvalboardTargetKey]
    right: ThumbCluster[SvalboardTargetKey]


def route_overview_connectors(
    layers: Sequence[OverviewLayerSource],
    thumb:  ThumbSource,
    layout: RoutingLayout,
    indicator_rects: Mapping[SvalboardTargetKey, tuple[float, float, float, float]],
    keymap_spacing: float,
) -> ConnectorRouting: ...
```

`route_thumb_connectors` is removed. The single existing caller
(`overview.py`) updates to call `route_overview_connectors` instead and
collects sources for every layer.

### Private helpers (in `connectors.py`)

- `_R4_PRIORITY: list[tuple[str, Direction]]` — six entries.
- `_NON_R4_PRIORITY: list[tuple[str, Direction]]` — six entries.
- `build_finger_path_list_for_cluster(cluster, is_r4, source_layer, layout, keymap_spacing) -> list[ConnectorStep]`
  — applies the right priority table, decides South initial direction by
  checking whether DS also triggers, populates `key_origin_attr`.
- `build_finger_path_list_for_layer(left, right, source_layer, layout, keymap_spacing) -> list[ConnectorStep]`
  — iterates the 8 clusters in `L4, L3, L2, L1, R1, R2, R3, R4` order,
  flat-concatenates each cluster's step list.
- `phase1_redirect_right_to_down(path_list, keymap_spacing) -> None`
  — mirror of `phase1_redirect_left_to_down`. For each `RIGHT`-direction
  step, find its DS partner via `key_origin_attr == "double_south_key"`
  AND same source cluster, extend east `keymap_spacing` past the partner's
  drop X, mark direction `DOWN`. Cluster identity is checked via the
  step's `source_cluster_attr` (new field on `ConnectorStep`; see below).

### `ConnectorStep` addition

Add one field to track which cluster a step originated in (so the S+DS
partner search can scope to the same cluster):

```python
source_cluster_attr: str = ""   # e.g. "left.index", "right.pinky"
```

Empty string for thumb steps (current behavior; partner searches that
key don't apply to thumb).

### `OverviewLayout` additions

```python
def shift_layer_row_and_below(self, row_idx: int, amount: float) -> None:
    """Shift layer row `row_idx` and every row below it (plus thumb) down
    by ``amount``; grow the canvas accordingly. No-op when amount <= 0.

    Used to apply a layer's ``extra_top_padding``."""

def shift_below_layer_row(self, row_idx: int, amount: float) -> None:
    """Shift every row strictly below `row_idx` (plus thumb) down by
    ``amount``; grow the canvas accordingly. The row at ``row_idx`` itself
    does NOT move. No-op when amount <= 0.

    Used to apply a layer's ``extra_bottom_padding`` — the lanes occupy
    the gap reserved between the source layer's row and the next thing
    below it."""
```

Mutates `_layer_row_y_positions`, `_thumb_row_y`, and `_canvas_height`.
`shift_thumb_down` stays for the thumb-only case.

### `_RoutingLayoutAdapter` addition (overview.py)

Mirror methods that translate QMK→row before delegating to
`OverviewLayout`. Both translation methods accept a QMK source-layer
index and resolve to the corresponding row index internally.

## Indicator-rect plumbing

`overview.py` already has `_compute_thumb_indicator_rects`. Phase 2 adds:

- `_compute_finger_indicator_rects(layer_clusters, keymap, config) -> dict[Key, Rect]`
  — mirrors the thumb helper for the 8 finger clusters of one layer.
- `_compute_all_indicator_rects(layers, thumb_components, keymap, config) -> dict[Key, Rect]`
  — top-level helper that calls the per-source helpers and concatenates
  the maps. Called twice during the two-pass strategy: once before Pass 1
  (so Phase 1 can attach starting points), once after the shifts settle
  (so Pass 2 routes against the post-shift indicator positions).

## Test strategy

### Synthetic fixture keymap

`tests/integration/fixtures/connector-routing-coverage.vil` — designed to
exercise every code path:

- R4 cluster with N/W/S/DS RIGHT triggers, E UP, C DOWN.
- Non-R4 cluster with W/N/E UP triggers, S/DS DOWN (no S+DS conflict).
- Non-R4 cluster with S+DS double-trigger (exercises RIGHT-DOWN-RIGHT).
- Triggers on multiple non-zero source layers (exercises cascading
  shifts and Phase 2 sharing columns across layers).
- Existing thumb LT_Up + LT_Down LEFT-DOWN case (cross-source
  compatibility — survived from Phase 1 unchanged).

### Unit tests (`tests/unit/application/render/test_connectors.py`)

For each new helper, follow the Phase-1 TDD pattern (fail → implement
→ pass):

- `build_finger_path_list_for_cluster`: R4 priority order; non-R4
  priority order; S+DS direction logic (south = RIGHT iff DS also
  triggers; south = DOWN otherwise); skip-rule delegation to
  `target_point_for`; `key_origin_attr` and `source_cluster_attr`
  populated.
- `build_finger_path_list_for_layer`: cluster iteration order
  L4→L3→L2→L1→R1→R2→R3→R4; flat concatenation; empty layer returns `[]`.
- `phase1_redirect_right_to_down`: scoped partner-finding (same
  cluster); fallback when no annotated DS partner; no-op when no
  RIGHT-direction steps; multiple RIGHT steps redirected together.
- `route_overview_connectors`:
  - Empty case → all-zero padding, no paths.
  - Single layer with one finger trigger → one path, expected paddings.
  - Multi-layer with cascading shifts → each layer's `extra_top_padding`
    propagates correctly; rows below are shifted; thumb cluster shifts.
  - S+DS end-to-end → south path has 4+ segments matching the
    RIGHT-DOWN-RIGHT geometry.
  - Multi-target merge across sources (finger + thumb both target same
    layer) → outermost emits the final LEFT segment; non-outermost
    terminate at `(col_x, target_y)`.

### Integration tests (`tests/integration/test_overview_connectors.py`)

Render the synthetic fixture and assert:

- Path count equals the keymap's total trigger count (finger + thumb,
  excluding self-ref and out-of-range).
- Each path's stroke color matches its target layer's palette color.
- No path coordinate escapes the final canvas bounds.
- The S+DS trigger produces a path with at least four `L` commands
  whose first horizontal segment goes east past the source cluster
  (`x` strictly greater than the source cluster's right edge).
- `extra_right_padding` matches `(cols_used + 1) × keymap_spacing`,
  where `cols_used` is provable from the fixture's expected
  Y-overlap structure (test computes the expected count and asserts).

The single existing thin integration test
(`test_overview_renders_with_connectors_for_layer_trigger_keymap`)
remains as a smoke test for the public sample.

## Algorithm output

`ConnectorRouting` unchanged: `paths`, `extra_top_padding`,
`extra_bottom_padding`, `extra_right_padding`. Caller responsibilities
unchanged (apply each padding to the layout / canvas).

`extra_top_padding` and `extra_bottom_padding` are sums across all
sources; `extra_right_padding` is the global Phase 2 result.

## Edge cases

| Case | Handling |
| --- | --- |
| `show_layer_indicators` or `show_layer_connectors` off | Skip everything; empty `ConnectorRouting`. (Inherited from Phase 1.) |
| No layer or thumb has any layer_switch trigger | All path lists empty; all paddings 0. |
| Self-referential or out-of-range `layer_switch` | Skipped at `target_point_for`; no `ConnectorStep` produced. |
| Multiple sources target the same layer | Multi-target merge — outermost (largest `col_x`) emits final LEFT segment. |
| S+DS double-trigger on a non-R4 cluster | South does RIGHT-DOWN-RIGHT (Phase 1 sub-step 2.1). May visually overlap neighbour cluster until Pass A lands. |
| Layer with `extra_top_padding > 0` shifts every row below | `shift_layer_row_and_below` handles cascading; subsequent layers' Phase 1 runs against the already-shifted layout. |
| Layer with `extra_bottom_padding > 0` adds inter-layer gap | `shift_below_layer_row` shifts rows strictly below the current source down; lanes occupy the freed gap. The 0.5 buffer becomes a slightly looser inter-layer gap (acceptable). |
| Thumb's `extra_bottom_padding > 0` | NOT applied to layout. Returned in `ConnectorRouting.extra_bottom_padding`; caller grows `canvas_h` by it (Phase 1 already handles this). |

## Module organization

`connectors.py` adds ~150 lines (priority tables, two new builders, one
new Phase 1 sub-step helper, the new orchestrator) and removes ~75 lines
(`route_thumb_connectors` body becomes a special case of the new
orchestrator's thumb path). Net file size stays under 700 lines.

`overview.py` adds the `_compute_finger_indicator_rects` and
`_compute_all_indicator_rects` helpers (~80 lines) and updates
`draw_overview` to collect sources and call `route_overview_connectors`.

`overview_layout.py` adds `shift_layer_row_and_below` (~12 lines).

If `connectors.py` crosses ~800 lines after Phase 2 lands, revisit a
package split (`connectors/builders.py`, `connectors/phases.py`,
`connectors/orchestrator.py`) in a follow-up.

## Open / Future Work

### Pass A — inter-cluster right-padding for S+DS double-trigger

Carries forward unchanged from Phase 1. Not in this plan's scope. When a
non-R4 cluster has both South and DS triggering on any layer, the new
RIGHT-DOWN-RIGHT path's first RIGHT segment may visually intrude on the
neighbour cluster's space. Pass A is a layout pre-scan that reserves
`KEYMAP_SPACING` of inter-cluster padding for affected cluster columns
across **every layer** (column alignment must hold). Scheduled when a
real keymap actually exercises the visual issue.

### Other items inherited from Phase 1

- Lane order rationale within direction groups — revisit if specific
  keymaps want different priority.
- Source layer for thumb cluster — currently fixed at layer 0.
- Path style (dash pattern, stroke width, end-cap markers) — renderer
  concern, not routing.

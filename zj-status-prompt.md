# zj-status: Zellij Status Bar Plugin

## Overview

Build `zj-status`, a Zellij plugin that renders a status bar at the bottom of
the terminal. It is a port of the WezTerm plugin `statusbar.wezterm`, adapted
to Zellij's architecture, mode system, and plugin API.

The behavioral specification of the original plugin is located at:
`docs/specs/statusbar-wezterm-requirements.md`

That document is the **source of truth** for algorithms (tab truncation,
equalization, scrolling, color gradient, contrast handling). This prompt
describes what to build for Zellij specifically — where this prompt is silent
on an algorithm's details, defer to the spec. Where this prompt explicitly
diverges from the spec, this prompt wins.

---

## Concept Mapping (WezTerm → Zellij)

Before reading the spec, internalize these translations:

| WezTerm Concept | Zellij Equivalent | Notes |
|---|---|---|
| Workspace | Session | Zellij sessions are named. The default session varies (often the user's shell creates one named `main` or similar). |
| Key table / Leader | Input mode | Zellij modes: `normal`, `locked`, `resize`, `pane`, `tab`, `scroll`, `enter_search`, `search`, `rename_tab`, `rename_pane`, `session`, `move`, `prompt`, `tmux`. |
| `window:leader_is_active()` | No equivalent | Zellij has no "leader key" concept. Ignore spec §6.1's leader branch entirely. |
| Tab (`tab_index`, `tab_id`, `is_active`) | `TabInfo` from `TabUpdate` event | Zellij provides tab name, active status, pane list, position. |
| Pane (`foreground_process_name`, `title`, `is_zoomed`) | `PaneInfo` / `PaneManifest` | Available from `TabUpdate` and `PaneUpdate` events. |
| `update-status` event | `render()` call | Zellij calls `render()` when the plugin's viewport needs repainting. |
| `format-tab-title` (called per tab) | Plugin renders ALL tabs itself | The plugin owns the entire bar; it draws every tab in a single `render()` pass. |
| `use_fancy_tab_bar = false` | Inherent | Zellij plugins render raw ANSI-styled cells. |
| `window:get_dimensions().is_full_screen` | See §Fullscreen Detection below | Zellij does not expose this directly. |
| `wezterm.color.parse` / `darken` / `lighten` / `contrast_ratio` / `gradient` | Must be implemented | No built-in color manipulation in the Zellij plugin API. |
| `wezterm.column_width(string)` | `unicode-width` crate | Use `UnicodeWidthStr::width()` for cell-width arithmetic. |
| `wezterm.nerdfonts.*` | Hardcoded Unicode codepoints | Reference the same NerdFont code points from the spec. |

---

## Architecture & Performance

### Plugin Lifecycle in Zellij

Zellij's plugin system is WASI-based. A status bar plugin is declared in the
user's KDL layout and instantiated once **per tab**. Each tab's instance
receives the full session state via events (`TabUpdate`, `ModeUpdate`,
`SessionUpdate`, etc.), but a newly spawned instance starts cold.

The core architectural challenge: when the user opens a new tab, a new plugin
instance starts. It must immediately render the correct bar (with all existing
tabs in their current state) without visible flicker or a loading state. The
`TabUpdate` event arrives on subscription and contains the full tab list — use
it to hydrate immediately.

### Performance Requirements

Reference implementation for performance expectations:
[`zjstatus`](https://github.com/dj95/zjstatus).

Requirements:

1. **Debounce rapid events.** If N `TabUpdate` events arrive within a short
   window (e.g., the user holds a "new tab" keybinding and spawns 10 tabs in
   200ms), the plugin MUST coalesce them and render only the final state. Do
   NOT render intermediate states that will be immediately overwritten.

2. **Minimal allocations in the render path.** Pre-compute what you can on
   event receipt; `render()` should assemble pre-computed segments, not parse
   or compute layouts from scratch.

3. **No blocking I/O in the render path.** System queries (battery, WiFi) must
   run asynchronously or be cached with a TTL. Never block `render()` on a
   shell command.

4. **Instant cold-start hydration.** A new instance must produce a correct
   first frame using only the `TabUpdate` event data (which Zellij sends on
   subscription). No multi-frame "loading" state.

---

## Feature Specification

### Status Bar Layout

The bar is a single row at the bottom of the terminal:

```
[ tabs ... ]                    [ mode | session | battery wifi | date/time ]
 ← left-aligned                                              right-aligned →
```

- **Left side:** Tab list (§5 of spec).
- **Right side:** Status segments (§6 of spec), rendered right-to-left with
  powerline-style dividers between segments.

### Tabs

Implement the tab rendering system from spec §5, with these adaptations:

1. **Title composition** (spec §5.3): Use the same priority chain:
   - User-set tab name (via `rename-tab` action or CLI) → show with tab icon.
   - Foreground process is a long-lived process → show process icon + name.
   - Otherwise → show CWD: directory icon + basename of the working directory.
     Use home icon (`icons.tabs.home`) when CWD is `$HOME`.

2. **Process icon mapping** (spec §5.6): Port the full hardcoded table. Zellij
   provides the foreground process name via `PaneInfo`. Determine "long-lived"
   vs "ephemeral" processes: shells (bash, zsh, fish, nu) are ephemeral (show
   CWD instead); everything else is long-lived (show process name + icon).

3. **Truncation** (spec §5.3.1): Implement the exact truncation algorithm with
   configurable `truncation_point` (default 0.4).

4. **Layout / equalization** (spec §5.4.4): When tabs exceed available width,
   apply the equalization algorithm.

5. **Scrolling** (spec §5.4.5): When equalization would shrink any tab below
   `MIN_TAB_WIDTH` (12 cells), switch to the visible-window algorithm with
   chevron indicators. The visible window is centered on the active tab.

6. **Active tab styling:** The active tab gets a distinct background color
   (from the Zellij theme or user config). Inactive tabs get the inactive
   color.

7. **Mode-active behavior** (spec §5.1): When a non-normal input mode is
   active, hide all inactive tabs and show only the active tab with mode-
   colored styling and a rounded edge glyph (`ple_right_half_circle_thick`).

8. **Zoomed pane indicator:** If the active pane in a tab is zoomed, append a
   zoom indicator glyph to the tab title (same as spec §5.3 extra-icons).

9. **Tab index:** Each tab shows its 1-based index before the title.

### Right-Side Status Segments

Implement the segment system from spec §6, with these adaptations:

#### Mode Segment (always, when mode ≠ normal)

- **All** Zellij input modes except `normal` produce a visible mode segment.
- Each mode has a configurable icon and label. Defaults:

  | Mode | Label | Default Icon (NerdFont) |
  |---|---|---|
  | `locked` | Locked | `md_lock` |
  | `resize` | Resize | `md_resize` |
  | `pane` | Pane | `md_view_column` |
  | `tab` | Tab | `md_tab` |
  | `scroll` | Scroll | `md_unfold_more_horizontal` |
  | `enter_search` | Search | `fa_search` |
  | `search` | Search | `fa_search` |
  | `rename_tab` | Rename | `md_rename` |
  | `rename_pane` | Rename | `md_rename` |
  | `session` | Session | `md_collage` |
  | `move` | Move | `md_cursor_move` |
  | `prompt` | Prompt | `md_console` |
  | `tmux` | Tmux | `md_apple_keyboard_command` |

- Each mode has a configurable color. The color drives the gradient for the
  entire right side (spec §6.2).
- When mode is `normal`, this segment is suppressed (returns width 0).

#### Session Segment (conditional)

- Displayed only when the current session name is **not** `main`.
- Shows: session icon + session name.
- This is the equivalent of spec §6.4.1's workspace behavior (suppress
  `default` workspace → suppress `main` session).

#### Battery Segment (conditional)

- Displayed only when the terminal is fullscreen OR is not a graphical terminal
  (see §Fullscreen Detection).
- Cross-platform detection:
  - **macOS:** Read from `ioreg` or `/Library/...` battery paths, or use the
    `battery` crate.
  - **Linux:** Read `/sys/class/power_supply/BAT*/capacity` and
    `/sys/class/power_supply/BAT*/status`.
  - If no battery is detected, show a static desktop/host icon
    (`icons.pane_host.host`).
- Icon selection follows spec §6.4.3 thresholds: `>=90` (high), `>=40`
  (medium), `>5` (low), `<=5` (outline/empty).
- **Fix the spec quirk:** When charging (state != Full and state == Charging),
  use the `charging` icon array, not `discharging`. The WezTerm version has a
  bug where `charging[1..3]` are never shown — fix this.
- Cache battery state with a TTL (e.g., 30 seconds). Never call system APIs
  in the render path.

#### WiFi Segment (conditional)

- Same visibility condition as battery (fullscreen or non-graphical terminal).
- Cross-platform detection:
  - **macOS:** `networksetup -getairportpower <iface>` or
    `/System/Library/PrivateFrameworks/Apple80211.framework/...` — cache the
    interface name.
  - **Linux:** `nmcli radio wifi` or read
    `/sys/class/net/*/wireless` presence.
- Show active icon when connected, inactive icon when off.
- Cache with a TTL (e.g., 10 seconds).

#### Date/Time Segment (conditional)

- Same visibility condition as battery (fullscreen or non-graphical terminal).
- Format: `%a %b %-e %-l:%M%P` (e.g., `Fri May 23 5:42pm`).
- Always the rightmost (last) segment.
- Refreshes on every render cycle — no separate timer needed since Zellij
  redraws the bar on events.

### Segment Rendering & Color

Implement spec §6.4's `format_segment` logic:

- Each segment has a background color.
- Foreground = `background.darken(0.8)`. If `contrast_ratio(bg, fg) < 3.8`,
  switch to `background.lighten(0.6)`.
- Segments are separated by powerline dividers (`ple_lower_right_triangle`)
  with `bg=left_segment_color, fg=right_segment_color`.
- The backgrounds form a 5-stop gradient from mode color (rightmost/loudest)
  to the tab bar background color (spec §6.2). Use perceptual interpolation
  (Oklab or similar) for the gradient.

### Segment Elision

Follow spec §6.3.1 exactly: when a segment returns width 0, collapse the
corresponding gradient slot and divider. The rendering must gracefully degrade
to zero right-side content (e.g., normal mode + `main` session + windowed =
empty right side).

---

## Fullscreen Detection

Zellij does not expose whether the host terminal is fullscreen. Use this
heuristic:

- The plugin knows its own viewport width (columns available in `render()`).
- If `columns >= threshold` (configurable, default: 120), treat as
  "fullscreen-equivalent" and show battery/wifi/time segments.
- Alternatively, detect non-graphical terminals: if `$DISPLAY` / `$WAYLAND_DISPLAY`
  are unset AND `$TERM` does not indicate a GUI terminal, always show system
  segments (the user is likely on a TTY or SSH session with no other system
  tray).

The condition should be: **show system segments when the terminal is wide
enough (or non-graphical) to benefit from the extra information.**

---

## Configuration (KDL Layout)

All configuration is done via Zellij's native KDL `plugin` block. No external
config files.

Example layout snippet showing all configurable options with their defaults:

```kdl
layout {
    pane size=1 borderless=true {
        plugin location="file:target/wasm32-wasip1/release/zj-status.wasm" {
            // Tab behavior
            tab_max_width          40
            tab_truncation_point   "0.4"
            tab_hide_single        false

            // Width threshold for showing system segments
            fullscreen_min_cols    120

            // Mode colors (CSS hex strings)
            mode_color_locked      "#ff6666"
            mode_color_resize      "#ffcc66"
            mode_color_pane        "#66ccff"
            mode_color_tab         "#cc99ff"
            mode_color_scroll      "#99ffcc"
            mode_color_search      "#ffff66"
            mode_color_session     "#ff99cc"
            mode_color_move        "#66ffcc"
            mode_color_tmux        "#cc66ff"
            mode_color_rename_tab  "#ffcc99"
            mode_color_rename_pane "#ffcc99"
            mode_color_prompt      "#99ccff"

            // Override the session name that suppresses the session segment
            // (default: "main")
            default_session_name   "main"

            // Override icons (NerdFont codepoints as hex strings)
            // icon_wifi_active     "U+F05A9"
            // icon_wifi_inactive   "U+F092E"
            // ... (full icon override table)
        }
    }
}
```

Parse configuration from the `BTreeMap<String, String>` provided by Zellij's
plugin API in the `load()` function. All values are strings; parse numbers and
booleans from their string representations.

---

## Events to Subscribe

Subscribe to these Zellij events in `load()`:

| Event | Purpose |
|---|---|
| `ModeUpdate` | Detect input mode changes. Drives mode segment color/label. |
| `TabUpdate` | Full tab list with names, active status, pane info. Drives tab rendering. |
| `SessionUpdate` | Session name. Drives session segment. |
| `PaneUpdate` | Pane focus, CWD, foreground process. Drives tab title content. |

On each event, update internal state and request a re-render (if the state
actually changed — skip redundant renders).

---

## Debounce Strategy

When multiple events arrive in a burst (e.g., rapid tab creation):

1. On each event, update internal state immediately (this is cheap).
2. Do NOT call render logic on every event. Instead, mark the plugin as
   "dirty."
3. In the `render()` call (which Zellij triggers on its own
   
   
   
   
   
   
   
    
   
   
   
   
    
    
     
   
    
    cadence), only recompute
   layout if dirty. Clear the dirty flag after rendering.

This ensures that 10 rapid `TabUpdate` events result in a single layout
computation and render pass using the final state.

---

## Project Structure

```
zj-status/
├── Cargo.toml
├── docs/
│   └── specs/
│       └── statusbar-wezterm-requirements.md    # behavioral reference
├── src/
│   ├── main.rs          # plugin entry point (load, update, render)
│   ├── config.rs        # KDL config parsing, defaults
│   ├── state.rs         # session state (tabs, mode, session name, system info)
│   ├── tabs.rs          # tab title composition, §5.3 algorithm
│   ├── layout.rs        # tab width equalization (§5.4.4) and scrolling (§5.4.5)
│   ├── segments.rs      # right-side segment rendering (§6.4)
│   ├── color.rs         # color parsing, darken/lighten, contrast, gradient (§7)
│   ├── icons.rs         # NerdFont codepoint constants, process-icon map (§5.6, §8)
│   ├── truncation.rs    # text truncation algorithm (§5.3.1)
│   ├── system.rs        # battery, WiFi detection (cached, async-safe)
│   └── render.rs        # final bar assembly, ANSI output
└── README.md
```

---

## Acceptance Criteria

The plugin is complete when:

1. **Tab rendering matches spec behavior:** tabs show index + icon + title,
   truncate correctly at `truncation_point`, equalize when crowded, scroll with
   chevrons when extremely crowded.
2. **Mode indicator works for all 13 non-normal modes:** each shows its icon,
   label, and drives the gradient color of the right side.
3. **Session segment appears only for non-`main` sessions.**
4. **System segments (battery, WiFi, time) appear only when width >= threshold
   or non-graphical terminal.**
5. **Battery is cross-platform** (macOS + Linux) with correct charging vs
   discharging icon arrays.
6. **No flicker on rapid tab operations:** holding "new tab" keybinding
   produces a smooth final state, not 10 intermediate renders.
7. **Cold-start is instant:** switching to a new tab shows the correct bar
   immediately (no loading frame).
8. **All configuration is via KDL layout** with sensible defaults that work
   with no configuration.
9. **Color contrast** is always >=3.8 (spec §7 algorithm).
10. **The plugin compiles to WASM** and runs under Zellij's WASI sandbox
    without errors.

---

## What NOT to Implement (Out of Scope for v1)

- Tab activity notifications (bell, output detection).
- Mouse click handlers.
- Pane host / SSH detection (Zellij does not reliably expose remote host info
  in the same way WezTerm's pane title does).
- Left-side status content.
- Persistence of state across Zellij restarts.
- Custom user-defined segments.
- Animation or transitions (debounce is sufficient for v1).

# `statusbar.wezterm` — Reverse-Engineered Specification

This spec describes the behavior of the plugin at the current `main` revision
precisely enough to re-implement it in another language and/or on another
terminal multiplexer. It is descriptive, not prescriptive — every behavior
listed below is what the code does today, including quirks where they exist
(those are called out explicitly as **Observed quirk**).

When the README and source disagree, the source is treated as authoritative.
The README shows `max_width = 35` and omits the `pane_host` icon family; the
actual defaults are `max_width = 40` and `pane_host = { ssh, host }`.

---

## 1. Glossary & Host Environment

| Term | Meaning in this spec |
|---|---|
| **Host terminal** | WezTerm. The plugin is a Lua module loaded by WezTerm's `wezterm.plugin.require`. |
| **Tab** | A WezTerm tab. Has: `tab_index` (0-based), `tab_id` (numeric), `tab_title` (user-set string), `is_active`, `panes` (list), `active_pane`. |
| **Pane** | A split inside a tab. Has: `pane_id`, `title` (built-in title), `foreground_process_name`, `is_zoomed`, `left`, `width` (cell coordinates). |
| **Workspace** | WezTerm concept; named string. The default workspace is named `default`. |
| **Key table** | WezTerm modal keybinding set. Plugin uses these as "modes": `command` (leader), `search_mode`, `copy_mode`, plus the synthetic `workspace`. |
| **Leader** | WezTerm "leader key" prefix mode. While active, the plugin treats the mode as `command`. |
| **Status bar** | The bottom row of the WezTerm window. The plugin sets `tab_bar_at_bottom = true`, `use_fancy_tab_bar = false`. The left half holds tabs; the right half is set via `window:set_right_status`. |
| **Fullscreen** | `window:get_dimensions().is_full_screen == true`. |
| **NerdFont** | Patched icon font; all glyphs are referenced via `wezterm.nerdfonts.<name>`. A re-implementation needs the same code points. |

The plugin is single-user, single-window-aware, but its state is keyed by
WezTerm IDs that are unique per WezTerm process.

---

## 2. Plugin Contract

### 2.1 Entry Point

The plugin exposes one public function and one public table:

```
apply_to_config(config, customization?) -> void
naming_cache  -> StatusBarNamingElementCache  (see §10)
```

`apply_to_config(config, customization)`:

1. **Merge defaults.** Take the default config (see §3), deep-merge
   `customization` into it. Merge rule: for each key in `customization`, if
   both sides are tables, recurse; otherwise overwrite. Keys not present in
   `customization` keep the default. The merged object becomes the effective
   `status_config`.
2. **Force these WezTerm settings on the user's config object** (these are not
   optional — the plugin overrides them):
   - `tab_bar_at_bottom = true`
   - `use_fancy_tab_bar = false`
   - `hide_tab_bar_if_only_one_tab = status_config.tabs.hide_on_single_tab`
   - `tab_max_width = status_config.tabs.max_width`
   - `tab_and_split_indices_are_zero_based = false` (tab indices shown to user
     are 1-based)
3. **Register two WezTerm event handlers:**
   - `update-status` → §6 (right-side status segments)
   - `format-tab-title` → §5 (tab rendering)

There are no other side effects. The plugin does not register keybindings,
palettes, commands, or menus.

### 2.2 Resolving the Plugin Install Directory

The Lua module loads sibling files via Lua's `package.path`. To find its own
directory, it iterates `wezterm.plugin.list()` and matches plugins whose `url`
ends with `statusbar.wezterm` **or** `statusbar.wezterm.git`.

**Observed quirk:** any other naming (fork, mirror under a different name) will
fail to resolve, and the plugin will error on `require`.

A re-implementation on a non-WezTerm host has no equivalent of this discovery
step; it can be ignored.

---

## 3. Configuration Model

### 3.1 Schema

```
StatusBarConfig {
  tabs:        StatusBarTabsConfig
  icons:       StatusBarIconLibrary
  key_tables:  table<string, StatusBarConfigKeyTable>
}

StatusBarTabsConfig {
  hide_on_single_tab: boolean    -- default false
  max_width:          number     -- default 40 (cells)
  truncation_point:   number     -- default 0.4 (0.0..1.0)
}

StatusBarConfigKeyTable {
  label: string?    -- text shown after icon; if nil and the key table is
                    --   named 'workspace', uses workspace name; otherwise
                    --   uses key-table name itself
  icon:  string?    -- single NerdFont glyph, optionally with trailing space
  color: string?    -- CSS-like color string parsed by wezterm.color.parse;
                    --   if nil and key_table != 'workspace', the segment
                    --   falls through to inactive-tab bg
}

StatusBarIconLibrary {
  battery: {
    charging:    string[4]   -- low -> high
    discharging: string[4]   -- low -> high
  }
  mode:      { command, workspace, search, copy:    string }
  pane_host: { ssh, host:                            string }
  tabs:      { dir, home, process, tab:              string }
  time:      { calendar:                             string }
  wifi:      { active, inactive:                     string }
}
```

### 3.2 Default Values (Authoritative)

```
tabs = {
  hide_on_single_tab = false,
  max_width          = 40,
  truncation_point   = 0.4,
}

icons.battery.charging    = [U+F08DF, U+F12A4, U+F12A5, U+F12A6]
  -- md_battery_charging_outline / low / medium / high

icons.battery.discharging = [U+F008E, U+F12A1, U+F12A2, U+F12A3]
  -- md_battery_outline / low / medium / high

icons.mode = {
  command   = U+F0633,    -- md_apple_keyboard_command
  workspace = U+F0640,    -- md_collage
  search    = U+F002,     -- fa_search
  copy      = U+F018F,    -- md_content_copy
}

icons.pane_host = {
  ssh  = U+F08B9,         -- md_remote_desktop
  host = U+F07C0,         -- md_desktop_classic
}

icons.tabs = {
  dir     = U+F0770,      -- md_folder_open
  home    = U+F02DC,      -- md_home
  process = U+F070E,      -- md_run
  tab     = U+F04E9,      -- md_tab
}

icons.time = {
  calendar = U+F00F0,     -- md_calendar_clock
}

icons.wifi = {
  active   = U+F05A9,     -- md_wifi
  inactive = U+F092E,     -- md_wifi_strength_off_outline
}

key_tables = {
  command     = { label = 'Command', icon = icons.mode.command,   color = nil },
  workspace   = {                    icon = icons.mode.workspace, color = nil },
  search_mode = { label = 'Search',  icon = icons.mode.search,    color = nil },
  copy_mode   = { label = 'Copy',    icon = icons.mode.copy,      color = nil },
}
```

No `color` is provided by default for any key table. With no color, the mode
segment uses the WezTerm color scheme's `tab_bar.inactive_tab.bg_color`. Users
typically set a distinct color per mode.

---

## 4. Cell-Width Arithmetic

All width math in this spec uses **terminal cell columns**, not bytes or
codepoints. NerdFont glyphs may be 1 or 2 cells wide; the implementation calls
`wezterm.column_width(string)` to measure. A re-implementation must use an
equivalent (e.g. `wcwidth` / `unicode-width`).

Two named widths used throughout:

- `DIVIDER_GLYPH` = NerdFont `ple_lower_right_triangle`,
  `DIVIDER_WIDTH = column_width(DIVIDER_GLYPH)`.
- `MIN_TAB_WIDTH = 12` cells. This is the floor below which scrolling kicks in
  (§5.4.3).

---

## 5. Tab Bar Specification

The tab bar is rendered by WezTerm calling
`format-tab-title(tab, all_tabs, panes, config, hover, max_width)` once per
tab, every redraw. The plugin's handler is responsible for:

1. Deciding whether this tab is visible at all (scrolling hides tabs outside a
   window),
2. Computing this tab's final cell width,
3. Generating the formatted (colored) cells.

### 5.1 Top-Level Decision Tree (Per Tab)

```
on format-tab-title(tab, all_tabs, cfg, hover, max_width):
  active_key_table = cache.current_key_table()         # see §10
  if active_key_table and not tab.is_active:
      return ''                  # hide ALL inactive tabs while a mode is active

  config_max = status_config.tabs.max_width

  window_cols = max(p.left + p.width for p in tab.panes)  # see §5.2

  if window_cols > 0 and not tab.is_active:
      # Compute this inactive tab's allotted width via the layout algorithm
      max_width = layout_inactive_tab_width(
          tab, all_tabs, window_cols, config_max)          # §5.4

  title = create_tab_title(tab, max_width)                 # §5.3
  return render(title, tab, cfg, hover, active_key_table)  # §5.5
```

Notes:

- The active tab always renders. Its width is `config_max` (subject to
  truncation inside `create_tab_title`).
- When `active_key_table` is set, **only the active tab renders**; all other
  tabs collapse to empty strings. The mode-colored segment in the right status
  (§6) carries the affordance instead.

### 5.2 Window-Width Derivation

WezTerm does not pass window cell width into `format-tab-title`. The plugin
derives it by scanning the active tab's panes:

```
window_cols = max over panes of (pane.left + pane.width)
```

This works because panes always tile the full tab. If `tab.panes` is empty
(shouldn't happen in practice), `window_cols == 0` and the plugin skips the
layout step entirely (falls through to default WezTerm behavior).

### 5.3 Tab Title Composition (`create_tab_title`)

Given a tab and a `max_width` (cells), produce the title string **without**
color/styling.

Reserved per-tab budget:

- 2 cells for leading + trailing space (these are added in §5.5, but the budget
  is reserved here)
- `column_width("<index> ")` cells for the leading index (1-based, with one
  trailing space)
- 1 cell for the powerline edge

```
max_length = max_width - 2 - column_width(index_str) - 1
```

Then the title body is chosen from the following priority chain. The **first**
matching rule wins:

#### Rule 1: User-Set Name (Cache Lookup, §10)

Lookup priority:

1. `cache.tab_name(tab.tab_id)`
2. else `cache.pane_name(tab.active_pane.pane_id)`
3. else `tab.tab_title` (WezTerm's user-set tab title)

If any of these returns a non-empty string:

```
body = icons.tabs.tab + ' ' + that_string
```

#### Rule 2: Foreground Process Basename

Let `proc = basename(tab.active_pane.foreground_process_name)`. If
`proc != ''`:

```
body = (process_icon_map[parsed_pane_info.cwd] or icons.tabs.process) + ' ' + proc
```

`process_icon_map` is the table in §5.6.

**Observed quirk:** the icon is looked up by `pane_info.cwd` rather than by
`proc`. In practice `pane_info.cwd` is rarely a process name, so this branch
almost always picks `icons.tabs.process`. The keyed lookup in
`process_icon_map` only fires for very specific built-in titles (e.g.
`C:\WINDOWS\system32\cmd.exe`).

#### Rule 3: Infer From Pane Title

Process basename is empty. Parse the pane title (§5.7) into
`{ cwd, host, mode }`.

- If `cwd == ''`:
  ```
  body = icons.tabs.process + ' ' + tab.active_pane.title
  ```
- Else:
  - If `cwd` starts with `~`, expand to `$HOME + cwd[1:]`.
  - If `pane_info.host` is set (SSH session):
    ```
    body = icons.pane_host.ssh + ' ' + basename(resolve_home_dir(cwd))
    ```
  - Else if `cwd` is a readable directory (`is_dir`, §11):
    - Let `d = basename(resolve_home_dir(cwd))`.
    - If `d == '~'`:
      ```
      body = icons.tabs.home + ' ' + '~'
      ```
    - Else:
      ```
      body = icons.tabs.dir + ' ' + d
      ```
  - Else (cwd is not a directory): take the first whitespace-delimited token of
    `pane_info.cwd` as `proc_name`.
    ```
    body = (process_icon_map[proc_name] or icons.tabs.process) + ' ' + cwd
    ```

#### Extra-Indicator Suffix

After the body is chosen:

- If any pane in `tab.panes` has `is_zoomed == true`: start with ` ` (zoomed
  indicator glyph).
- If `pane_info.mode` is set (the pane is in a key-table mode, e.g.
  copy-mode): append `key_tables[mode].icon`.
- If non-empty, prefix with ` | ` and decrement `max_length` by
  `column_width(extra_icons)` before truncating the body.

#### Final Assembly

```
return index_str
     + truncated_text(body, max_length, status_config.tabs.truncation_point)
     + extra_icons
```

#### 5.3.1 Truncation Algorithm (`truncated_text`)

Inputs: `text`, `max_length` (cells), `truncation_point` (0.0..1.0).

If `column_width(text) <= max_length`, return `text` unchanged.

**Clamp** `truncation_point`:

- Let `min_multiplier = 1 / max_length`.
- If `truncation_point > 1 - min_multiplier`, set to `1`.
- Else if `truncation_point < min_multiplier`, set to `0`.

**Choose ellipsis:**

| `truncation_point` | Ellipsis string |
|---|---|
| `== 0` | `'... '` (ellipsis + space) |
| `== 1` | `' ...'` (space + ellipsis) |
| otherwise | `' ... '` (space + ellipsis + space) |

Let `ell_w = column_width(ellipsis)`, `available = max_length - ell_w`.

```
prefix_length = round(available * truncation_point)    # floor(x + 0.5)
suffix_length = available - prefix_length
```

Build:

```
left  = truncate_right(text, prefix_length)   # keep first prefix_length columns
right = truncate_left(text, suffix_length)    # keep last suffix_length columns
return left + ellipsis + right
```

If `prefix_length == 0`, `left` is empty (front-truncated). If
`suffix_length == 0`, `right` is empty (back-truncated). Default
`truncation_point = 0.4` means ~40% of the kept text is the prefix and ~60% is
the suffix.

### 5.4 Layout Algorithm for Inactive Tabs

When there are multiple tabs and the window is narrow, the plugin
re-distributes width across inactive tabs. The active tab is always rendered at
`config_max` (it never shrinks). The algorithm runs only for **inactive** tabs,
and each inactive tab's handler computes the **whole** layout from scratch
(because WezTerm calls the formatter once per tab independently).

#### 5.4.1 Inputs and Budget

- `config_max` = `status_config.tabs.max_width`.
- `active_tab_width` = rendered width of the active tab via
  `tab_rendered_width(active_tab, config_max)` (see §5.4.2).
- `right_width` = `cache.right_status_width()` (cells consumed by the right-
  side status from the previous `update-status` event, §6.6).
- `available_total = window_cols - right_width - 4` (the `4` reserves 3 cells
  for the WezTerm `+` button and 1 cell of gap).
- `available_inactive = available_total - active_tab_width`.

#### 5.4.2 Natural Width Per Tab

`tab_rendered_width(t, width_cap)`:

1. `title = create_tab_title(t, width_cap)` (§5.3).
2. Return `column_width(title) + 3` (1 leading space + 1 trailing space +
   1 powerline edge).

Build:

```
inactive_tabs = [
  { tab_id, width: tab_rendered_width(t, config_max) }
  for each inactive t
]
total_needed = sum of widths
```

#### 5.4.3 Branches

**Branch A:** `total_needed <= available_inactive`. Plenty of space. No
equalization, no scrolling. `cache.clear_scroll_state()`. The current inactive
tab keeps its natural width.

**Branch B:** `total_needed > available_inactive`. Call
`equalize_tab_widths(inactive_tabs, available_inactive)` (§5.4.4). Then check
if any resulting `width < MIN_TAB_WIDTH`:

- If **no** tab fell below the floor, accept the equalized widths and
  `clear_scroll_state()`.
- If **any** tab is below `MIN_TAB_WIDTH`, switch to scrolling (§5.4.5).

After the layout decides the current tab's final allotted width, the formatter
sets `max_width = max(inactive_tabs[current_idx].width, MIN_TAB_WIDTH)` and
passes it to `create_tab_title` in §5.1.

#### 5.4.4 Equalization (`equalize_tab_widths`)

Inputs: `tab_widths[]` (each `{ width }`, with optional `natural` written by
the algorithm), `available` (cells).

```
total = sum(tw.width for tw in tab_widths)
if total <= available: return     # nothing to do

min_w = min(tw.width for tw in tab_widths)
N = len(tab_widths)

# Phase 1: floor everyone to the smallest natural width.
for tw in tab_widths:
    tw.natural = tw.width
    tw.width   = min_w
equalized_sum = min_w * N

if equalized_sum <= available:
    # Phase 2a: hand width back, left-to-right, up to each tab's natural width.
    remaining = available - equalized_sum
    for tw in tab_widths:
        add = min(tw.natural - tw.width, remaining)
        tw.width += add
        remaining -= add
        if remaining <= 0: break
else:
    # Phase 2b: still too wide. Shrink uniformly below min_w.
    overflow       = equalized_sum - available
    base_reduction = floor(overflow / N)
    extra          = overflow - base_reduction * N      # 0..N-1
    for tw in tab_widths: tw.width = min_w - base_reduction
    # Distribute the remainder one cell at a time, RIGHT to LEFT.
    for i in [N-1, N-2, ..., N-extra]:
        tab_widths[i].width -= 1
```

Property: after the call, `sum(tw.width) == available` whenever
`equalized_sum > available` (the function fully consumes the budget); otherwise
the sum may be `<= available`.

#### 5.4.5 Scrolling (Visible Window)

Triggered when equalization would push some inactive tab below
`MIN_TAB_WIDTH = 12`. Goal: render only a contiguous range `[L, R]` (1-based
indices into `all_tabs`) that always contains the active tab, plus chevron
indicators on the endpoints if hidden tabs exist on that side.

```
visible_tab_range(tabs, active_idx, active_width, available_total) -> (L, R):
  L = R = active_idx
  visible_sum = active_width

  loop:
      expanded = false
      left_count  = active_idx - L
      right_count = R - active_idx

      if left_count <= right_count:
          # try left first (bias toward centering)
          if L > 1 and visible_sum + MIN_TAB_WIDTH <= available_total:
              L -= 1; visible_sum += MIN_TAB_WIDTH; expanded = true
          if R < len(tabs) and visible_sum + MIN_TAB_WIDTH <= available_total:
              R += 1; visible_sum += MIN_TAB_WIDTH; expanded = true
      else:
          # try right first
          if R < len(tabs) and visible_sum + MIN_TAB_WIDTH <= available_total:
              R += 1; visible_sum += MIN_TAB_WIDTH; expanded = true
          if L > 1 and visible_sum + MIN_TAB_WIDTH <= available_total:
              L -= 1; visible_sum += MIN_TAB_WIDTH; expanded = true

      if not expanded: break

  return L, R
```

Then:

1. First pass:
   `L, R = visible_tab_range(tabs, active_idx, active_tab_width, available_total)`.
2. `has_left = L > 1`, `has_right = R < len(tabs)`.
   `indicator_cols = (has_left ? 1 : 0) + (has_right ? 1 : 0)`.
3. If `indicator_cols > 0`, recompute the range against
   `available_total - indicator_cols` (room for chevrons), then refresh
   `has_left` / `has_right` / `indicator_cols`.
4. Persist
   `cache.store_scroll_state(tabs[L].tab_id, tabs[R].tab_id, has_left, has_right)`
   so all tab formatters can see it during this render cycle.
5. If this tab's index in `all_tabs` falls outside `[L, R]`, return `''`
   (hide it).
6. Rebuild `inactive_tabs` for indices in `[L, R]` excluding the active one.
   Run `equalize_tab_widths(inactive_tabs, available_inactive - indicator_cols)`
   once more so the visible tabs evenly fill the available space.

If scrolling was not needed (Branch B's equalized result was OK),
`cache.clear_scroll_state()` so nothing renders chevrons.

### 5.5 Tab Rendering (Cells, Colors, Glyphs)

Given the computed `title`, the formatter emits a sequence of styled cells:

```
edge_bg    = cfg.colors.tab_bar.background
bg         = cfg.colors.tab_bar.inactive_tab.bg_color
fg         = cfg.colors.tab_bar.inactive_tab.fg_color
edge_glyph = U+258C                                   # left-half-block

if tab.is_active:
    bg = cfg.colors.tab_bar.active_tab.bg_color
    fg = cfg.colors.tab_bar.active_tab.fg_color
elif hover:
    bg = cfg.colors.tab_bar.inactive_tab_hover.bg_color
    fg = cfg.colors.tab_bar.inactive_tab_hover.fg_color

if active_key_table:               # mode is active; only the active tab here
    edge_glyph = NerdFont ple_right_half_circle_thick
    if status_config.key_tables[active_key_table]:
        bg = parse_color(status_config.key_tables[active_key_table].color)
        fg = bg.darken(0.8)
        if contrast_ratio(bg, fg) < 3.8: fg = bg.lighten(0.6)

edge_fg = bg
```

Cell sequence:

1. **Left scroll chevron**: if `scroll.has_left` and
   `tab.tab_id == scroll.first`, emit
   `bg=edge_bg, fg=fg, text=NerdFont fa_chevron_left`. Else omit.
2. `Attribute(Intensity=Bold)`, `bg=bg`, `fg=fg`, `text=' ' + title + ' '`.
3. `bg=edge_bg`, `fg=edge_fg`, `text=edge_glyph`. This is the powerline-style
   edge after the tab.
4. **Right scroll chevron**: if `scroll.has_right` and
   `tab.tab_id == scroll.last`, emit
   `fg=fg, text=NerdFont fa_chevron_right`. Else omit.
5. `Attribute(Intensity=Normal)`.

The output is returned as the formatter's "FormatItems" array (WezTerm-specific
shape). A non-WezTerm port should produce the same logical run of styled cells.

### 5.6 Process-Icon Mapping (`tabs.M.icons`)

Hardcoded inside `tabs.lua` (not user-configurable today):

| Key | NerdFont Identifier |
|---|---|
| `C:\WINDOWS\system32\cmd.exe` | `md_console_line` |
| `Topgrade` | `md_rocket_launch` |
| `bash` | `cod_terminal_bash` |
| `btm` | `mdi_chart_donut_variant` |
| `cargo` | `dev_rust` |
| `curl` | `mdi_flattr` |
| `docker` | `linux_docker` |
| `docker-compose` | `linux_docker` |
| `fish` | `md_fish` |
| `gh` | `dev_github_badge` |
| `git` | `dev_git` |
| `go` | `seti_go` |
| `htop` | `md_chart_areaspline` |
| `btop` | `md_chart_areaspline` |
| `kubectl` | `linux_docker` |
| `kuberlr` | `linux_docker` |
| `lazydocker` | `linux_docker` |
| `lazygit` | `cod_github` |
| `lua` | `seti_lua` |
| `make` | `seti_makefile` |
| `node` | `mdi_hexagon` |
| `nvim` | `custom_vim` |
| `pacman` | literal glyph U+F0BAF + trailing space |
| `paru` | literal glyph U+F0BAF + trailing space |
| `psql` | `dev_postgresql` |
| `pwsh.exe` | `md_console` |
| `ruby` | `cod_ruby` |
| `sudo` | `fa_hashtag` |
| `vim` | `dev_vim` |
| `wget` | `mdi_arrow_down_box` |
| `zsh` | `dev_terminal` |
| `Debug` | `cod_debug` |
| `brew` | `md_beer_outline` |

Lookup keys are case-sensitive and matched as exact strings.

### 5.7 Pane-Title Parsing (`parse_pane_title`)

WezTerm's built-in pane title follows a roughly fixed shape:
`<target>: <directory>`, where `<target>` may be `Copy mode`, `user@host`, or
just a label.

```
parse_pane_title(title) -> { cwd, host, mode } | nil:
  if title is nil or '': return nil
  mode = cache.current_key_table()                # may be nil
  host = nil

  (target, dir) = match(title, /^([^:]+):\s*(.*)$/)

  if target == 'Copy mode':
      # strip the 'Copy mode: ' wrapper, parse the inner title
      title = dir
      (target, dir) = match(title, /^([^:]+):\s*(.*)$/)

  if target and dir:
      (username, hostname) = match(target, /^([^@]+)@(.*)$/)
      if username and hostname:
          host = { username, hostname }
  else:
      dir = title

  return { cwd = dir, host = host, mode = mode }
```

`mode` is **not** parsed out of the title (despite the title carrying that
information); it is always taken from `cache.current_key_table()`. The
"Copy mode" prefix is stripped so the inner cwd/host can still be parsed.

---

## 6. Right-Side Status Segments

Emitted by `update_status(window, _pane)` on every `update-status` event.

```
update_status(window):
  cache.store_current_key_table(window:active_key_table())
  window:set_left_status('')
  (right_status, right_width) = build_right_status(window)
  cache.store_right_status_width(right_width)       # consumed by tab layout (§5.4.1)
  window:set_right_status(right_status)
```

### 6.1 Determining the Status Mode

```
if window:leader_is_active(): status_mode = 'command'
else: status_mode = cache.current_key_table() or 'workspace'
```

This is the key driving the **color** and the **mode segment** of the right-
side bar.

### 6.2 Color Gradient

```
base_color = mode_color(status_mode, color_scheme)
tab_bg     = color_scheme.tab_bar.background
colors     = color_gradient(
                { colors = { base_color, tab_bg } },
                5)                          # array of 5 colors, interpolated
```

`mode_color(kt, scheme)` returns:

- `parse_color(scheme.tab_bar.inactive_tab.bg_color)` if `kt` has no key-table
  config **or** `kt == 'workspace'`.
- Else `parse_color(status_config.key_tables[kt].color)`.

Convention: `colors[1]` is closest to the mode color (used by the rightmost,
"loudest" segment) and `colors[5]` equals `tab_bg` (background fill).
Intermediate colors form a smooth fade.

### 6.3 Segment Layout

Two layouts, picked by `window:get_dimensions().is_full_screen`:

**Windowed (not full screen):**

```
[ tab_bar bg | divider | mode | divider | pane_host ]
```

Backgrounds used:

- `bg3 = colors[1]`, `bg4 = colors[2]`. `first_segment = 2`.
- Mode segment background = `bg4`, pane_host background = `bg3`.

**Fullscreen:**

```
[ tab_bar bg | divider | mode | divider | pane_host | divider | battery wifi | divider | time ]
```

Backgrounds:

- `bg1 = colors[1]`, `bg2 = colors[2]`, `bg3 = colors[3]`, `bg4 = colors[4]`.
  `first_segment = 4`.
- Mode bg = `bg4`, pane_host bg = `bg3`, battery + wifi bg = `bg2`,
  time bg = `bg1`.

The base `bg = colors[5]` is the "fade-out" background flush against the rest
of the tab bar; it's never used for content, only for the leading divider.

#### 6.3.1 Segment Elision Rules

- If `pane_host` returns width 0 (no remote host, see §6.4.2): collapse `bg4`
  to equal `bg3` and decrement `first_segment` by 1. The mode segment then
  sits directly against the right of the fade.
- If `mode` returns width 0 (workspace=default, no key table) **and**
  `pane_host` width 0: no left "block" exists; in fullscreen the right block
  (battery/wifi/time) is preceded by a single divider from `bg` to `bg2`
  instead of the chain.

Concretely the four cases the code emits:

| mode | pane_host | Emitted left block |
|---|---|---|
| present | present | `div(bg, colors[fs])` + mode + `div(colors[fs], colors[fs-1])` + pane_host |
| present | absent | `div(bg, colors[fs])` + mode |
| absent | present | `div(bg, colors[fs])` + pane_host |
| absent | absent | empty |

(`fs` = `first_segment`)

For fullscreen, the right block is appended after the left block:

```
if left_block non-empty:
    status += div(bg3, bg2) + battery + wifi + div(bg2, bg1) + time
else:
    status  = div(bg,  bg2) + battery + wifi + div(bg2, bg1) + time
```

### 6.4 Per-Segment Specifications

Every segment is rendered through `format_segment(color, text, last_segment)`:

- Foreground = `color.darken(0.8)`; if `contrast_ratio(color, fg) < 3.8`,
  foreground becomes `color.lighten(0.6)` instead.
- Body = `' ' + text + (' ' if not last_segment else '')` — i.e. all segments
  have a leading space; only the last segment in a chain has no trailing space
  (the trailing space is replaced by the next divider).
- Returns `(formatted_string, column_width(body))`.

Dividers use `DIVIDER_GLYPH` (`ple_lower_right_triangle`) with
`Background=left_color`, `Foreground=right_color`. Width = `DIVIDER_WIDTH`.

#### 6.4.1 Mode Segment

```
mode(window, key_table, color, last_segment) -> (text, width):
  active = status_config.key_tables[key_table]
  ws_name = window:active_workspace()

  if active is nil or (key_table == 'workspace' and ws_name == 'default'):
      return ('', 0)                       # suppressed

  ws_name = cache.workspace_name(ws_name) or ws_name

  label = (key_table == 'workspace')
        ? ws_name
        : (active.label or key_table)

  if active.icon: label = active.icon + ' ' + label

  return format_segment(color, label, last_segment)
```

Behaviors:

- Workspace named `default` produces no segment.
- Workspace renaming via `cache.workspace_name(ws_name)` (see §10): if a
  friendly name was registered for the workspace id, that's shown instead.
- Other key tables: icon + label, where label falls back to the key-table name
  if `label` is nil.
- The `command` mode appears when `window:leader_is_active()` (driven by §6.1)
  — there is no actual `command` key table in WezTerm; the plugin synthesizes
  it.

#### 6.4.2 Pane Host (SSH) Segment

```
pane_host(window, color, last_segment) -> (text, width):
  pane = window:active_pane()
  info = pane and parse_pane_title(pane:get_title())
  if not info.host: return ('', 0)
  return format_segment(
      color,
      icons.pane_host.ssh + ' ' + info.host.hostname,
      last_segment)
```

Only emitted when the parsed pane title contains `user@host:`. The hostname is
rendered; the username is parsed but **not** displayed.

#### 6.4.3 Battery Segment

Active only in fullscreen layout (the function is called from the fullscreen
branch).

```
is_macos_laptop_cached():
  if cached: return cached
  (ok, stdout) = run_child_process(['sysctl', '-n', 'hw.model'])
  cached = ok and 'MacBook' in stdout
  return cached

battery(color, last_segment) -> (text, width):
  if not is_macos_laptop_cached():
      # static desktop icon for non-laptop machines
      return format_segment(color, icons.pane_host.host, last_segment)

  b = battery_info()[0]                    # primary battery
  if b.state_of_charge is nil:
      return ('', 0)                       # silent if missing

  if b.state == 'Full':
      pct  = '100%'
      icon = icons.battery.charging[4]
  else:
      v = (b.state_of_charge > 0)
        ? round(b.state_of_charge * 100)
        : 0
      pct  = str(v) + '%'
      icon = icons.battery.discharging[
             4 if v >= 90 else
             3 if v >= 40 else
             2 if v >  5 else
             1]

  return format_segment(color, pct + ' ' + icon, last_segment)
```

**Observed quirks:**

- Laptop check is macOS-only (relies on `sysctl hw.model` containing
  "MacBook"). On Linux laptops, the segment renders the static "host" icon as
  if it were a desktop, regardless of battery presence. A correct cross-
  platform port must detect "is a battery present" instead.
- The result of `is_macos_laptop_cached()` is memoized for the lifetime of the
  WezTerm process; hot-swappable batteries / dock changes are not reconsidered.
- `icons.battery.charging[1..3]` are configurable but never rendered: in any
  non-Full charging state the code currently picks from `discharging`. Only
  `charging[4]` (the 100%/Full glyph) is ever shown.
- Boundary inclusivity: `>=90`, `>=40`, `>5` (strictly greater). Values 1-5
  use level-1 (lowest). 0 also uses level-1.

#### 6.4.4 WiFi Segment

Active only in fullscreen layout.

```
wifi_enabled (closure with 10-second TTL cache):
  on darwin (macOS):
      iface = first device under 'Hardware Port: Wi-Fi'
              in `networksetup -listallhardwareports`
      run `networksetup -getairportpower <iface>`
      status = output contains 'On'
  else (Linux):
      run `nmcli radio wifi`
      status = output starts with 'enabled'

  cache result for 10 seconds
  return status

wifi(color, last_segment):
  glyph = wifi_enabled() ? icons.wifi.active : icons.wifi.inactive
  return format_segment(color, glyph + ' ', last_segment)
```

**Observed quirks:**

- macOS interface detection is also memoized for the WezTerm process lifetime
  (the closure caches `wifi_interface` once it finds one).
- Linux check requires `nmcli` (NetworkManager); systems without it report
  inactive.
- Windows and other OSes: always inactive.
- The segment renders the icon plus a trailing space; `format_segment` adds its
  own leading/trailing space, so the effective body is `' <glyph>  '` when not
  the last segment.

#### 6.4.5 Time Segment

Active only in fullscreen layout. Always the last segment.

```
time(color, last_segment):
  return format_segment(
      color,
      icons.time.calendar + ' ' + strftime('%a %b %-e %-l:%M%P'),
      last_segment)
```

Format string breakdown:

| Specifier | Meaning | Example |
|---|---|---|
| `%a` | abbreviated weekday name | `Fri` |
| `%b` | abbreviated month name | `May` |
| `%-e` | day of month (no leading zero) | `23` |
| `%-l` | 12-hour hour (no leading zero) | `5` |
| `%M` | minute (zero-padded) | `42` |
| `%P` | lower-case am/pm | `pm` |

Full example: `Fri May 23 5:42pm`.

`last_segment` is `true` here, so no trailing space. The plugin does not
register a refresh timer; the clock advances at WezTerm's natural
`update-status` cadence (typically once per second).

### 6.5 Left Status

Always cleared: `window:set_left_status('')`. The plugin does not use the left
status.

### 6.6 Width Propagation

After rendering, `total_width` (the cell width of everything
`set_right_status` will display) is stored via
`cache.store_right_status_width(width)`. The tab-layout algorithm reads this
back on the next `format-tab-title` to know how much horizontal space the tabs
may consume.

This is a deliberate one-frame lag: tab layout in frame *N* uses the right-
status width from frame *N-1*. In practice this is invisible because the right
status changes slowly relative to redraw rate.

---

## 7. Color & Contrast Handling

A re-implementation needs:

- **Color parsing** equivalent to WezTerm's `wezterm.color.parse` (CSS-like
  hex, `rgb()`, and named colors). The plugin parses user-provided `color`
  strings and the color scheme's `tab_bar.*.bg_color` / `fg_color`.
- **HSL-style darken/lighten**: `c.darken(0.8)` reduces lightness by 80%,
  `c.lighten(0.6)` raises it by 60%. (Both are WezTerm's built-ins; a clone
  should match their behavior closely enough for visual parity.)
- **Contrast ratio** following WCAG (the algorithm WezTerm uses). The threshold
  `3.8` is the plugin's switching point: if `darken(0.8)` doesn't produce
  >=3.8 contrast against the segment background, the plugin falls back to
  `lighten(0.6)`.
- **Color gradient** with linear interpolation of 5 stops between two colors
  (RGB or HSL — WezTerm's `wezterm.color.gradient` defaults to perceptual
  interpolation; visual parity is sufficient).

This produces the "fade from mode color to tab-bar background" effect across
the right-side segments.

---

## 8. Glyphs (Full Inventory)

Every NerdFont identifier the plugin uses, by source location:

| Identifier | Where Used |
|---|---|
| `ple_lower_right_triangle` | Segment dividers (§6.4) |
| `ple_right_half_circle_thick` | Tab edge when a key table is active (§5.5) |
| `fa_chevron_left` | Left scroll indicator (§5.5 / §5.4.5) |
| `fa_chevron_right` | Right scroll indicator (§5.5 / §5.4.5) |
| `fa_search` | Default search-mode icon |
| `md_apple_keyboard_command` | Default command/leader icon |
| `md_collage` | Default workspace icon |
| `md_content_copy` | Default copy-mode icon |
| `md_remote_desktop` | SSH/pane_host icon |
| `md_desktop_classic` | Non-laptop "host" icon (battery slot replacement) |
| `md_folder_open`, `md_home`, `md_run`, `md_tab` | Tab body icons |
| `md_calendar_clock` | Clock icon |
| `md_wifi`, `md_wifi_strength_off_outline` | WiFi on/off |
| `md_battery_*` (8 glyphs) | Battery icons |
| All process icons in §5.6 | Process-aware tab body icon |
| `U+258C` (left half block) | Tab right edge in normal mode |
| Zoomed-pane indicator glyph | Pane-zoomed indicator suffix in tab title |

A non-NerdFont environment must substitute glyphs of comparable width or
accept that segments will misalign.

---

## 9. Platform Notes (Current Support Matrix)

| Concern | macOS | Linux | Windows |
|---|---|---|---|
| Plugin load via wezterm.plugin | Yes | Yes | Yes (path separator handled) |
| Tab rendering, modes, time, gradient | Yes | Yes | Yes |
| Pane host / SSH detection | Yes | Yes | Yes (relies only on pane title) |
| Battery accuracy | MacBook only | No (shows static "host" icon) | No (shows static "host" icon) |
| WiFi accuracy | Yes (via `networksetup`) | Yes (if `nmcli` available) | No (always inactive) |
| `is_dir` (CWD vs process in tab title) | Yes (POSIX `EISDIR == 21`) | Yes | Partial (see §11) |

---

## 10. Naming Cache (State Model)

State lives in a process-global shared table. Schema:

```
sb_plugin = {
  _workspaces: { [workspace_id: string]: string },     # display name
  _tabs:       { [tab_id_as_string: string]: string },
  _panes:      { [pane_id_as_string: string]: string },
  _key_table:           string?,   # last seen active_key_table()
  _right_status_width:  number?,   # last rendered right-status width (cells)
  _scroll: {                       # nil when scrolling is not active
    first:     number,             # tab_id of leftmost visible inactive tab
    last:      number,             # tab_id of rightmost visible inactive tab
    has_left:  boolean,
    has_right: boolean,
  }?
}
```

Public surface (the module exported as `statusbar.naming_cache`):

| Function | Signature |
|---|---|
| `store_workspace_name` | `(workspace_id: string, name: string)` |
| `store_tab_name` | `(tab_id: number, name: string)` |
| `store_pane_name` | `(pane_id: number, name: string)` |
| `workspace_name` | `(workspace_id: string) -> string?` |
| `tab_name` | `(tab_id: number) -> string?` |
| `pane_name` | `(pane_id: number) -> string?` |
| `current_key_table` | `() -> string?` |

The plugin does **not** ship any keybindings or UI flows for setting these
names. Users wire their own commands and call into the store functions from
their terminal config. The lookup priority for the tab title is documented in
§5.3 Rule 1.

State is **process-global**, not persisted: it is reset every time the host
terminal starts.

---

## 11. Misc Utilities (`utils`)

| Function | Signature | Notes |
|---|---|---|
| `truncated_text` | `(text, max_length, truncation_point?) -> string` | §5.3.1 |
| `basename` | `(path) -> string` | Last segment after `/` or `\`. Pure string transform. |
| `resolve_home_dir` | `(path) -> string` | Replaces leading `$HOME` with `~`. If the substitution produces empty string, returns the original. |
| `is_dir` | `(path) -> boolean` | Opens the path read-only; calls `read(1)`; checks the OS error code returned. Returns `true` iff error code is `21` (`EISDIR` on Linux/macOS). On Windows this constant is wrong; re-implementations should use a proper `stat` / `GetFileAttributes` check. |
| `parse_pane_title` | `(title) -> { cwd, host, mode }?` | §5.7 |

---

## 12. Invariants & Edge Cases

1. **Active tab is always visible.** No code path hides it. When a key table is
   active, the active tab is the **only** tab rendered.
2. **`tab_max_width` is a hard cap on individual tab width**, enforced by the
   host terminal (plugin sets the config), not by the formatter. The formatter
   may shrink below it.
3. **`MIN_TAB_WIDTH = 12`** is the floor that triggers scrolling. It is not
   configurable.
4. **The "+ new tab" button** is reserved 3 cells; the gap before the right
   status is 1 cell. Together: 4 cells of padding past the right status width.
   This is hardcoded.
5. **Workspace named `default`** never renders a mode segment.
6. **Leader key wins over key tables.** While leader is active, the displayed
   mode is `command` even if a key table is also active. (In WezTerm, leader is
   usually a transient prefix; the cache key-table value persists.)
7. **Search and Copy mode tab indicators** are added to inactive-tab titles via
   `pane_info.mode`, but since `pane_info.mode` is sourced from
   `cache.current_key_table()` (not from per-pane state), all inactive tabs in
   the window will display the same suffix while a mode is active. Combined
   with invariant 1 (inactive tabs hidden in modes), this code path effectively
   only matters for transient state.
8. **No periodic refresh.** Everything updates only when the host terminal fires
   `update-status` or redraws tabs. WiFi has its own 10-second TTL inside the
   closure but only re-runs the shell command when the segment is rendered
   after the TTL.
9. **Empty/missing pane title** in tab title resolution causes the
   `parse_pane_title` chain to short-circuit and fall back to the foreground
   process basename or the pane title directly (§5.3 rules 2-3).
10. **`window_cols == 0`** (e.g. very early in startup before panes have
    geometry) disables the entire layout algorithm for that frame; tabs render
    at their natural width up to `config_max`.

---

## 13. What the Plugin Explicitly Does NOT Do

These are notable absences in the current implementation. A re-implementation
is free to add them, but they are not required for behavioral parity:

- No left-side status content.
- No mouse-driven actions (no click-to-rename, no click-to-scroll). All input
  is via the user's own keybindings.
- No persistence of naming cache across restarts.
- No CPU / memory / load / git-branch / language-version segments.
- No theming hooks beyond the per-mode `color` field and the host terminal's
  color scheme.
- No support for non-NerdFont fallback glyphs.
- No localization of `%a`, `%b`, `am/pm`; uses the host's locale defaults via
  `strftime`.
- No event hook other than `update-status` and `format-tab-title`. The plugin
  does not react to `window-resized`, `window-config-reloaded`, etc.

---

## 14. Re-Implementation Checklist

To bring up an equivalent feature set on another host:

1. Provide a config object matching §3.1 with defaults from §3.2.
2. Hook the host's "render tab title" event with the algorithm in §5 (including
   the equalization + scrolling math, which is the most intricate part of the
   plugin).
3. Hook the host's "redraw status" event with the algorithm in §6.
4. Provide color parsing, `darken`/`lighten`, contrast ratio, and a 5-stop
   gradient (§7).
5. Provide platform-specific battery detection and WiFi state with caching
   (§6.4.3, §6.4.4) — and **fix** the laptop-detection quirk if cross-platform
   parity matters.
6. Provide a shared key-value store for the naming cache (§10) and expose the
   same six setters/getters.
7. Provide a NerdFont (or substitute glyphs of comparable width) — see §8.

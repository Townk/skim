# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Shared reusable TUI widgets for skim configuration editor."""

from __future__ import annotations

import re
from typing import Any

from textual import events
from textual.actions import SkipAction
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Button, Footer, Input, ListView, Select, Switch, Tabs
from textual.widgets._footer import FooterKey
from textual.widgets._select import SelectCurrent, SelectOverlay

# ---------------------------------------------------------------------------
# Custom footer with standardised binding order and paired display
# ---------------------------------------------------------------------------

# Sort priority for actions.  Lower value → further left in the footer.
_ACTION_ORDER: dict[str, int] = {
    "show_help": -1,
    # Always-visible (app-level)
    "request_quit": 0,
    "save": 1,
    "previous_tab": 2,
    "next_tab": 3,
    "scroll_view('up')": 4,
    "scroll_view('down')": 5,
    "focus_previous": 6,
    "focus_next": 7,
    # Per-widget
    "press": 10,
    "toggle_switch": 10,
    "show_overlay": 10,
    "select": 11,
    "dismiss": 12,
    "cursor_up": 13,
    "select_cursor": 14,
    # HSL nudge (before submit so they sit left of "Confirm changes")
    "nudge_saturation_up": 18,
    "nudge_saturation_down": 18,
    "nudge_lightness_up": 19,
    "nudge_lightness_down": 19,
    # Edit-pane
    "submit": 20,
    "cancel_edit": 21,
}

# Pairs rendered with "/" between key displays.
# Maps first_action → (second_action, combined_description).
_PAIRS: dict[str, tuple[str, str]] = {
    "previous_tab": ("next_tab", "Prev/Next tab"),
    "scroll_view('up')": ("scroll_view('down')", "Scroll up/down"),
    "focus_previous": ("focus_next", "Prev/Next field"),
    "cursor_up": ("cursor_down", "Prev/Next item"),
    "nudge_saturation_up": ("nudge_saturation_down", "Sat +/-"),
    "nudge_lightness_up": ("nudge_lightness_down", "Lum +/-"),
}

# Second actions in pairs — skipped during individual rendering.
_PAIR_SECONDS: set[str] = {v[0] for v in _PAIRS.values()}


class SkimFooter(Footer):
    """Footer with controlled binding order and paired key display."""

    def _yield_key(
        self,
        key: str,
        key_display: str,
        description: str,
        action: str,
        *,
        enabled: bool = True,
        tooltip: str = "",
    ) -> FooterKey:
        return FooterKey(
            key,
            key_display,
            description,
            action,
            disabled=not enabled,
            tooltip=tooltip,
        ).data_bind(compact=Footer.compact)

    def compose(self) -> ComposeResult:
        if not self._bindings_ready:
            return

        active = self.screen.active_bindings

        # Collect one representative binding per action.
        by_action: dict[str, tuple[Binding, bool, str]] = {}
        for _key, (_node, binding, enabled, tooltip) in active.items():
            if not binding.show:
                continue
            if binding.action not in by_action:
                by_action[binding.action] = (binding, enabled, tooltip)

        default_order = max(_ACTION_ORDER.values()) + 1
        sorted_actions = sorted(
            by_action,
            key=lambda a: _ACTION_ORDER.get(a, default_order),
        )

        for action in sorted_actions:
            if action in _PAIR_SECONDS:
                continue

            binding, enabled, tooltip = by_action[action]

            if action in _PAIRS:
                second_action, description = _PAIRS[action]
                if second_action in by_action:
                    second_binding = by_action[second_action][0]
                    key_display = (
                        self.app.get_key_display(binding)
                        + "/"
                        + self.app.get_key_display(second_binding)
                    )
                    yield self._yield_key(
                        binding.key,
                        key_display,
                        description,
                        binding.action,
                        enabled=enabled,
                    )
                    continue

            yield self._yield_key(
                binding.key,
                self.app.get_key_display(binding),
                binding.description,
                binding.action,
                enabled=enabled,
                tooltip=tooltip,
            )

        # Inject tab-bar bindings when a Tabs widget is focused.
        focused = self.screen.focused
        if isinstance(focused, Tabs):
            yield self._yield_key("down", "\u2193", "Next field", "")
            yield self._yield_key(
                "left",
                "\u2190/\u2192",
                "Prev/Next tab",
                "",
            )


# ---------------------------------------------------------------------------
# Widget classes
# ---------------------------------------------------------------------------


class SkimStandaloneInput(Input):
    """Input for standalone fields outside edit panes."""

    BINDINGS = [
        Binding("tab", "focus_next", "Next field", key_display="\u2193,\u21e5", show=True),
        Binding(
            "shift+tab", "focus_previous", "Previous field", key_display="\u2191,\u21e4", show=True
        ),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key


_COLOR_NUDGE_BINDINGS: list[Binding] = [
    Binding(
        "alt+up",
        "nudge_saturation_up",
        "Sat +",
        key_display="\u2325\u2191",
        show=True,
        priority=True,
    ),
    Binding(
        "alt+down",
        "nudge_saturation_down",
        "Sat -",
        key_display="\u2325\u2193",
        show=True,
        priority=True,
    ),
    Binding(
        "alt+right",
        "nudge_lightness_up",
        "Lum +",
        key_display="\u2325\u2192",
        show=True,
        priority=True,
    ),
    Binding(
        "alt+left",
        "nudge_lightness_down",
        "Lum -",
        key_display="\u2325\u2190",
        show=True,
        priority=True,
    ),
]

_HSL_STEP = 0.05
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _nudge_color(
    widget: Any, *, saturation_delta: float = 0.0, lightness_delta: float = 0.0
) -> None:
    """Apply an HSL nudge to *widget*.value if it is a valid 6-digit hex color."""
    from skim.application.render.styling import nudge_color_hsl

    current = (widget.value or "").strip()
    if not _HEX_RE.match(current):
        return
    try:
        widget.value = nudge_color_hsl(
            current,
            saturation_delta=saturation_delta,
            lightness_delta=lightness_delta,
        )
    except Exception:
        return


class ColorInput(SkimStandaloneInput):
    """SkimStandaloneInput with shortcuts to nudge the color's HSL channels.

    ``alt+up`` / ``alt+down`` increase / decrease saturation; ``alt+right``
    / ``alt+left`` increase / decrease lightness. Each press applies a
    0.05 delta clamped into ``[0, 1]``. Non-hex values (empty input,
    named CSS colors, malformed strings) are silently ignored — the
    binding is a no-op.

    The footer renders two grouped cells using ``SkimFooter._PAIRS``:
    one for the saturation pair and one for the lightness pair, with
    the standard yellow-key / white-description styling.
    """

    BINDINGS = list(_COLOR_NUDGE_BINDINGS)

    def action_nudge_saturation_up(self) -> None:
        _nudge_color(self, saturation_delta=_HSL_STEP)

    def action_nudge_saturation_down(self) -> None:
        _nudge_color(self, saturation_delta=-_HSL_STEP)

    def action_nudge_lightness_up(self) -> None:
        _nudge_color(self, lightness_delta=_HSL_STEP)

    def action_nudge_lightness_down(self) -> None:
        _nudge_color(self, lightness_delta=-_HSL_STEP)


class SkimInput(Input):
    """Input with footer bindings for edit-pane field navigation."""

    BINDINGS = [
        Binding("tab", "focus_next", "Next field", key_display="\u2193,\u21e5", show=True),
        Binding(
            "shift+tab", "focus_previous", "Previous field", key_display="\u2191,\u21e4", show=True
        ),
        Binding("enter", "submit", "Confirm changes", key_display="\u23ce", show=True),
        Binding("escape", "cancel_edit", "Discard changes", key_display="\U000f12b7", show=True),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key

    def action_cancel_edit(self) -> None:
        """No-op — handled by ListDetailPane.on_key via event bubbling."""


class LayerColorInput(SkimInput):
    """SkimInput variant with HSL-nudge shortcuts (Layer Colors edit pane)."""

    BINDINGS = list(_COLOR_NUDGE_BINDINGS)

    def action_nudge_saturation_up(self) -> None:
        _nudge_color(self, saturation_delta=_HSL_STEP)

    def action_nudge_saturation_down(self) -> None:
        _nudge_color(self, saturation_delta=-_HSL_STEP)

    def action_nudge_lightness_up(self) -> None:
        _nudge_color(self, lightness_delta=_HSL_STEP)

    def action_nudge_lightness_down(self) -> None:
        _nudge_color(self, lightness_delta=-_HSL_STEP)


class SkimListView(ListView):
    """ListView with footer bindings for navigation and edit."""

    BINDINGS = [
        # Normal mode
        Binding("up", "cursor_up", "Prev item", show=True),
        Binding("down", "cursor_down", "Next item", show=True),
        Binding("enter", "select_cursor", "Edit", key_display="\u23ce", show=True),
        Binding("m", "move_mode", "Move", show=True),
        # Move mode (toggled via check_action)
        Binding("up", "move_up", "Move up", show=True),
        Binding("down", "move_down", "Move down", show=True),
        Binding("enter", "confirm_move", "Confirm position", key_display="\u23ce", show=True),
        Binding("escape", "cancel_move", "Discard changes", key_display="\U000f12b7", show=True),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key

    def _parent_pane(self):
        """Find the parent ListDetailPane, if any."""
        from skim.tui.list_detail_pane import ListDetailPane

        node = self.parent
        while node is not None:
            if isinstance(node, ListDetailPane):
                return node
            node = node.parent
        return None

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        pane = self._parent_pane()
        moving = pane is not None and pane._moving
        move_supported = pane is not None and pane.move_enabled
        normal_actions = {"cursor_up", "cursor_down", "select_cursor"}
        move_actions = {"move_up", "move_down", "confirm_move", "cancel_move"}
        if action == "move_mode":
            return move_supported and not moving
        if action in normal_actions:
            return not moving
        if action in move_actions:
            return moving
        return True

    def action_move_mode(self) -> None:
        """No-op — handled by LayerListPane.on_key via event bubbling."""

    def action_move_up(self) -> None:
        """No-op — handled by LayerListPane.on_key via event bubbling."""

    def action_move_down(self) -> None:
        """No-op — handled by LayerListPane.on_key via event bubbling."""

    def action_confirm_move(self) -> None:
        """No-op — handled by LayerListPane.on_key via event bubbling."""

    def action_cancel_move(self) -> None:
        """No-op — handled by LayerListPane.on_key via event bubbling."""


class SkimButton(Button):
    """Button that responds to both Enter and Space."""

    BINDINGS = [
        Binding("enter", "press", "Activate", key_display="\u23ce,\u2423", show=True),
        Binding("space", "press", "Activate", show=False),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "space":
            self.action_press()
            event.stop()
            event.prevent_default()
            return
        await super()._on_key(event)


class SkimSwitch(Switch):
    """Switch with footer binding for toggle action."""

    BINDINGS = [
        Binding("enter", "toggle_switch", "Toggle", key_display="\u23ce,\u2423", show=True),
        Binding("space", "toggle_switch", "Toggle", show=False),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key


class _SkimSelectOverlay(SelectOverlay):
    """SelectOverlay that treats Space as select instead of type-to-search."""

    BINDINGS = [
        Binding("enter", "select", "Select option", key_display="\u23ce,\u2423", show=True),
        Binding("space", "select", "Select option", show=False),
        Binding("escape", "dismiss", "Dismiss", key_display="\U000f12b7", show=True),
    ]

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "space":
            self.action_select()
            event.stop()
            event.prevent_default()
            return
        await super()._on_key(event)


class SkimSelect(Select):
    """Select with footer binding for menu action."""

    BINDINGS = [
        Binding("enter", "show_overlay", "Show options", key_display="\u23ce,\u2423", show=True),
        Binding("space", "show_overlay", "Show options", show=False),
        Binding("tab", "focus_next", "Next field", key_display="\u2193,\u21e5", show=True),
        Binding(
            "shift+tab", "focus_previous", "Previous field", key_display="\u2191,\u21e4", show=True
        ),
        Binding("escape", "cancel_edit", "Discard changes", key_display="\U000f12b7", show=True),
        Binding("up", "skip_arrow", show=False),
        Binding("down", "skip_arrow", show=False),
    ]

    def __init__(self, *args: Any, help_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.help_key = help_key

    def action_cancel_edit(self) -> None:
        """No-op — handled by ListDetailPane.on_key via event bubbling."""

    def action_skip_arrow(self) -> None:
        """Yield arrow keys to app-level spatial navigation."""
        raise SkipAction()

    def compose(self) -> ComposeResult:
        yield SelectCurrent(self.prompt)
        yield _SkimSelectOverlay(type_to_search=self._type_to_search).data_bind(
            compact=Select.compact
        )


class SkimVerticalScroll(VerticalScroll):
    """VerticalScroll that yields arrow keys for spatial focus navigation.

    Arrow keys raise SkipAction so the app-level directional focus handler
    receives them.  Page Up/Down and Home/End still scroll normally.
    """

    def action_scroll_up(self) -> None:
        raise SkipAction()

    def action_scroll_down(self) -> None:
        raise SkipAction()

    def action_scroll_left(self) -> None:
        raise SkipAction()

    def action_scroll_right(self) -> None:
        raise SkipAction()

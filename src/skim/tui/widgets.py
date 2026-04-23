# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Shared reusable TUI widgets for skim configuration editor."""

from __future__ import annotations

from textual import events
from textual.actions import SkipAction
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Input, ListView, Select, Switch, Tabs
from textual.widgets._footer import FooterKey
from textual.widgets._select import SelectCurrent, SelectOverlay


# ---------------------------------------------------------------------------
# Custom footer with standardised binding order and paired display
# ---------------------------------------------------------------------------

# Sort priority for actions.  Lower value → further left in the footer.
_ACTION_ORDER: dict[str, int] = {
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
    "toggle_switch": 10,
    "show_overlay": 10,
    "select": 11,
    "dismiss": 12,
    "cursor_up": 13,
    "select_cursor": 14,
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
            key, key_display, description, action,
            disabled=not enabled, tooltip=tooltip,
        ).data_bind(compact=Footer.compact)

    def compose(self) -> ComposeResult:
        if not self._bindings_ready:
            return

        active = self.screen.active_bindings

        # Collect one representative binding per action.
        by_action: dict[str, tuple[Binding, bool, str]] = {}
        for _key, (node, binding, enabled, tooltip) in active.items():
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
                        binding.key, key_display, description,
                        binding.action, enabled=enabled,
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
                "left", "\u2190/\u2192", "Prev/Next tab", "",
            )


# ---------------------------------------------------------------------------
# Widget classes
# ---------------------------------------------------------------------------


class SkimStandaloneInput(Input):
    """Input for standalone fields outside edit panes."""

    BINDINGS = [
        Binding("tab", "focus_next", "Next field", key_display="\u2193,\u21e5", show=True),
        Binding("shift+tab", "focus_previous", "Previous field", key_display="\u2191,\u21e4", show=True),
    ]


class SkimInput(Input):
    """Input with footer bindings for edit-pane field navigation."""

    BINDINGS = [
        Binding("tab", "focus_next", "Next field", key_display="\u2193,\u21e5", show=True),
        Binding("shift+tab", "focus_previous", "Previous field", key_display="\u2191,\u21e4", show=True),
        Binding("enter", "submit", "Confirm changes", key_display="\u23ce", show=True),
        Binding("escape", "cancel_edit", "Discard changes", key_display="\U000f12b7", show=True),
    ]

    def action_cancel_edit(self) -> None:
        """No-op — handled by ListDetailPane.on_key via event bubbling."""


class SkimListView(ListView):
    """ListView with footer bindings for navigation and edit."""

    BINDINGS = [
        Binding("up", "cursor_up", "Prev item", show=True),
        Binding("down", "cursor_down", "Next item", show=True),
        Binding("enter", "select_cursor", "Edit", key_display="\u23ce", show=True),
    ]


class SkimSwitch(Switch):
    """Switch with footer binding for toggle action."""

    BINDINGS = [
        Binding("enter", "toggle_switch", "Toggle", key_display="\u23ce,\u2423", show=True),
        Binding("space", "toggle_switch", "Toggle", show=False),
    ]


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
        Binding("shift+tab", "focus_previous", "Previous field", key_display="\u2191,\u21e4", show=True),
        Binding("escape", "cancel_edit", "Discard changes", key_display="\U000f12b7", show=True),
        Binding("up", "skip_arrow", show=False),
        Binding("down", "skip_arrow", show=False),
    ]

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

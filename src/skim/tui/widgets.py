# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Shared reusable TUI widgets for skim configuration editor."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Input, ListView, Select, Switch
from textual.widgets._select import SelectCurrent, SelectOverlay


class SkimInput(Input):
    """Input with footer bindings for field navigation."""

    BINDINGS = [
        Binding("enter", "submit", "Commit changes", key_display="\u23ce", show=True),
        Binding("escape", "cancel_edit", "Cancel changes", key_display="\U000f12b7", show=True),
        Binding("tab", "focus_next", "Next field", key_display="\u21e5", show=True),
        Binding("shift+tab", "focus_previous", "Previous field", key_display="\u21e4", show=True),
    ]

    def action_cancel_edit(self) -> None:
        """No-op — handled by ListDetailPane.on_key via event bubbling."""


class SkimListView(ListView):
    """ListView with footer binding for edit action."""

    BINDINGS = [
        Binding("enter", "select_cursor", "Edit", key_display="\u23ce", show=True),
    ]


class SkimSwitch(Switch):
    """Switch with footer binding for toggle action."""

    BINDINGS = [
        Binding("enter,space", "toggle_switch", "Toggle", key_display="\u2423", show=True),
    ]


class _SkimSelectOverlay(SelectOverlay):
    """SelectOverlay that treats Space as select instead of type-to-search."""

    BINDINGS = [
        Binding("enter", "select", "Select item", key_display="\u23ce/\u2423", show=True),
        Binding("escape", "dismiss", "Cancel selection", key_display="\U000f12b7", show=True),
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
        Binding("enter,space", "show_overlay", "Show menu", key_display="\u23ce/\u2423", show=True),
        Binding("escape", "cancel_edit", "Cancel changes", key_display="\U000f12b7", show=True),
    ]

    def action_cancel_edit(self) -> None:
        """No-op — handled by ListDetailPane.on_key via event bubbling."""

    def compose(self) -> ComposeResult:
        yield SelectCurrent(self.prompt)
        yield _SkimSelectOverlay(type_to_search=self._type_to_search).data_bind(
            compact=Select.compact
        )

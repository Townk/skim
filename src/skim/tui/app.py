# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Main TUI application for skim configuration editing."""

import copy
import time
from pathlib import Path
from typing import Any

import yaml
from textual import events
from textual.actions import SkipAction
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.geometry import Size
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    ListView,
    Markdown,
    OptionList,
    TabbedContent,
    TabPane,
    Tabs,
)

from skim.assets import ASSETS
from skim.data.config import SkimConfig
from skim.tui.widgets import SkimButton, SkimFooter, SkimListView


class LayerAdded(Message):
    """Posted when a layer is added in either tab."""

    def __init__(self, index: int, source_tab: str) -> None:
        super().__init__()
        self.index = index
        self.source_tab = source_tab


class LayerRemoved(Message):
    """Posted when a layer is removed in either tab."""

    def __init__(self, index: int, source_tab: str) -> None:
        super().__init__()
        self.index = index
        self.source_tab = source_tab


class LayerUpdated(Message):
    """Posted when a layer's metadata (name, label, etc.) is changed."""

    def __init__(self, source_tab: str) -> None:
        super().__init__()
        self.source_tab = source_tab


class QuitConfirmScreen(ModalScreen[str]):
    """Modal dialog for save-on-quit with unsaved changes.

    Returns "save" to save and quit, "discard" to quit without saving,
    or None if dismissed.
    """

    BINDINGS = [
        Binding(key="s", action="save_quit", description="Save & Quit", show=False),
        Binding(key="d", action="discard", description="Discard", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-dialog"):
            yield Label(
                "You have unsaved changes.\nDo you want to save before quitting?",
                id="question",
            )
            with Horizontal(id="quit-buttons"):
                yield SkimButton("Save & Quit (s)", variant="success", id="save")
                yield SkimButton("Discard (d)", variant="error", id="discard")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)

    def action_save_quit(self) -> None:
        self.dismiss("save")

    def action_discard(self) -> None:
        self.dismiss("discard")


_DEFAULT_CONFIG_NAME = "skim-config.yaml"


class SaveTargetScreen(ModalScreen[str | None]):
    """Modal dialog to choose where to save when -c was used without -o.

    Returns "overwrite" to save back to the config file,
    "default" to save to skim-config.yaml in cwd, or None if dismissed.
    """

    BINDINGS = [
        Binding(key="escape", action="dismiss_dialog", description="Cancel", show=False),
    ]

    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.config_path = config_path

    def compose(self) -> ComposeResult:
        with Vertical(id="save-target-dialog"):
            yield Label(
                "Where do you want to save?",
                id="question",
            )
            with Vertical(id="save-target-buttons"):
                yield SkimButton(
                    f"Overwrite {self.config_path.name} (o)",
                    variant="warning",
                    id="overwrite",
                )
                yield SkimButton(
                    f"Create ./{_DEFAULT_CONFIG_NAME} (c)",
                    variant="success",
                    id="default",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)

    def on_key(self, event) -> None:
        if event.key == "o":
            self.dismiss("overwrite")
        elif event.key == "c":
            self.dismiss("default")

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


class OverwriteConfirmScreen(ModalScreen[bool]):
    """Modal dialog to confirm overwriting an existing file.

    Returns True to overwrite, False to cancel.
    """

    BINDINGS = [
        Binding(key="escape", action="dismiss_dialog", description="Cancel", show=False),
    ]

    def __init__(self, path: Path, display_name: str | None = None) -> None:
        super().__init__()
        self.path = path
        self._display_name = display_name or str(path)

    def compose(self) -> ComposeResult:
        with Vertical(id="overwrite-dialog"):
            yield Label(
                f"File '{self._display_name}' already exists.\nOverwrite?",
                id="question",
            )
            with Horizontal(id="overwrite-buttons"):
                yield SkimButton("Overwrite (y)", variant="warning", id="confirm")
                yield SkimButton("Cancel (n)", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def on_key(self, event) -> None:
        if event.key == "y":
            self.dismiss(True)
        elif event.key == "n":
            self.dismiss(False)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(False)


class ErrorDialog(ModalScreen[None]):
    """Modal dialog to show an error message."""

    BINDINGS = [
        Binding(key="escape", action="dismiss_dialog", description="OK", show=False),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="error-dialog"):
            yield Label(self.message, id="error-message")
            with Horizontal(id="error-buttons"):
                yield SkimButton("OK", variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(None)


class _HelpMarkdown(Markdown):
    """Markdown widget that reports its content height for layout sizing.

    Overrides ``get_content_height`` so that a parent container with
    ``height: auto; max-height: 80%`` can size itself to the content on
    the very first frame — no post-render measurement or flashing.
    """

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        total = 0
        children = list(self.children)
        # Zero the last child's bottom margin so the virtual size matches
        # the reported content height (prevents a spurious scrollbar).
        if children:
            last = children[-1]
            if last.styles.margin.bottom:
                last.styles.margin = (last.styles.margin.top, 0, 0, 0)
        for child in children:
            m = child.styles.margin
            total += m.top + child.get_content_height(container, viewport, width) + m.bottom
        return total


class HelpScreen(ModalScreen[None]):
    """Modal dialog to show contextual help as rendered markdown."""

    BINDINGS = [
        Binding(key="escape", action="dismiss_help", description="Close", show=False),
        Binding(key="q", action="dismiss_help", description="Close", show=False),
    ]

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield _HelpMarkdown(self.content)

    def on_mount(self) -> None:
        md = self.query_one(_HelpMarkdown)
        md.can_focus = True
        md.focus()

    def on_key(self, event: events.Key) -> None:
        md = self.query_one(_HelpMarkdown)
        key = event.key
        if key == "j":
            md.scroll_down(animate=False)
        elif key == "k":
            md.scroll_up(animate=False)
        elif key in ("ctrl+d", "ctrl+f"):
            md.scroll_page_down(animate=False)
        elif key in ("ctrl+u", "ctrl+b"):
            md.scroll_page_up(animate=False)
        elif key == "G":
            md.scroll_end(animate=False)
        elif key == "g":
            md.scroll_home(animate=False)
        elif key == "ctrl+q":
            self.dismiss(None)
            self.app.call_later(self.app.action_request_quit)  # type: ignore[reportAttributeAccessIssue]
        else:
            return
        event.stop()

    def action_dismiss_help(self) -> None:
        self.dismiss(None)


class SkimConfigApp(App):
    """Interactive skim configuration editor."""

    ENABLE_COMMAND_PALETTE = False
    TITLE = "skim configure"
    CSS = """
    QuitConfirmScreen, SaveTargetScreen, OverwriteConfirmScreen, ErrorDialog, HelpScreen {
        align: center middle;
    }
    #quit-dialog, #save-target-dialog, #error-dialog {
        padding: 1 2;
        width: 55;
        height: auto;
        border: thick $background 80%;
        background: $surface;
    }
    #overwrite-dialog {
        padding: 1 2;
        width: 82;
        height: auto;
        border: thick $background 80%;
        background: $surface;
    }
    #question {
        text-align: center;
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    #error-message {
        text-align: center;
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    #quit-buttons, #overwrite-buttons, #error-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
    }
    #quit-buttons Button, #overwrite-buttons Button, #error-buttons Button {
        margin: 0 1;
        padding: 0 3;
    }
    #help-dialog {
        padding: 0;
        width: 70;
        height: auto;
        max-height: 80%;
        border: thick $background 80%;
        background: $surface;
    }
    #help-dialog _HelpMarkdown {
        padding: 1 3;
        overflow-y: auto;
        max-height: 100%;
    }
    #help-dialog MarkdownH1 {
        background: transparent;
        margin: 0 0 1 0;
    }
    #help-dialog MarkdownH2,
    #help-dialog MarkdownH3 {
        background: transparent;
    }
    #save-target-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
    }
    #save-target-buttons Button {
        width: 100%;
        margin: 0 0 1 0;
    }
    /* Global compact styling */
    Input {
        height: 3;
        width: 1fr;
        margin: 0;
    }
    Switch {
        height: auto;
        min-height: 1;
    }
    Select {
        width: 1fr;
        max-width: 30;
    }
    .field-row {
        height: auto;
        margin: 0;
        padding: 0;
    }
    .field-label {
        width: 22;
        height: 3;
        padding: 1 0 0 0;
    }
    .section-title {
        text-style: bold;
        color: $accent;
        margin: 1 0 0 0;
    }
    .section-title-first {
        margin: 0;
    }
    AutoComplete {
        & AutoCompleteList {
            border-left: wide $accent;
        }
    }
    ListItem {
        layout: horizontal;
    }
    ListItem > Static {
        text-wrap: nowrap;
        text-overflow: ellipsis;
        width: 1fr;
    }
    ListItem.moving {
        background: $accent 30%;
    }
    ListItem.moving > Static {
        color: $accent;
    }
    ListItem > .lc-swatch {
        width: 4;
    }
    ListItem > .move-indicator {
        dock: right;
        width: 3;
        color: $accent;
    }
    .list-buttons {
        height: auto;
    }
    .list-buttons Button {
        min-width: 12;
        margin: 0 1 0 0;
    }
    """

    BINDINGS = [
        Binding(key="ctrl+q", action="request_quit", description="Quit", key_display="\u2303Q"),
        Binding(key="ctrl+s", action="save", description="Save", key_display="\u2303S"),
        Binding(
            key="ctrl+p",
            action="previous_tab",
            description="Previous Tab",
            key_display="\u2303P",
            priority=True,
        ),
        Binding(
            key="ctrl+n",
            action="next_tab",
            description="Next Tab",
            key_display="\u2303N",
            priority=True,
        ),
        Binding(key="up", action="focus_direction('up')", show=False, priority=True),
        Binding(key="down", action="focus_direction('down')", show=False, priority=True),
        Binding(key="left", action="focus_direction('left')", show=False, priority=True),
        Binding(key="right", action="focus_direction('right')", show=False, priority=True),
        Binding(
            key="ctrl+e",
            action="scroll_view('down')",
            description="Scroll down",
            key_display="\u2303E",
            priority=True,
        ),
        Binding(
            key="ctrl+y",
            action="scroll_view('up')",
            description="Scroll up",
            key_display="\u2303Y",
            priority=True,
        ),
        Binding(
            key="f1",
            action="show_help",
            description="Help",
            key_display="F1,\u2325H",
            priority=True,
        ),
        Binding(key="alt+h", action="show_help", show=False, priority=True),
    ]

    def __init__(
        self,
        config_data: dict[str, Any],
        output_path: Path | None = None,
        config_path: Path | None = None,
        force: bool = False,
    ) -> None:
        super().__init__()
        self.config_data = config_data
        self.saved_data = copy.deepcopy(config_data)
        self._tab_focus: dict[str, str] = {}
        self.output_path = output_path
        self.config_path = config_path
        self.force = force
        self._last_nav_time: dict[str, float] = {}  # direction -> monotonic timestamp

    def compose(self) -> ComposeResult:
        from skim.tui.keyboard_tab import KeyboardTab

        with TabbedContent(initial="keyboard-tab"):
            with TabPane("Keyboard", id="keyboard-tab"):
                yield KeyboardTab(config_data=self.config_data)
            with TabPane("Keycodes", id="keycodes-tab"):
                from skim.tui.keycodes_tab import KeycodesTab

                yield KeycodesTab(config_data=self.config_data)
            with TabPane("Output", id="output-tab"):
                from skim.tui.output_tab import OutputTab

                yield OutputTab(config_data=self.config_data)
        yield SkimFooter()

    @property
    def has_unsaved_changes(self) -> bool:
        return self.config_data != self.saved_data

    def action_request_quit(self) -> None:
        if self.has_unsaved_changes:
            self.push_screen(QuitConfirmScreen(), self._handle_quit_confirm)
        else:
            self.exit()

    def action_show_help(self) -> None:
        """Show contextual help for the currently focused widget."""
        if isinstance(self.screen, HelpScreen):
            return
        widget = self.focused
        help_key = None
        while widget is not None:
            if hasattr(widget, "help_key") and widget.help_key:  # type: ignore[reportAttributeAccessIssue]
                help_key = widget.help_key  # type: ignore[reportAttributeAccessIssue]
                break
            widget = widget.parent
        content = ASSETS.help_text(help_key or "general")
        self.push_screen(HelpScreen(content))

    def _handle_quit_confirm(self, result: str | None) -> None:
        if result == "save":
            self.action_save(exit_after=True)
        elif result == "discard":
            self.exit()

    def _save_current_tab_focus(self) -> None:
        """Save the currently focused widget for the active tab pane."""
        tabbed = self.query_one(TabbedContent)
        pane = tabbed.active_pane
        focused = self.focused
        if (
            pane is not None
            and focused is not None
            and focused.id is not None
            and focused in pane.query("*")
        ):
            self._tab_focus[pane.id] = focused.id  # type: ignore[index]

    def action_previous_tab(self) -> None:
        self._save_current_tab_focus()
        self.query_one(Tabs).action_previous_tab()
        self.call_after_refresh(self._restore_tab_focus)

    def action_next_tab(self) -> None:
        self._save_current_tab_focus()
        self.query_one(Tabs).action_next_tab()
        self.call_after_refresh(self._restore_tab_focus)

    def _restore_tab_focus(self) -> None:
        """Restore previously focused widget for the active tab pane, or focus the first focusable child."""
        tabbed = self.query_one(TabbedContent)
        pane = tabbed.active_pane
        if pane is None:
            return
        saved_id = self._tab_focus.get(pane.id)  # type: ignore[arg-type]
        if saved_id is not None:
            try:
                widget = pane.query_one(f"#{saved_id}")
                if widget.can_focus:
                    widget.focus()
                    return
            except Exception:
                pass
        for widget in pane.query("*"):
            if widget.can_focus:
                widget.focus()
                return

    def action_save(self, *, exit_after: bool = False) -> None:
        try:
            SkimConfig.model_validate(self.config_data)
        except Exception as e:
            self.notify(f"Validation error: {e}", severity="error")
            return

        if self.output_path is not None:
            # -o was provided: save directly to that path
            path = self.output_path
            if path.is_dir():
                path = path / _DEFAULT_CONFIG_NAME
            self._save_to_path(path, exit_after=exit_after)
        elif self.config_path is not None:
            # -c was provided without -o: ask where to save
            self.push_screen(
                SaveTargetScreen(self.config_path),
                lambda result: self._handle_save_target(result, exit_after=exit_after),
            )
        else:
            # No -o or -c: save to default in cwd
            path = Path.cwd() / _DEFAULT_CONFIG_NAME
            self._save_to_path(path, prettify_name=True, exit_after=exit_after)

    def _handle_save_target(self, result: str | None, *, exit_after: bool = False) -> None:
        if result == "overwrite":
            assert self.config_path is not None
            # User already confirmed overwrite intent via the dialog choice
            self._do_write(self.config_path, exit_after=exit_after)
        elif result == "default":
            self._save_to_path(
                Path.cwd() / _DEFAULT_CONFIG_NAME,
                prettify_name=True,
                exit_after=exit_after,
            )

    @staticmethod
    def _friendly_path(path: Path) -> str:
        """Return a user-friendly display name for a path."""
        try:
            rel = path.relative_to(Path.cwd())
        except ValueError:
            rel = path
        path_str = str(rel)
        if not path_str.startswith((".", "/")):
            path_str = f"./{path_str}"
        return path_str

    def _save_to_path(
        self,
        path: Path,
        *,
        prettify_name: bool = False,
        exit_after: bool = False,
    ) -> None:
        if path.exists() and not self.force:
            display_name = self._friendly_path(path) if prettify_name else None
            self.push_screen(
                OverwriteConfirmScreen(path, display_name=display_name),
                lambda confirmed: (
                    self._do_write(path, exit_after=exit_after) if confirmed else None
                ),
            )
            return
        self._do_write(path, exit_after=exit_after)

    def _do_write(self, path: Path, *, exit_after: bool = False) -> None:
        content = yaml.dump(self.config_data, sort_keys=False, default_flow_style=False)
        path.write_text(content)
        self.saved_data = copy.deepcopy(self.config_data)
        self.notify(f"Saved to {path}", severity="information")
        if exit_after:
            self.exit()

    def on_layer_added(self, event: LayerAdded) -> None:
        from skim.tui.keyboard_tab import KeyboardTab
        from skim.tui.output_tab import OutputTab

        if event.source_tab == "keyboard":
            self.query_one(OutputTab).sync_layer_added(event.index)
        elif event.source_tab == "style":
            self.query_one(KeyboardTab).sync_layer_added(event.index)

    def on_layer_updated(self, event: LayerUpdated) -> None:
        from skim.tui.keyboard_tab import KeyboardTab
        from skim.tui.output_tab import OutputTab

        # Only rebuild the *other* tab's list. The source tab already holds
        # the post-commit state — rebuilding it would clear list_view.index
        # and snap the cursor back to the top.
        if event.source_tab != "keyboard":
            self.query_one(KeyboardTab)._rebuild_layer_list()
        if event.source_tab != "style":
            self.query_one(OutputTab)._rebuild_layer_colors_list()

    def on_layer_removed(self, event: LayerRemoved) -> None:
        from skim.tui.keyboard_tab import KeyboardTab
        from skim.tui.output_tab import OutputTab

        if event.source_tab == "keyboard":
            self.query_one(OutputTab).sync_layer_removed(event.index)
        elif event.source_tab == "style":
            self.query_one(KeyboardTab).sync_layer_removed(event.index)

    # ------------------------------------------------------------------
    # Spatial focus navigation
    # ------------------------------------------------------------------

    def action_scroll_view(self, direction: str) -> None:
        """Scroll the VerticalScroll in the active tab (skip ListViews)."""
        if isinstance(self.screen, HelpScreen):
            scroll = self.screen.query_one(_HelpMarkdown)
            if direction == "up":
                scroll.scroll_up(animate=False)
            else:
                scroll.scroll_down(animate=False)
            return
        if isinstance(self.screen, ModalScreen):
            return

        from skim.tui.widgets import SkimVerticalScroll

        focused = self.focused
        if focused is None:
            return

        # Walk up from the focused widget, skipping ListViews.
        scroll = self._scroll_ancestor(focused)
        while scroll is not None and isinstance(scroll, ListView):
            scroll = self._scroll_ancestor(scroll)

        # When focused on the tab bar (or no scroll ancestor found),
        # look for the SkimVerticalScroll inside the active pane.
        if scroll is None:
            tabbed = self.query_one(TabbedContent)
            pane = tabbed.active_pane
            if pane is not None:
                results = pane.query(SkimVerticalScroll)
                if results:
                    scroll = results.first()

        if scroll is None:
            return
        if direction == "down":
            scroll.scroll_down(animate=False)
        else:
            scroll.scroll_up(animate=False)

    _REPEAT_THRESHOLD = 0.1  # seconds — key repeats are ~30ms apart

    def _is_hold_repeat(self, direction: str) -> bool:
        """Return True if this is a held-down key repeat for *direction*.

        We consider it a repeat when the previous navigation in the same
        direction happened very recently (within _REPEAT_THRESHOLD seconds).
        """
        last = self._last_nav_time.get(direction)
        return last is not None and (time.monotonic() - last) < self._REPEAT_THRESHOLD

    def _record_nav(self, direction: str) -> None:
        """Record that a navigation key was pressed for *direction*."""
        self._last_nav_time[direction] = time.monotonic()

    @staticmethod
    def _scroll_ancestor(widget):
        """Return the nearest ScrollableContainer ancestor, if any."""
        node = widget.parent
        while node is not None:
            if isinstance(node, ScrollableContainer):
                return node
            node = node.parent
        return None

    @staticmethod
    def _best_in_direction(current, direction, candidates, focused):
        """Find the nearest focusable widget in *direction* from *current*."""
        cx = current.x + current.width / 2
        cy = current.y + current.height / 2
        best = None
        best_score = float("inf")

        for widget in candidates:
            if widget is focused:
                continue
            if not widget.can_focus or widget.disabled:
                continue
            region = widget.region
            if not region.width or not region.height:
                continue

            tx = region.x + region.width / 2
            ty = region.y + region.height / 2
            dx = tx - cx
            dy = ty - cy

            if (
                direction == "down"
                and dy <= 0
                or direction == "up"
                and dy >= 0
                or direction == "right"
                and dx <= 0
                or direction == "left"
                and dx >= 0
            ):
                continue

            # Left/right: only navigate to widgets in the same visual row
            # (y-ranges must overlap).  This prevents jumping to unrelated
            # widgets far above or below.
            # Up/down: prefer same-column widgets but allow cross-column
            # with a penalty, since vertical navigation across sections
            # is expected.
            if direction in ("left", "right"):
                same_row = (
                    current.y < region.y + region.height and region.y < current.y + current.height
                )
                if not same_row:
                    continue
                score = abs(dx)
            else:
                same_col = (
                    current.x < region.x + region.width and region.x < current.x + current.width
                )
                score = abs(dy) + (0 if same_col else abs(dx) * 5)

            if score < best_score:
                best_score = score
                best = widget

        return best

    def _has_visible_autocomplete(self, widget) -> bool:
        """Check if *widget* has a visible autocomplete dropdown."""
        from textual_autocomplete import AutoComplete

        tabbed = self.query_one(TabbedContent)
        pane = tabbed.active_pane
        if pane is None:
            return False
        return any(ac.target is widget and ac.display for ac in pane.query(AutoComplete))

    @staticmethod
    def _maybe_select_edge(widget, direction: str) -> None:
        """Select the edge item when a ListView gains focus with no selection.

        When navigating *up* into a ListView that has no selected item, the
        bottom-most item is selected so the cursor position matches the
        spatial direction.
        """
        if not isinstance(widget, ListView):
            return
        if widget.index is not None:
            return
        if direction == "up" and len(widget._nodes) > 0:
            widget.index = len(widget._nodes) - 1

    def action_focus_direction(self, direction: str) -> None:
        """Move focus to the nearest focusable widget in the given direction."""
        focused = self.focused
        if focused is None:
            return

        # HelpScreen: scroll content instead of navigating.
        if isinstance(self.screen, HelpScreen):
            if direction in ("up", "down"):
                scroll = self.screen.query_one(_HelpMarkdown)
                if direction == "up":
                    scroll.scroll_up(animate=False)
                else:
                    scroll.scroll_down(animate=False)
            return

        # Modal screens: navigate among the modal's own widgets only.
        if isinstance(self.screen, ModalScreen):
            current = focused.region
            if not current.width or not current.height:
                return
            target = self._best_in_direction(
                current,
                direction,
                self.screen.query("*"),
                focused,
            )
            if target is not None:
                target.focus()
            return

        # OptionList: don't navigate away from Select/AutoComplete overlays
        if isinstance(focused, OptionList):
            raise SkipAction()

        # ListView: allow escape at edges unless it's a hold-down repeat.
        if isinstance(focused, ListView):
            if direction in ("left", "right"):
                raise SkipAction()
            at_edge = False
            if direction == "up" and focused.index == 0:
                at_edge = True
            elif direction == "down" and focused.index is not None:
                at_edge = focused.index >= len(focused._nodes) - 1
            if not at_edge:
                self._record_nav(direction)
                raise SkipAction()  # Normal cursor movement within list
            # At the edge — block if this is a hold-down repeat.
            if self._is_hold_repeat(direction):
                self._record_nav(direction)
                raise SkipAction()
            self._record_nav(direction)
            # Fall through to spatial navigation (escape the list).

        # Input: left/right must move the cursor, not navigate
        elif isinstance(focused, Input) and direction in ("left", "right"):
            raise SkipAction()

        # Input: when an autocomplete dropdown is visible, let it handle
        # up/down to navigate the completion list.
        elif isinstance(focused, Input) and direction in ("up", "down"):
            if self._has_visible_autocomplete(focused):
                raise SkipAction()

        # Tab bar: left/right must switch tabs, not navigate
        elif isinstance(focused, Tabs) and direction in ("left", "right"):
            raise SkipAction()

        current = focused.region
        if not current.width or not current.height:
            return

        # If inside an editing ListDetailPane, trap arrows within the
        # detail pane — only Tab/Shift-Tab can leave.
        from skim.tui.list_detail_pane import ListDetailPane

        node = focused.parent
        while node is not None:
            if isinstance(node, ListDetailPane) and node._editing:
                detail = node.query_one(f"#{node.pane_id}-detail")
                target = self._best_in_direction(
                    current,
                    direction,
                    detail.query("*"),
                    focused,
                )
                if target is not None:
                    target.focus()
                return  # Never escape the edit pane via arrows
            node = node.parent

        tabbed = self.query_one(TabbedContent)
        pane = tabbed.active_pane
        if pane is None:
            return

        # If inside a scrollable container, try to stay within it first.
        scroll = self._scroll_ancestor(focused)
        if scroll is not None and direction in ("up", "down"):
            inner = self._best_in_direction(
                current,
                direction,
                scroll.query("*"),
                focused,
            )
            if inner is not None:
                self._record_nav(direction)
                inner.focus()
                self._maybe_select_edge(inner, direction)
                return
            # No widget inside the scroll container in that direction.
            # Only leave if the container is fully scrolled to the edge
            # AND this is not the first rapid press (fly-out prevention).
            at_scroll_edge = (direction == "down" and scroll.scroll_y >= scroll.max_scroll_y) or (
                direction == "up" and scroll.scroll_y <= 0
            )
            if not at_scroll_edge or self._is_hold_repeat(direction):
                self._record_nav(direction)
                return
            self._record_nav(direction)

        # Search the full pane + the tab bar.
        tabs_widget = tabbed.query_one(Tabs)
        all_candidates = list(pane.query("*"))
        all_candidates.append(tabs_widget)

        target = self._best_in_direction(current, direction, all_candidates, focused)
        if target is not None:
            target.focus()
            self._maybe_select_edge(target, direction)

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        widget = event.widget
        if (
            isinstance(widget, (ListView, SkimListView))
            and widget.index is None
            and len(widget.children) > 0
        ):
            widget.index = 0

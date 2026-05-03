# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Text rendering components for keyboard labels.

This module provides font management, label parsing, and text rendering
utilities for displaying key labels with support for Nerd Font glyphs,
separators, and multi-part labels.
"""

from __future__ import annotations

import base64
import math
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from functools import cache, cached_property, lru_cache
from pathlib import Path
from typing import Protocol

from fontTools.ttLib import TTFont
from PIL import ImageFont

from skim.assets import ASSETS


@lru_cache(maxsize=256)
def _load_font(font_path: Path, font_size: int) -> ImageFont.FreeTypeFont:
    """Load a TrueType font with caching.

    Args:
        font_path: Path to the font file (validated by ASSETS).
        font_size: Font size in points.

    Returns:
        A PIL ImageFont.FreeTypeFont instance.
    """
    return ImageFont.truetype(font_path, font_size)


@cache
def _font_cmap(font: Font) -> frozenset[int]:
    """Return the set of code points actually present in the embedded font.

    Used by the parser / analyser to decide whether a character can
    render in a given font or needs to be routed through the
    Unicode-symbols fallback. Cached because the cmap walk has a
    fixed cost and the same font is queried many times across a
    keymap render.
    """
    tt = TTFont(font.path)
    cmap = tt.getBestCmap()
    return frozenset(cmap.keys()) if cmap is not None else frozenset()


class Font(Enum):
    """Enumeration of available fonts for keyboard rendering.

    Attributes:
        FINGER_KEY: Regular font for finger cluster key labels.
        THUMB_KEY: Bold font for thumb cluster key labels.
        TITLE: Thin font for keymap titles.
        SYMBOLS: Nerd Font for Nerd-Font-token glyphs (``%%nf-…;``).
        UNICODE_SYMBOLS: DejaVu Sans Condensed — Unicode fallback
            for keyboard symbols (⎇ ⌘ ⌥ ⌃ ⇧ ↹ ⏎ ␣ ⌫ ⌦) and the
            box-drawing separator (│) that the Roboto family
            doesn't carry. Used by ``parse_into_spans`` for any
            character missing from the requesting span's font.
    """

    FINGER_KEY = (
        "Finger-Key-Label",
        ASSETS.font_roboto_regular,
    )
    THUMB_KEY = (
        "Thumb-Key-Label",
        ASSETS.font_roboto_black,
    )
    TITLE = (
        "Keymap-Title",
        ASSETS.font_roboto_thin,
    )
    SYMBOLS = (
        "Key-Symbols",
        ASSETS.font_symbols_nerd,
    )
    UNICODE_SYMBOLS = (
        "Unicode-Symbols",
        ASSETS.font_dejavu_sans_condensed,
    )

    def __init__(self, font_family: str, font_path: Path):
        """Initialize a Font enum member.

        Args:
            font_family: The CSS font-family name for this font.
            font_path: Path to the font file resource.
        """
        self._value_ = font_family
        self.path = font_path

    @cached_property
    def css_style(self) -> str:
        """Generate CSS @font-face rule with embedded base64 font data.

        Returns:
            CSS string with embedded font data for SVG inclusion.
        """
        return f"""
        @font-face {{
            font-family: '{self.value}';
            src: url("data:font/ttf;base64,{base64.b64encode(self.path.read_bytes()).decode("utf-8")}") format('truetype');
        }}
        """

    def load(self, font_size: float) -> ImageFont.FreeTypeFont:
        """Load this font at the specified size.

        Args:
            font_size: Font size in points. Floats are accepted and
                rounded UP to the nearest int (PIL operates on
                integer point sizes; the cache stays keyed by int and
                rounding upward ensures measurement at-or-above the
                requested size — banker's rounding to the nearest int
                used to underestimate widths whenever ``font_size``
                landed on a ``.5`` boundary, since e.g.
                ``round(6.5)`` returns 6, leaving long labels to
                overflow the slot the layout reserved for them).

        Returns:
            A PIL ImageFont.FreeTypeFont instance.
        """
        return _load_font(self.path, max(int(math.ceil(font_size)), 1))

    def get_system_font_family(self) -> str:
        """Get the system font family name for CSS when not embedding fonts.

        Returns:
            The CSS font-family string to use when relying on system fonts.
        """
        match self:
            case Font.FINGER_KEY:
                return "Roboto, sans-serif"
            case Font.THUMB_KEY:
                return "'Roboto Black', 'Arial Black', sans-serif"
            case Font.TITLE:
                return "'Roboto Thin', 'Helvetica Neue', Arial, sans-serif"
            case Font.SYMBOLS:
                return "'Symbols Nerd Font', 'Nerd Fonts', monospace"
            case Font.UNICODE_SYMBOLS:
                return "'DejaVu Sans Condensed', 'DejaVu Sans', 'Apple Symbols', sans-serif"
            case _:
                return "sans-serif"


class FontUsageCollector:
    """Per-render set of characters actually painted, indexed by :class:`Font`.

    ``AdjustableText`` registers ``(style.font, rendered_text)`` at
    construction time when the active collector is set. The collector
    accumulates the union over all text composables built during one
    render pass; :func:`render` then consumes it to subset embedded
    fonts to just the glyphs the document will actually paint.

    Lives on its own ContextVar so a render pass starts with a fresh
    collector — :func:`using_render_context` activates one for the
    duration of its block. Calling ``add`` outside an active
    collector is a no-op (composables can be built outside a render
    pass for tests / introspection).
    """

    def __init__(self) -> None:
        self._char_sets: dict[Font, set[str]] = {font: set() for font in Font}

    def add(self, font: Font, text: str) -> None:
        """Register every character in ``text`` against ``font``.

        Empty / ``None`` text is a no-op so callers can register
        unconditionally without guard checks at the call site.
        """
        if not text:
            return
        self._char_sets[font].update(text)

    def get_used_chars(self, font: Font) -> set[str]:
        """Return the set of characters registered against ``font``.

        Returns a copy so the caller can mutate without disturbing
        the collector.
        """
        return self._char_sets[font].copy()


# Active font-usage collector — set inside ``using_render_context`` and
# read by :func:`current_font_usage_collector`. ``None`` means we're
# outside a render pass; composables that try to register fall back
# to a no-op.
_font_usage_var: ContextVar[FontUsageCollector | None] = ContextVar(
    "skim_font_usage_collector", default=None
)


def current_font_usage_collector() -> FontUsageCollector | None:
    """Return the active collector, or ``None`` if no render is in flight."""
    return _font_usage_var.get()


def register_font_usage(font: Font, text: str) -> None:
    """Register ``text`` against ``font`` on the active collector.

    No-op when no collector is active (outside a render pass — the
    composable might be under construction in a test / introspection
    flow). Used by :func:`AdjustableText` at construction time so the
    document's character usage is automatically tracked without each
    image entry point having to walk the keymap structure manually.
    """
    collector = _font_usage_var.get()
    if collector is not None:
        collector.add(font, text)


@contextmanager
def using_font_usage_collector(
    collector: FontUsageCollector | None = None,
) -> Iterator[FontUsageCollector]:
    """Push ``collector`` (or a fresh one) for the duration of the block.

    :func:`render` activates one of these around the build + paint of
    the document so :func:`AdjustableText` can register glyphs with
    no other plumbing. Yields the active collector so callers can
    read ``get_used_chars`` post-hoc.
    """
    actual = collector if collector is not None else FontUsageCollector()
    token = _font_usage_var.set(actual)
    try:
        yield actual
    finally:
        _font_usage_var.reset(token)


class _UsedCharsProvider(Protocol):
    """Minimal surface :class:`FontSubsetter` needs from its source.

    :class:`FontUsageCollector` is the canonical source — populated
    automatically by :func:`AdjustableText` at construction time
    while :func:`using_render_context` is active. Anything else
    that exposes ``get_used_chars(font)`` works structurally.
    """

    def get_used_chars(self, font: Font) -> set[str]: ...


class FontSubsetter:
    """Subsets fonts to just the glyphs the document paints.

    Uses fonttools to create minimized font files containing only
    the glyphs the active source provides. The source is typically a
    :class:`FontUsageCollector` populated by :func:`AdjustableText`
    at construction time, but any object that implements
    :meth:`get_used_chars` works.

    Example:
        with using_render_context(ctx) as _:
            doc = MyDocument(...)  # AdjustableText auto-registers
        subsetter = FontSubsetter(current_font_usage_collector())
        css = subsetter.generate_subsetted_css()
    """

    _source: _UsedCharsProvider

    def __init__(self, source: _UsedCharsProvider) -> None:
        """Initialize the subsetter with a character-usage source."""
        self._source = source

    def generate_subsetted_css(self) -> str:
        """Generate CSS @font-face rules with subsetted font data."""
        from fontTools.subset import Options, Subsetter, load_font

        css_rules = []

        for font in Font:
            chars = self._source.get_used_chars(font)

            if not chars:
                continue

            unicodes = {ord(c) for c in chars}

            options = Options()
            options.layout_features = ["*"]
            options.glyph_names = True
            options.symbol_cmap = True
            options.legacy_cmap = True
            options.notdef_glyph = True
            options.notdef_outline = True
            options.recommended_glyphs = True
            options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 7]
            options.name_legacy = True
            options.name_languages = [0x0409]
            # Drop FontForge build-time metadata tables fontTools
            # doesn't know how to subset — ``PfEd`` (private editor
            # data) and ``FFTM`` (FontForge Time-stamp Marker).
            # Both are harmless to drop; without listing ``FFTM``
            # the subsetter logs ``FFTM NOT subset; don't know how
            # to subset; dropped`` once per font per render.
            options.drop_tables = ["PfEd", "FFTM"]

            try:
                tt_font = load_font(str(font.path), options)

                subsetter = Subsetter(options=options)
                subsetter.populate(unicodes=unicodes)
                subsetter.subset(tt_font)

                import io

                output = io.BytesIO()
                tt_font.save(output)
                font_data = output.getvalue()

                encoded = base64.b64encode(font_data).decode("utf-8")

                css_rules.append(f"""
                @font-face {{
                    font-family: '{font.value}';
                    src: url("data:font/ttf;base64,{encoded}") format('truetype');
                }}
                """)

            except Exception:
                encoded = base64.b64encode(font.path.read_bytes()).decode("utf-8")
                css_rules.append(f"""
                @font-face {{
                    font-family: '{font.value}';
                    src: url("data:font/ttf;base64,{encoded}") format('truetype');
                }}
                """)

        return "\n".join(css_rules)

    def subset_font(self, font: Font) -> bytes | None:
        """Create a subsetted font file for a specific font."""
        from fontTools.subset import Options, Subsetter, load_font

        chars = self._source.get_used_chars(font)

        if not chars:
            return None

        unicodes = {ord(c) for c in chars}

        options = Options()
        options.layout_features = ["*"]
        options.glyph_names = True
        options.symbol_cmap = True
        options.legacy_cmap = True
        options.notdef_glyph = True
        options.notdef_outline = True
        options.recommended_glyphs = True
        options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 7]
        options.name_legacy = True
        options.name_languages = [0x0409]
        options.drop_tables = ["PfEd"]

        tt_font = load_font(str(font.path), options)

        subsetter = Subsetter(options=options)
        subsetter.populate(unicodes=unicodes)
        subsetter.subset(tt_font)

        import io

        output = io.BytesIO()
        tt_font.save(output)
        return output.getvalue()

    def get_size_reduction(self, font: Font) -> tuple[int, int]:
        """Get the file size reduction for a subsetted font."""
        original_size = font.path.stat().st_size
        subsetted_data = self.subset_font(font)

        if subsetted_data is None:
            return (original_size, 0)

        return (original_size, len(subsetted_data))

    def generate_full_fonts_css(self) -> str:
        css_rules = []
        for font in Font:
            encoded = base64.b64encode(font.path.read_bytes()).decode("utf-8")
            css_rules.append(f"""
            @font-face {{
                font-family: '{font.value}';
                src: url("data:font/ttf;base64,{encoded}") format('truetype');
            }}
            """)
        return "\n".join(css_rules)

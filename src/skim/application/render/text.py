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
from enum import Enum
from functools import cache, cached_property, lru_cache
from pathlib import Path
from typing import TypeVar

import drawsvg as draw
from fontTools.ttLib import TTFont
from PIL import ImageFont

from skim.application.loaders import load_nerdfont_glyphs
from skim.assets import ASSETS
from skim.data import SvalboardLayout
from skim.domain import SEPARATOR_CHAR, SvalboardMacro, SvalboardTapDance
from skim.domain.domain_types import SvalboardTargetKey

from .styling import adjust_luminance

LabelT = TypeVar("LabelT", bound="Label | None")


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
    return frozenset(tt.getBestCmap().keys())


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


class LabelPart:
    """Base class for parts of a label.

    Attributes:
        text: The text content of this label part.
    """

    _text: str
    _text_color: str
    _font: Font

    def __init__(self, text: str, text_color: str = "#000", font: Font = Font.FINGER_KEY):
        """Initialize a label part.

        Args:
            text: The text content.
            text_color: The text color as a hex string. Default: "#000" (black).
            font: The font to use for rendering. Default: FINGER_KEY.
        """
        self.text = text
        self._text_color = text_color
        self._font = font

    def __str__(self) -> str:
        """Return the text content."""
        return self.text

    def __repr__(self) -> str:
        """Return a detailed representation for debugging."""
        return f"LabelPart('{self.text}')"

    @cached_property
    def text_color(self) -> str:
        """Get the text color for this part."""
        return self._text_color

    @property
    def font(self) -> Font:
        """Get the font for this part."""
        return self._font

    @property
    def font_family(self) -> str:
        """Get the CSS font-family name."""
        return self._font.value

    def measure_width(self, font: ImageFont.FreeTypeFont) -> float:
        """Measure the width of this text part.

        Args:
            font: The PIL font to use for measurement.

        Returns:
            The width in pixels.
        """
        return font.getlength(self.text)


class TextPart(LabelPart):
    def __repr__(self) -> str:
        return f"TextPart('{self.text}')"

    def measure_width(self, font: ImageFont.FreeTypeFont) -> float:
        return font.getlength(self.text.upper())


class SymbolPart(LabelPart):
    name: str

    def __init__(self, name: str, char: str, fill: str = "#000"):
        super().__init__(char, fill, Font.SYMBOLS)
        self.name = name

    def __str__(self) -> str:
        return f"{self.text} ({self.name})"

    def __repr__(self) -> str:
        return f"LabelPart('{self.text}', class_name='{self.name}')"


class SeparatorPart(LabelPart):
    SEPARATOR_DARKEN_FACTOR = 0.7
    # This is not a magic number! This ratio is exactly what this particular
    # Unicode character I use as a separator needs to render properly using
    # both Roboto fonts I embed in the final SVG.
    # If you change the character, the adjustment that happens in the
    # `measure_width` function will break and your label will look wrong!
    SEPARATOR_SIZE_MULTI = 7 / 3

    def __repr__(self) -> str:
        return f"SeparatorPart('{self.text}')"

    @cached_property
    def text_color(self) -> str:
        return adjust_luminance(self._text_color, SeparatorPart.SEPARATOR_DARKEN_FACTOR)

    def measure_width(self, font: ImageFont.FreeTypeFont) -> float:
        return font.getlength(self.text) * SeparatorPart.SEPARATOR_SIZE_MULTI


class Label:
    """Parsed label with support for Nerd Font glyphs and separators.

    Parses label strings containing Nerd Font tokens (%%nf-icon-name;) and
    separator characters, breaking them into LabelPart objects for rendering.

    Attributes:
        parts: List of LabelPart objects making up this label.
        font: The primary font for text parts.
        text_color: The text color as a hex string.
        background_color: The background color for separators.
        text_anchor: SVG text-anchor attribute value.
        dominant_baseline: SVG dominant-baseline attribute value.
        letter_spacing: Optional letter spacing in SVG units.
    """

    _GLYPHS: dict[str, str] = {}

    parts: list[LabelPart]
    font: Font
    text_color: str
    background_color: str
    text_anchor: str
    dominant_baseline: str
    letter_spacing: float | None

    def __init__(
        self,
        label: str,
        font: Font,
        text_color: str,
        background_color: str = "#FFF",
        text_anchor: str = "middle",
        dominant_baseline: str = "central",
        letter_spacing: float | None = None,
    ) -> None:
        """Initialize a Label by parsing the label string.

        Args:
            label: The label string to parse. Can contain Nerd Font tokens
                (%%nf-icon-name;) and separator characters.
            font: The primary font for text parts.
            text_color: The text color as a hex string.
            background_color: The background color for separators. Default: "#FFF".
            text_anchor: SVG text-anchor value. Default: "middle".
            dominant_baseline: SVG dominant-baseline value. Default: "central".
            letter_spacing: Optional letter spacing in SVG units.
        """
        self.parts = []
        self.font = font
        self.text_color = text_color
        self.background_color = background_color
        self.text_anchor = text_anchor
        self.dominant_baseline = dominant_baseline
        self.letter_spacing = letter_spacing
        self._parse_label(label)

    def __str__(self) -> str:
        """Return the concatenated text of all parts."""
        return "".join(p.text for p in self.parts)

    def __repr__(self) -> str:
        """Return a detailed representation of all label parts."""
        return f"Label[{', '.join(repr(p) for p in self.parts)}]"

    def add_text(self, text: str) -> None:
        """Add a text part to this label.

        Args:
            text: The text to add.
        """
        self.parts.append(TextPart(text, self.text_color, self.font))

    def add_separator(self, char: str) -> None:
        """Add a separator part to this label.

        Args:
            char: The separator character.
        """
        self.parts.append(SeparatorPart(char, self.background_color, self.font))

    def add_symbol(self, class_name: str, char: str) -> None:
        """Add a Nerd Font symbol part to this label.

        Args:
            class_name: The Nerd Font class name (e.g., "nf-fa-heart").
            char: The Unicode character for the symbol.
        """
        self.parts.append(SymbolPart(class_name, char, self.text_color))

    def measure_width(self, font_size: float) -> float:
        """Measure the total width of this label at a given font size.

        Args:
            font_size: The font size in points. Floats are accepted —
                ``Font.load`` rounds internally for the LRU cache.

        Returns:
            The total width in pixels.
        """
        width = 0.0
        for part in self.parts:
            width += part.measure_width(part.font.load(font_size))
        return width

    def measure_rendered_width(self, font_size: float) -> float:
        """Measure the label's width as it is actually painted in the SVG.

        Differs from :meth:`measure_width` in one detail: text parts
        are measured WITHOUT being upper-cased. ``measure_width`` is
        intended for keymap-key labels (which the renderer paints in
        all-caps), so ``TextPart.measure_width`` upper-cases before
        calling ``getlength``. For free-form text — tap-dance names,
        macro names, symbol-legend descriptions — that upper-casing
        over-estimates the rendered run by ~20% and leaves a visible
        gap between the text and its right-side decoration.

        Symbol and separator parts measure identically in both paths.
        """
        width = 0.0
        for part in self.parts:
            font = part.font.load(font_size)
            if isinstance(part, TextPart):
                width += font.getlength(part.text)
            else:
                width += part.measure_width(font)
        return width

    def size_to_fit(self, target_width: float, max_font_size: int, min_font_size: int = 1) -> int:
        """Find the largest font size that fits the label within target width.

        Uses binary search to find the optimal font size.

        Args:
            target_width: The maximum width in pixels.
            max_font_size: The maximum font size to try.
            min_font_size: The minimum font size to try. Default: 1.

        Returns:
            The largest font size that fits within target_width.
        """
        lo, hi = min_font_size, max_font_size
        result = min_font_size

        while lo <= hi:
            mid = (lo + hi) // 2
            text_width = self.measure_width(mid)

            if text_width <= target_width:
                result = mid
                lo = mid + 1
            else:
                hi = mid - 1

        return result

    def build_text(
        self,
        x: float,
        y: float,
        font_size: float,
        use_system_fonts: bool = False,
    ) -> draw.DrawingParentElement:
        """Build an SVG text element from this label.

        Args:
            x: The x coordinate for the text.
            y: The y coordinate for the text.
            font_size: The font size in SVG units. Floats are accepted —
                SVG ``font-size`` is unitless and renders at any
                precision.
            use_system_fonts: Whether to use system font families instead of embedded fonts.

        Returns:
            A drawsvg Text element with TSpan children for each part.
        """
        if not self.parts:
            return draw.Text(
                "",
                font_size,
                x,
                y,
                text_anchor=self.text_anchor,
                dominant_baseline=self.dominant_baseline,
                letter_spacing=self.letter_spacing,
            )

        first_font = (
            self.parts[0].font.get_system_font_family()
            if use_system_fonts
            else self.parts[0].font_family
        )
        text = draw.Text(
            self.parts[0].text,
            font_size,
            x,
            y,
            fill=self.parts[0].text_color,
            text_anchor=self.text_anchor,
            dominant_baseline=self.dominant_baseline,
            letter_spacing=self.letter_spacing,
            font_family=first_font,
        )
        for part in self.parts[1:]:
            part_font = part.font.get_system_font_family() if use_system_fonts else part.font_family
            text.append(
                draw.TSpan(
                    text=part.text,
                    fill=part.text_color,
                    font_family=part_font,
                    dominant_baseline=self.dominant_baseline,
                )
            )
        return text

    @property
    def _glyphs(self) -> dict[str, str]:
        """Get the Nerd Font glyphs dictionary, loading it if necessary."""
        if len(Label._GLYPHS) == 0:
            Label._GLYPHS = load_nerdfont_glyphs()
        return Label._GLYPHS

    @staticmethod
    def _is_nerd_font_token_start(label: str, pos: int, size: int) -> bool:
        """Check if a position marks the start of a Nerd Font token (%%...)."""
        return label[pos] == "%" and pos < (size - 3) and label[pos + 1] == "%"

    def _parse_nerd_font_token(
        self,
        label: str,
        start_pos: int,
        size: int,
    ) -> tuple[int, str | None, str | None]:
        """Parse a Nerd Font token from the label string."""
        nf_class = ""
        j = start_pos + 2
        while j < size and label[j] != ";":
            nf_class += label[j]
            j += 1

        if j >= size or label[j] != ";":
            return start_pos, None, None

        if not nf_class.startswith("nf-"):
            nf_class = f"nf-{nf_class}"

        char = self._glyphs.get(nf_class)
        return j, nf_class, char

    def _parse_label(self, label: str) -> None:
        """Parse the label string and populate the parts list."""
        part = ""
        label_size = len(label)
        i = 0

        while i < label_size:
            if Label._is_nerd_font_token_start(label, i, label_size):
                end_pos, nf_class, char = self._parse_nerd_font_token(label, i, label_size)
                if char and nf_class:
                    if part:
                        self.add_text(part)
                        part = ""
                    self.add_symbol(nf_class, char)
                    i = end_pos
                elif nf_class:
                    part += f"%%{nf_class};"
                    i = end_pos
                else:
                    part += label[i]
            elif label[i] == SEPARATOR_CHAR:
                if part:
                    self.add_text(part)
                    part = ""
                self.add_separator(label[i])
            else:
                part += label[i]
            i += 1

        if part:
            self.add_text(part)


class FontUsageAnalyzer:
    """Analyzes a SvalboardLayout to determine which characters are used from
    each font.

    Scans key labels and collects characters by font type for font subsetting.
    Font assignment: FINGER_KEY for finger clusters, THUMB_KEY for thumb
    clusters, TITLE for layer names, SYMBOLS for Nerd Font glyphs (%%nf-*
    tokens).
    """

    _char_sets: dict[Font, set[str]]

    def __init__(self) -> None:
        self._char_sets = {font: set() for font in Font}

    def analyze_keymap(
        self,
        layout: SvalboardLayout[LabelT],
        layer_name: str | None = None,
        copyright_text: str | None = None,
    ) -> None:
        """Analyze a Svalboard Layout (layer) to collect character usage for
        each font.

        Args:
            layout: The layout (a.k.a. layer) to analyze containing Label
                objects for each key.
            layer_name: Optional layer name to collect characters for the
                TITLE font.
            copyright_text: Optional copyright string to collect characters for
                the FINGER_KEY font (used by the footer).
        """
        for side in (layout.left, layout.right):
            for finger_cluster in side.fingers:
                for label in finger_cluster:
                    self._collect_from_label(label)
            for label in side.thumb:
                self._collect_from_label(label)

        if layer_name:
            self._collect_from_label(Label(layer_name, Font.TITLE, text_color="#000"))
        if copyright_text:
            self._collect_from_label(Label(copyright_text, Font.FINGER_KEY, text_color="#000"))

    def analyze_legend(
        self,
        macros: tuple[SvalboardMacro[SvalboardTargetKey], ...],
        tap_dances: tuple[SvalboardTapDance[SvalboardTargetKey], ...],
    ) -> None:
        """Analyze legend macros and tap-dances to collect character usage.

        Walks every macro action and tap-dance variant label to ensure the
        font subset includes glyphs that appear only in the legend.
        """
        for macro in macros:
            # Macro chip: name + per-action glyphs/keys/text
            if macro.name:
                self._collect_from_label(Label(macro.name, Font.FINGER_KEY, text_color="#000"))
            for action in macro.actions:
                for key in action.keys:
                    if key is not None and key.label:
                        self._collect_from_label(
                            Label(key.label, Font.FINGER_KEY, text_color="#000")
                        )
                if action.text:
                    self._collect_from_label(Label(action.text, Font.FINGER_KEY, text_color="#000"))
        for td in tap_dances:
            if td.name:
                self._collect_from_label(Label(td.name, Font.FINGER_KEY, text_color="#000"))
            for variant in (td.tap, td.hold, td.double_tap, td.tap_then_hold):
                if variant is not None and variant.label:
                    self._collect_from_label(
                        Label(variant.label, Font.FINGER_KEY, text_color="#000")
                    )

        # Chip glyphs — appear once per macro / tap-dance row.
        if macros:
            self._collect_from_label(
                Label("%%nf-md-script_text_play_outline;", Font.FINGER_KEY, text_color="#000")
            )
        if tap_dances:
            self._collect_from_label(
                Label("%%nf-md-keyboard_close;", Font.FINGER_KEY, text_color="#000")
            )

    def get_used_chars(self, font: Font) -> set[str]:
        """Get the set of characters used from a specific font."""
        return self._char_sets[font].copy()

    def _collect_from_label(self, label: Label | None) -> None:
        if not label:
            return
        unicode_symbols_cmap = _font_cmap(Font.UNICODE_SYMBOLS)
        for part in label.parts:
            part_cmap = _font_cmap(part.font)
            for ch in part.text:
                if ord(ch) in part_cmap:
                    self._char_sets[part.font].add(ch)
                elif ord(ch) in unicode_symbols_cmap:
                    # Routed through ``Font.UNICODE_SYMBOLS`` at
                    # render time (see ``parse_into_spans``); track
                    # it in that subset so the embedded font
                    # actually carries the glyph.
                    self._char_sets[Font.UNICODE_SYMBOLS].add(ch)
                else:
                    # In neither font — keep it in the requesting
                    # font's subset (it'll fall through to the
                    # browser's default at render time, but the
                    # placeholder ``.notdef`` glyph stays embedded).
                    self._char_sets[part.font].add(ch)


class FontSubsetter:
    """Subsets fonts based on characters used in a layer.

    Uses fonttools to create minimized font files containing only the glyphs
    needed for a specific layer, significantly reducing SVG file sizes.

    Works on a per-layer basis with FontUsageAnalyzer to determine which
    characters are needed from each font.

    Example:
        analyzer = FontUsageAnalyzer()
        analyzer.analyze_keymap(layout, layer_name="Base")

        subsetter = FontSubsetter(analyzer)
        css = subsetter.generate_subsetted_css()
    """

    _analyzer: FontUsageAnalyzer

    def __init__(self, analyzer: FontUsageAnalyzer) -> None:
        """Initialize the subsetter with a FontUsageAnalyzer."""
        self._analyzer = analyzer

    def generate_subsetted_css(self) -> str:
        """Generate CSS @font-face rules with subsetted font data."""
        from fontTools.subset import Options, Subsetter, load_font

        css_rules = []

        for font in Font:
            chars = self._analyzer.get_used_chars(font)

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

        chars = self._analyzer.get_used_chars(font)

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

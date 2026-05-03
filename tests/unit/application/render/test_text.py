# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.application.render.text module.

Covers the :class:`Font` enum (resource resolution, CSS embedding,
PIL font loading) and the :class:`FontUsageCollector` /
:class:`FontSubsetter` pipeline that produces auto-subsetted CSS
for an active render pass.
"""

from skim.application.render.text import (
    Font,
    FontSubsetter,
    FontUsageCollector,
    register_font_usage,
    using_font_usage_collector,
)


class TestFont:
    """Tests for Font enum."""

    def test_finger_key_font_exists(self):
        """FINGER_KEY font is defined."""
        assert Font.FINGER_KEY is not None
        assert Font.FINGER_KEY.value == "Finger-Key-Label"

    def test_thumb_key_font_exists(self):
        """THUMB_KEY font is defined."""
        assert Font.THUMB_KEY is not None
        assert Font.THUMB_KEY.value == "Thumb-Key-Label"

    def test_title_font_exists(self):
        """TITLE font is defined."""
        assert Font.TITLE is not None
        assert Font.TITLE.value == "Keymap-Title"

    def test_symbols_font_exists(self):
        """SYMBOLS font is defined."""
        assert Font.SYMBOLS is not None
        assert Font.SYMBOLS.value == "Key-Symbols"

    def test_unicode_symbols_font_exists(self):
        """UNICODE_SYMBOLS font is defined."""
        assert Font.UNICODE_SYMBOLS is not None
        assert Font.UNICODE_SYMBOLS.value == "Unicode-Symbols"

    def test_font_has_path(self):
        """Font has a path attribute."""
        assert Font.FINGER_KEY.path is not None

    def test_css_style_generates_font_face(self):
        """css_style property generates @font-face rule."""
        css = Font.FINGER_KEY.css_style
        assert "@font-face" in css
        assert "font-family" in css
        assert Font.FINGER_KEY.value in css
        assert "base64" in css

    def test_load_font(self):
        """load method returns a PIL ImageFont."""
        font = Font.FINGER_KEY.load(12)
        assert font is not None
        assert hasattr(font, "getlength")

    def test_load_font_with_different_sizes(self):
        """load method handles different font sizes."""
        font_small = Font.FINGER_KEY.load(8)
        font_large = Font.FINGER_KEY.load(24)
        assert font_small is not None
        assert font_large is not None


class TestFontUsageCollector:
    """Tests for the auto font-usage collector."""

    def test_add_accumulates_chars(self):
        """add registers every character against the requesting font."""
        c = FontUsageCollector()
        c.add(Font.FINGER_KEY, "abc")
        c.add(Font.FINGER_KEY, "bcd")
        assert c.get_used_chars(Font.FINGER_KEY) == {"a", "b", "c", "d"}

    def test_add_partitions_by_font(self):
        """Different fonts accumulate independently."""
        c = FontUsageCollector()
        c.add(Font.FINGER_KEY, "abc")
        c.add(Font.THUMB_KEY, "xyz")
        assert c.get_used_chars(Font.FINGER_KEY) == {"a", "b", "c"}
        assert c.get_used_chars(Font.THUMB_KEY) == {"x", "y", "z"}
        assert c.get_used_chars(Font.TITLE) == set()

    def test_add_empty_text_is_noop(self):
        """Empty text doesn't register anything."""
        c = FontUsageCollector()
        c.add(Font.FINGER_KEY, "")
        assert c.get_used_chars(Font.FINGER_KEY) == set()

    def test_get_used_chars_returns_copy(self):
        """The returned set can be mutated without disturbing the collector."""
        c = FontUsageCollector()
        c.add(Font.FINGER_KEY, "abc")
        snapshot = c.get_used_chars(Font.FINGER_KEY)
        snapshot.add("z")
        assert "z" not in c.get_used_chars(Font.FINGER_KEY)


class TestRegisterFontUsage:
    """``register_font_usage`` is a no-op outside an active collector
    and writes through to the active one when present."""

    def test_no_active_collector_is_noop(self):
        """Calling without an active collector doesn't raise."""
        register_font_usage(Font.FINGER_KEY, "abc")  # would raise if no-op was wrong

    def test_writes_through_active_collector(self):
        """Inside the manager, characters land in the yielded collector."""
        with using_font_usage_collector() as collector:
            register_font_usage(Font.FINGER_KEY, "abc")
        assert collector.get_used_chars(Font.FINGER_KEY) == {"a", "b", "c"}

    def test_nested_collectors_isolate(self):
        """Each nested ``using_font_usage_collector`` block isolates its own state."""
        with using_font_usage_collector() as outer:
            register_font_usage(Font.FINGER_KEY, "ab")
            with using_font_usage_collector() as inner:
                register_font_usage(Font.FINGER_KEY, "xy")
            register_font_usage(Font.FINGER_KEY, "cd")
        assert outer.get_used_chars(Font.FINGER_KEY) == {"a", "b", "c", "d"}
        assert inner.get_used_chars(Font.FINGER_KEY) == {"x", "y"}


class TestFontSubsetter:
    """Tests for FontSubsetter using a populated collector."""

    def test_subsetted_css_includes_only_used_fonts(self):
        """Fonts with no registered chars are skipped in subset CSS."""
        c = FontUsageCollector()
        c.add(Font.FINGER_KEY, "ABC")
        css = FontSubsetter(c).generate_subsetted_css()
        assert "@font-face" in css
        assert Font.FINGER_KEY.value in css
        # No chars registered against TITLE or SYMBOLS — they shouldn't
        # appear in the subset.
        assert Font.TITLE.value not in css
        assert Font.SYMBOLS.value not in css

    def test_empty_collector_returns_empty_subset(self):
        """A collector with no registered chars produces no subset."""
        c = FontUsageCollector()
        css = FontSubsetter(c).generate_subsetted_css()
        assert css == ""

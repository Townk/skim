"""Unit tests for FontUsageAnalyzer class."""

from skim.application.render.text import Font, FontUsageAnalyzer, SeparatorPart
from skim.data.keyboard import (
    FingerCluster,
    SplitSide,
    SvalboardKeymap,
    SvalboardLayout,
    ThumbCluster,
)
from skim.domain.domain_types import SvalboardTargetKey


def make_key(label: str = "", layer_switch: int | None = None) -> SvalboardTargetKey:
    return SvalboardTargetKey(label=label, layer_switch=layer_switch)


def make_finger_cluster(label: str = "") -> FingerCluster[SvalboardTargetKey]:
    return FingerCluster(make_key(label))


def make_thumb_cluster(label: str = "") -> ThumbCluster[SvalboardTargetKey]:
    return ThumbCluster(make_key(label))


def make_split_side(finger_label: str = "", thumb_label: str = "") -> SplitSide[SvalboardTargetKey]:
    return SplitSide(
        index=make_finger_cluster(finger_label),
        middle=make_finger_cluster(finger_label),
        ring=make_finger_cluster(finger_label),
        pinky=make_finger_cluster(finger_label),
        thumb=make_thumb_cluster(thumb_label),
    )


def make_layout(
    finger_label: str = "", thumb_label: str = ""
) -> SvalboardLayout[SvalboardTargetKey]:
    return SvalboardLayout(
        left=make_split_side(finger_label, thumb_label),
        right=make_split_side(finger_label, thumb_label),
    )


def make_keymap(
    layers: list[SvalboardLayout[SvalboardTargetKey]],
) -> SvalboardKeymap[SvalboardTargetKey]:
    return SvalboardKeymap(layers=layers)


class TestFontUsageAnalyzerInit:
    def test_init_creates_char_sets_for_all_fonts(self):
        analyzer = FontUsageAnalyzer()

        for font in Font:
            chars = analyzer.get_used_chars(font)
            assert isinstance(chars, set)

    def test_init_includes_ascii_safety_margin(self):
        analyzer = FontUsageAnalyzer()
        expected_ascii = {chr(i) for i in range(32, 127)}

        for font in Font:
            chars = analyzer.get_used_chars(font)
            assert expected_ascii.issubset(chars)

    def test_init_includes_separator_in_finger_key_font(self):
        analyzer = FontUsageAnalyzer()
        chars = analyzer.get_used_chars(Font.FINGER_KEY)

        assert SeparatorPart.SEPARATOR_CHAR in chars

    def test_init_includes_separator_in_thumb_key_font(self):
        analyzer = FontUsageAnalyzer()
        chars = analyzer.get_used_chars(Font.THUMB_KEY)

        assert SeparatorPart.SEPARATOR_CHAR in chars


class TestFontUsageAnalyzerGetUsedChars:
    def test_get_used_chars_returns_copy(self):
        analyzer = FontUsageAnalyzer()
        chars1 = analyzer.get_used_chars(Font.FINGER_KEY)
        chars2 = analyzer.get_used_chars(Font.FINGER_KEY)

        assert chars1 == chars2
        assert chars1 is not chars2

    def test_modifying_returned_set_does_not_affect_analyzer(self):
        analyzer = FontUsageAnalyzer()
        chars = analyzer.get_used_chars(Font.FINGER_KEY)
        original_len = len(chars)

        chars.add("EXTRA_CHAR_NOT_IN_ORIGINAL")
        new_chars = analyzer.get_used_chars(Font.FINGER_KEY)

        assert len(new_chars) == original_len


class TestFontUsageAnalyzerAnalyzeKeymap:
    def test_analyze_empty_keymap(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([])
        ascii_count = 127 - 32

        analyzer.analyze_keymap(keymap)

        for font in Font:
            chars = analyzer.get_used_chars(font)
            assert len(chars) >= ascii_count

    def test_analyze_finger_cluster_labels_go_to_finger_key_font(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout(finger_label="XYZ")])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "X" in finger_chars
        assert "Y" in finger_chars
        assert "Z" in finger_chars

    def test_analyze_thumb_cluster_labels_go_to_thumb_key_font(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout(thumb_label="ABC")])

        analyzer.analyze_keymap(keymap)

        thumb_chars = analyzer.get_used_chars(Font.THUMB_KEY)
        assert "A" in thumb_chars
        assert "B" in thumb_chars
        assert "C" in thumb_chars

    def test_finger_labels_not_in_thumb_font_beyond_ascii(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout(finger_label="\u00e9")])

        analyzer.analyze_keymap(keymap)

        thumb_chars = analyzer.get_used_chars(Font.THUMB_KEY)
        assert "\u00e9" not in thumb_chars

    def test_thumb_labels_not_in_finger_font_beyond_ascii(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout(thumb_label="\u00e9")])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "\u00e9" not in finger_chars

    def test_analyze_multiple_layers(self):
        analyzer = FontUsageAnalyzer()
        layer1 = make_layout(finger_label="ABC")
        layer2 = make_layout(finger_label="DEF")
        keymap = make_keymap([layer1, layer2])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "A" in finger_chars
        assert "D" in finger_chars

    def test_analyze_collects_from_both_sides(self):
        analyzer = FontUsageAnalyzer()
        layout = SvalboardLayout(
            left=SplitSide(
                index=FingerCluster(make_key("L")),
                middle=make_finger_cluster(),
                ring=make_finger_cluster(),
                pinky=make_finger_cluster(),
                thumb=make_thumb_cluster(),
            ),
            right=SplitSide(
                index=FingerCluster(make_key("R")),
                middle=make_finger_cluster(),
                ring=make_finger_cluster(),
                pinky=make_finger_cluster(),
                thumb=make_thumb_cluster(),
            ),
        )
        keymap = make_keymap([layout])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "L" in finger_chars
        assert "R" in finger_chars

    def test_analyze_empty_labels_handled(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout()])
        ascii_count = 127 - 32

        analyzer.analyze_keymap(keymap)

        for font in Font:
            chars = analyzer.get_used_chars(font)
            assert len(chars) >= ascii_count


class TestFontUsageAnalyzerLayerNames:
    def test_layer_names_go_to_title_font(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout()])

        analyzer.analyze_keymap(keymap, layer_names=["Base", "Nav"])

        title_chars = analyzer.get_used_chars(Font.TITLE)
        assert "B" in title_chars
        assert "a" in title_chars
        assert "s" in title_chars
        assert "e" in title_chars
        assert "N" in title_chars
        assert "v" in title_chars

    def test_no_layer_names_parameter(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout()])
        ascii_count = 127 - 32

        analyzer.analyze_keymap(keymap)

        title_chars = analyzer.get_used_chars(Font.TITLE)
        assert len(title_chars) >= ascii_count

    def test_empty_layer_names_list(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout()])
        ascii_count = 127 - 32

        analyzer.analyze_keymap(keymap, layer_names=[])

        title_chars = analyzer.get_used_chars(Font.TITLE)
        assert len(title_chars) >= ascii_count

    def test_layer_names_with_unicode(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout()])

        analyzer.analyze_keymap(keymap, layer_names=["\u00c9tage"])

        title_chars = analyzer.get_used_chars(Font.TITLE)
        assert "\u00c9" in title_chars


class TestFontUsageAnalyzerNerdFontSymbols:
    def test_nerd_font_symbols_go_to_symbols_font(self):
        analyzer = FontUsageAnalyzer()
        ascii_count = 127 - 32
        layout = SvalboardLayout(
            left=SplitSide(
                index=FingerCluster(make_key("%%nf-md-home;")),
                middle=make_finger_cluster(),
                ring=make_finger_cluster(),
                pinky=make_finger_cluster(),
                thumb=make_thumb_cluster(),
            ),
            right=make_split_side(),
        )
        keymap = make_keymap([layout])

        analyzer.analyze_keymap(keymap)

        symbol_chars = analyzer.get_used_chars(Font.SYMBOLS)
        assert len(symbol_chars) > ascii_count

    def test_mixed_text_and_symbols(self):
        analyzer = FontUsageAnalyzer()
        layout = SvalboardLayout(
            left=SplitSide(
                index=FingerCluster(make_key("Home%%nf-md-home;")),
                middle=make_finger_cluster(),
                ring=make_finger_cluster(),
                pinky=make_finger_cluster(),
                thumb=make_thumb_cluster(),
            ),
            right=make_split_side(),
        )
        keymap = make_keymap([layout])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "H" in finger_chars
        assert "o" in finger_chars
        assert "m" in finger_chars
        assert "e" in finger_chars


class TestFontUsageAnalyzerSeparators:
    def test_separator_in_label_collected_for_font(self):
        analyzer = FontUsageAnalyzer()
        sep = SeparatorPart.SEPARATOR_CHAR
        keymap = make_keymap([make_layout(finger_label=f"A{sep}B")])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "A" in finger_chars
        assert "B" in finger_chars
        assert sep in finger_chars


class TestFontUsageAnalyzerUnicode:
    def test_unicode_characters_collected(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout(finger_label="\u03b1\u03b2\u03b3")])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "\u03b1" in finger_chars
        assert "\u03b2" in finger_chars
        assert "\u03b3" in finger_chars

    def test_emoji_collected(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout(finger_label="\U0001f600")])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "\U0001f600" in finger_chars


class TestFontUsageAnalyzerAllFonts:
    def test_all_font_types_can_be_queried(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout(finger_label="F", thumb_label="T")])

        analyzer.analyze_keymap(keymap, layer_names=["Layer"])

        assert analyzer.get_used_chars(Font.FINGER_KEY)
        assert analyzer.get_used_chars(Font.THUMB_KEY)
        assert analyzer.get_used_chars(Font.TITLE)
        assert analyzer.get_used_chars(Font.SYMBOLS)

    def test_repeated_analysis_accumulates(self):
        analyzer = FontUsageAnalyzer()
        keymap1 = make_keymap([make_layout(finger_label="ABC")])
        keymap2 = make_keymap([make_layout(finger_label="DEF")])

        analyzer.analyze_keymap(keymap1)
        analyzer.analyze_keymap(keymap2)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "A" in finger_chars
        assert "D" in finger_chars


class TestFontUsageAnalyzerEdgeCases:
    def test_very_long_label(self):
        analyzer = FontUsageAnalyzer()
        long_label = "A" * 1000
        keymap = make_keymap([make_layout(finger_label=long_label)])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "A" in finger_chars

    def test_whitespace_in_labels(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout(finger_label="A B\tC")])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert " " in finger_chars
        assert "\t" in finger_chars

    def test_special_characters(self):
        analyzer = FontUsageAnalyzer()
        keymap = make_keymap([make_layout(finger_label="<>&'\"")])

        analyzer.analyze_keymap(keymap)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "<" in finger_chars
        assert ">" in finger_chars
        assert "&" in finger_chars
        assert "'" in finger_chars
        assert '"' in finger_chars

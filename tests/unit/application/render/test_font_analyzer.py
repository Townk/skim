"""Unit tests for FontUsageAnalyzer and FontSubsetter classes."""

from skim.application.render.text import Font, FontSubsetter, FontUsageAnalyzer, Label
from skim.data.keyboard import (
    FingerCluster,
    SplitSide,
    SvalboardLayout,
    ThumbCluster,
)


def make_label(text: str = "", font: Font = Font.FINGER_KEY) -> Label:
    """Create a Label with the given text and font."""
    return Label(text, font, text_color="#000")


def make_finger_cluster(label_text: str = "") -> FingerCluster[Label]:
    return FingerCluster(make_label(label_text, Font.FINGER_KEY))


def make_thumb_cluster(label_text: str = "") -> ThumbCluster[Label]:
    return ThumbCluster(make_label(label_text, Font.THUMB_KEY))


def make_split_side(finger_label: str = "", thumb_label: str = "") -> SplitSide[Label]:
    return SplitSide(
        index=make_finger_cluster(finger_label),
        middle=make_finger_cluster(finger_label),
        ring=make_finger_cluster(finger_label),
        pinky=make_finger_cluster(finger_label),
        thumb=make_thumb_cluster(thumb_label),
    )


def make_layout(finger_label: str = "", thumb_label: str = "") -> SvalboardLayout[Label]:
    return SvalboardLayout(
        left=make_split_side(finger_label, thumb_label),
        right=make_split_side(finger_label, thumb_label),
    )


class TestFontUsageAnalyzerInit:
    """Tests for FontUsageAnalyzer initialization."""

    def test_init_creates_empty_char_sets_for_all_fonts(self):
        analyzer = FontUsageAnalyzer()

        for font in Font:
            chars = analyzer.get_used_chars(font)
            assert len(chars) == 0


class TestFontSubsetterInit:
    def test_init_with_analyzer(self):
        analyzer = FontUsageAnalyzer()
        subsetter = FontSubsetter(analyzer)
        assert subsetter._analyzer is analyzer


class TestFontSubsetterSubsetFont:
    def test_subset_font_returns_bytes_for_used_font(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="ABC")
        analyzer.analyze_keymap(layout)
        subsetter = FontSubsetter(analyzer)

        result = subsetter.subset_font(Font.FINGER_KEY)
        assert result is not None
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_subset_font_returns_none_for_unused_font(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="ABC")
        analyzer.analyze_keymap(layout)
        subsetter = FontSubsetter(analyzer)

        result = subsetter.subset_font(Font.THUMB_KEY)
        assert result is None

    def test_subset_font_reduces_size(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="ABCD")
        analyzer.analyze_keymap(layout)
        subsetter = FontSubsetter(analyzer)

        original_size = Font.FINGER_KEY.path.stat().st_size
        subsetted_data = subsetter.subset_font(Font.FINGER_KEY)
        assert subsetted_data is not None
        assert len(subsetted_data) < original_size

    def test_subset_font_different_fonts_independent(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="F", thumb_label="T")
        analyzer.analyze_keymap(layout)
        subsetter = FontSubsetter(analyzer)

        finger_data = subsetter.subset_font(Font.FINGER_KEY)
        thumb_data = subsetter.subset_font(Font.THUMB_KEY)

        assert finger_data is not None
        assert thumb_data is not None
        assert finger_data != thumb_data


class TestFontSubsetterGenerateCSS:
    def test_generate_css_returns_string(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="ABC")
        analyzer.analyze_keymap(layout, layer_name="Test")
        subsetter = FontSubsetter(analyzer)

        css = subsetter.generate_subsetted_css()
        assert isinstance(css, str)
        assert "@font-face" in css
        assert "Finger-Key-Label" in css
        assert "Keymap-Title" in css

    def test_generate_css_contains_base64_data(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="AB")
        analyzer.analyze_keymap(layout)
        subsetter = FontSubsetter(analyzer)

        css = subsetter.generate_subsetted_css()
        assert "data:font/ttf;base64," in css

    def test_generate_css_empty_when_no_chars(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout()
        analyzer.analyze_keymap(layout)
        subsetter = FontSubsetter(analyzer)

        css = subsetter.generate_subsetted_css()
        assert css == ""

    def test_generate_css_multiple_fonts(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="F", thumb_label="T")
        analyzer.analyze_keymap(layout, layer_name="Test")
        subsetter = FontSubsetter(analyzer)

        css = subsetter.generate_subsetted_css()
        assert css.count("@font-face") >= 2


class TestFontSubsetterSizeReduction:
    def test_get_size_reduction_returns_tuple(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="ABC")
        analyzer.analyze_keymap(layout)
        subsetter = FontSubsetter(analyzer)

        original, subsetted = subsetter.get_size_reduction(Font.FINGER_KEY)
        assert isinstance(original, int)
        assert isinstance(subsetted, int)
        assert original > 0
        assert subsetted > 0
        assert subsetted < original

    def test_get_size_reduction_unused_font(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="ABC")
        analyzer.analyze_keymap(layout)
        subsetter = FontSubsetter(analyzer)

        original, subsetted = subsetter.get_size_reduction(Font.THUMB_KEY)
        assert original > 0
        assert subsetted == 0


class TestFontSubsetterPerLayer:
    def test_subsetter_per_layer_isolation(self):
        layer1_analyzer = FontUsageAnalyzer()
        layer1_layout = make_layout(finger_label="ABC")
        layer1_analyzer.analyze_keymap(layer1_layout, layer_name="Layer1")
        layer1_subsetter = FontSubsetter(layer1_analyzer)

        layer2_analyzer = FontUsageAnalyzer()
        layer2_layout = make_layout(finger_label="DEF")
        layer2_analyzer.analyze_keymap(layer2_layout, layer_name="Layer2")
        layer2_subsetter = FontSubsetter(layer2_analyzer)

        layer1_css = layer1_subsetter.generate_subsetted_css()
        layer2_css = layer2_subsetter.generate_subsetted_css()

        assert "Layer1" not in layer2_css
        assert "Layer2" not in layer1_css

    def test_subsetter_different_chars_per_layer(self):
        analyzer1 = FontUsageAnalyzer()
        analyzer1.analyze_keymap(make_layout(finger_label="ABC"))
        subsetter1 = FontSubsetter(analyzer1)

        analyzer2 = FontUsageAnalyzer()
        analyzer2.analyze_keymap(make_layout(finger_label="XYZ"))
        subsetter2 = FontSubsetter(analyzer2)

        css1 = subsetter1.generate_subsetted_css()
        css2 = subsetter2.generate_subsetted_css()

        assert len(css1) > 0
        assert len(css2) > 0


class TestFontUsageAnalyzerGetUsedChars:
    def test_get_used_chars_returns_copy(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="A")
        analyzer.analyze_keymap(layout)

        chars1 = analyzer.get_used_chars(Font.FINGER_KEY)
        chars2 = analyzer.get_used_chars(Font.FINGER_KEY)

        assert chars1 == chars2
        assert chars1 is not chars2

    def test_modifying_returned_set_does_not_affect_analyzer(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="A")
        analyzer.analyze_keymap(layout)

        chars = analyzer.get_used_chars(Font.FINGER_KEY)
        original_len = len(chars)

        chars.add("EXTRA_CHAR")
        new_chars = analyzer.get_used_chars(Font.FINGER_KEY)

        assert len(new_chars) == original_len


class TestFontUsageAnalyzerAnalyzeKeymap:
    def test_analyze_empty_layout(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout()

        analyzer.analyze_keymap(layout)

        for font in Font:
            chars = analyzer.get_used_chars(font)
            assert len(chars) == 0

    def test_analyze_finger_cluster_labels_go_to_finger_key_font(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="XYZ")

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "X" in finger_chars
        assert "Y" in finger_chars
        assert "Z" in finger_chars

    def test_analyze_thumb_cluster_labels_go_to_thumb_key_font(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(thumb_label="ABC")

        analyzer.analyze_keymap(layout)

        thumb_chars = analyzer.get_used_chars(Font.THUMB_KEY)
        assert "A" in thumb_chars
        assert "B" in thumb_chars
        assert "C" in thumb_chars

    def test_finger_labels_not_in_thumb_font(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="é")

        analyzer.analyze_keymap(layout)

        thumb_chars = analyzer.get_used_chars(Font.THUMB_KEY)
        assert "é" not in thumb_chars

    def test_thumb_labels_not_in_finger_font(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(thumb_label="é")

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "é" not in finger_chars

    def test_analyze_collects_from_both_sides(self):
        analyzer = FontUsageAnalyzer()
        layout = SvalboardLayout(
            left=SplitSide(
                index=FingerCluster(make_label("L", Font.FINGER_KEY)),
                middle=make_finger_cluster(),
                ring=make_finger_cluster(),
                pinky=make_finger_cluster(),
                thumb=make_thumb_cluster(),
            ),
            right=SplitSide(
                index=FingerCluster(make_label("R", Font.FINGER_KEY)),
                middle=make_finger_cluster(),
                ring=make_finger_cluster(),
                pinky=make_finger_cluster(),
                thumb=make_thumb_cluster(),
            ),
        )

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "L" in finger_chars
        assert "R" in finger_chars

    def test_analyze_all_finger_clusters(self):
        analyzer = FontUsageAnalyzer()
        layout = SvalboardLayout(
            left=SplitSide(
                index=FingerCluster(make_label("I", Font.FINGER_KEY)),
                middle=FingerCluster(make_label("M", Font.FINGER_KEY)),
                ring=FingerCluster(make_label("R", Font.FINGER_KEY)),
                pinky=FingerCluster(make_label("P", Font.FINGER_KEY)),
                thumb=make_thumb_cluster(),
            ),
            right=make_split_side(),
        )

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "I" in finger_chars
        assert "M" in finger_chars
        assert "R" in finger_chars
        assert "P" in finger_chars

    def test_analyze_all_thumb_keys(self):
        analyzer = FontUsageAnalyzer()
        layout = SvalboardLayout(
            left=SplitSide(
                index=make_finger_cluster(),
                middle=make_finger_cluster(),
                ring=make_finger_cluster(),
                pinky=make_finger_cluster(),
                thumb=ThumbCluster(
                    down_key=make_label("D", Font.THUMB_KEY),
                    pad_key=make_label("P", Font.THUMB_KEY),
                    up_key=make_label("U", Font.THUMB_KEY),
                    nail_key=make_label("N", Font.THUMB_KEY),
                    knuckle_key=make_label("K", Font.THUMB_KEY),
                    double_down_key=make_label("X", Font.THUMB_KEY),
                ),
            ),
            right=make_split_side(),
        )

        analyzer.analyze_keymap(layout)

        thumb_chars = analyzer.get_used_chars(Font.THUMB_KEY)
        assert "D" in thumb_chars
        assert "P" in thumb_chars
        assert "U" in thumb_chars
        assert "N" in thumb_chars
        assert "K" in thumb_chars
        assert "X" in thumb_chars


class TestFontUsageAnalyzerLayerName:
    def test_layer_name_goes_to_title_font(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout()

        analyzer.analyze_keymap(layout, layer_name="Base Layer")

        title_chars = analyzer.get_used_chars(Font.TITLE)
        assert "B" in title_chars
        assert "a" in title_chars
        assert "s" in title_chars
        assert "e" in title_chars
        assert " " in title_chars
        assert "L" in title_chars
        assert "y" in title_chars

    def test_no_layer_name_parameter(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout()

        analyzer.analyze_keymap(layout)

        title_chars = analyzer.get_used_chars(Font.TITLE)
        assert len(title_chars) == 0

    def test_empty_layer_name(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout()

        analyzer.analyze_keymap(layout, layer_name="")

        title_chars = analyzer.get_used_chars(Font.TITLE)
        assert len(title_chars) == 0

    def test_layer_name_with_unicode(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout()

        analyzer.analyze_keymap(layout, layer_name="Étage")

        title_chars = analyzer.get_used_chars(Font.TITLE)
        assert "É" in title_chars
        assert "t" in title_chars
        assert "a" in title_chars
        assert "g" in title_chars
        assert "e" in title_chars


class TestFontUsageAnalyzerNerdFontSymbols:
    def test_nerd_font_symbols_go_to_symbols_font(self):
        analyzer = FontUsageAnalyzer()
        layout = SvalboardLayout(
            left=SplitSide(
                index=FingerCluster(make_label("%%nf-md-home;", Font.FINGER_KEY)),
                middle=make_finger_cluster(),
                ring=make_finger_cluster(),
                pinky=make_finger_cluster(),
                thumb=make_thumb_cluster(),
            ),
            right=make_split_side(),
        )

        analyzer.analyze_keymap(layout)

        symbol_chars = analyzer.get_used_chars(Font.SYMBOLS)
        assert len(symbol_chars) > 0

    def test_mixed_text_and_symbols(self):
        analyzer = FontUsageAnalyzer()
        layout = SvalboardLayout(
            left=SplitSide(
                index=FingerCluster(make_label("Home%%nf-md-home;", Font.FINGER_KEY)),
                middle=make_finger_cluster(),
                ring=make_finger_cluster(),
                pinky=make_finger_cluster(),
                thumb=make_thumb_cluster(),
            ),
            right=make_split_side(),
        )

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "H" in finger_chars
        assert "o" in finger_chars
        assert "m" in finger_chars
        assert "e" in finger_chars

        symbol_chars = analyzer.get_used_chars(Font.SYMBOLS)
        assert len(symbol_chars) > 0


class TestFontUsageAnalyzerSeparators:
    def test_separator_in_label_collected_for_font(self):
        from skim.domain.domain_types import SEPARATOR_CHAR

        analyzer = FontUsageAnalyzer()
        sep = SEPARATOR_CHAR
        layout = make_layout(finger_label=f"A{sep}B")

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "A" in finger_chars
        assert "B" in finger_chars
        assert sep in finger_chars


class TestFontUsageAnalyzerUnicode:
    def test_unicode_characters_collected(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="αβγ")

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "α" in finger_chars
        assert "β" in finger_chars
        assert "γ" in finger_chars

    def test_emoji_collected(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="😀")

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "😀" in finger_chars


class TestFontUsageAnalyzerAllFonts:
    def test_all_font_types_can_be_queried(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="F", thumb_label="T")

        analyzer.analyze_keymap(layout, layer_name="Layer")

        assert analyzer.get_used_chars(Font.FINGER_KEY)
        assert analyzer.get_used_chars(Font.THUMB_KEY)
        assert analyzer.get_used_chars(Font.TITLE)

    def test_repeated_analysis_accumulates(self):
        analyzer = FontUsageAnalyzer()
        layout1 = make_layout(finger_label="ABC")
        layout2 = make_layout(finger_label="DEF")

        analyzer.analyze_keymap(layout1)
        analyzer.analyze_keymap(layout2)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "A" in finger_chars
        assert "D" in finger_chars


class TestFontUsageAnalyzerEdgeCases:
    def test_very_long_label(self):
        analyzer = FontUsageAnalyzer()
        long_label = "A" * 1000
        layout = make_layout(finger_label=long_label)

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "A" in finger_chars

    def test_whitespace_in_labels(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="A B\tC")

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert " " in finger_chars
        assert "\t" in finger_chars

    def test_special_characters(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout(finger_label="<>&'\"")

        analyzer.analyze_keymap(layout)

        finger_chars = analyzer.get_used_chars(Font.FINGER_KEY)
        assert "<" in finger_chars
        assert ">" in finger_chars
        assert "&" in finger_chars
        assert "'" in finger_chars
        assert '"' in finger_chars

    def test_empty_labels_skipped(self):
        analyzer = FontUsageAnalyzer()
        layout = make_layout()

        analyzer.analyze_keymap(layout)

        for font in Font:
            chars = analyzer.get_used_chars(font)
            assert len(chars) == 0


class TestFontSubsetterFullFontsCSS:
    def test_generate_full_fonts_css_returns_css_for_all_fonts(self):
        analyzer = FontUsageAnalyzer()
        subsetter = FontSubsetter(analyzer)

        css = subsetter.generate_full_fonts_css()

        assert "@font-face" in css
        assert len([line for line in css.split("\n") if "font-family" in line]) == len(Font)

    def test_generate_full_fonts_css_contains_base64(self):
        analyzer = FontUsageAnalyzer()
        subsetter = FontSubsetter(analyzer)

        css = subsetter.generate_full_fonts_css()

        assert "data:font/ttf;base64," in css


class TestFontSystemFonts:
    def test_font_get_system_font_family(self):
        assert "Roboto" in Font.FINGER_KEY.get_system_font_family()
        assert "Roboto Black" in Font.THUMB_KEY.get_system_font_family()
        assert "Roboto Thin" in Font.TITLE.get_system_font_family()
        assert "Nerd Font" in Font.SYMBOLS.get_system_font_family()

    def test_label_build_text_uses_system_fonts(self):
        label = Label("Test", Font.FINGER_KEY, text_color="#000")
        text_elem = label.build_text(x=0, y=0, font_size=12, use_system_fonts=True)
        import drawsvg as draw

        d = draw.Drawing(100, 100)
        d.append(text_elem)
        svg_output = d.as_svg()
        assert "Roboto" in svg_output

    def test_label_build_text_uses_embedded_fonts_by_default(self):
        label = Label("Test", Font.FINGER_KEY, text_color="#000")
        text_elem = label.build_text(x=0, y=0, font_size=12, use_system_fonts=False)
        import drawsvg as draw

        d = draw.Drawing(100, 100)
        d.append(text_elem)
        svg_output = d.as_svg()
        assert Font.FINGER_KEY.value in svg_output

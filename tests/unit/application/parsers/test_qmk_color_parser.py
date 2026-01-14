"""Unit tests for QmkColorParser."""

from skim.application.parsers.qmk_color_parser import QmkColorParser


class TestQmkColorParser:
    """Test parsing of QMK color.h file."""

    def test_parse_hsv_definitions(self):
        """Parse HSV definitions and convert to hex."""
        content = """
        #define HSV_AZURE       132, 102, 255
        #define HSV_BLACK         0,   0,   0
        #define HSV_WHITE         0,   0, 255
        """
        parser = QmkColorParser()
        colors = parser.parse(content)

        assert "AZURE" in colors
        assert "BLACK" in colors
        assert "WHITE" in colors

        assert colors["BLACK"] == "#000000"
        assert colors["WHITE"] == "#FFFFFF"  # h=0,s=0,v=1 -> white

    def test_parse_rgb_definitions(self):
        """Parse RGB definitions (fallback/additional)."""
        content = """
        #define RGB_RED         0xFF, 0x00, 0x00
        #define RGB_GREEN       0, 255, 0
        """
        parser = QmkColorParser()
        colors = parser.parse(content)

        assert colors["RED"] == "#FF0000"
        assert colors["GREEN"] == "#00FF00"

    def test_parse_mixed_priority(self):
        """Ensure HSV takes priority or handles overlap."""
        # If both defined, implementation choice.
        # Usually checking one then other.
        content = """
        #define RGB_TEST 0xFF, 0x00, 0x00
        #define HSV_TEST 0, 255, 255
        """
        parser = QmkColorParser()
        colors = parser.parse(content)

        assert "TEST" in colors
        assert colors["TEST"] == "#FF0000"

    def test_ignore_aliases(self):
        """Ignore alias definitions like #define HSV_OFF HSV_BLACK."""
        content = """
        #define HSV_OFF HSV_BLACK
        """
        parser = QmkColorParser()
        colors = parser.parse(content)

        # Should be empty or resolved?
        # Simpler to ignore non-numeric definitions for now
        assert "OFF" not in colors

    def test_parse_malformed_macros(self):
        """Handle malformed macros gracefully."""
        content = """
        #define RGB_BAD 0xGG, 0x00, 0x00
        """
        # 0xGG is invalid hex, int(..., 0) raises ValueError
        parser = QmkColorParser()
        colors = parser.parse(content)
        assert "BAD" not in colors

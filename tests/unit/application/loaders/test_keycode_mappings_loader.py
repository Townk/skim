"""Unit tests for skim.application.loaders.keycode_mappings_loader module.

Tests cover keycode mappings loading and merging with user overrides.
"""

from collections.abc import Mapping

from skim.application.loaders import load_keycode_mappings
from skim.data.config import Keycode, Keycodes


class TestLoadKeycodeMappings:
    """Tests for load_keycode_mappings function."""

    def test_returns_mapping(self):
        """Function returns a mapping type."""
        keycodes_config = Keycodes()
        mappings = load_keycode_mappings(keycodes_config)
        assert isinstance(mappings, Mapping)

    def test_mappings_has_expected_keys(self):
        """Mappings has expected top-level keys."""
        keycodes_config = Keycodes()
        mappings = load_keycode_mappings(keycodes_config)

        # These keys should exist in the bundled mappings
        expected_keys = ["keycodes", "pre_processing", "macro_functions", "modifier_union"]
        for key in expected_keys:
            assert key in mappings, f"Missing expected key: {key}"

    def test_common_keycodes_present(self):
        """Common keycodes are present in mappings."""
        keycodes_config = Keycodes()
        mappings = load_keycode_mappings(keycodes_config)
        keycodes = mappings.get("keycodes", {})

        # Check for some common QMK keycodes
        common_codes = ["KC_A", "KC_B", "KC_SPACE", "KC_ENTER"]
        for code in common_codes:
            assert code in keycodes, f"Missing common keycode: {code}"


class TestLoadKeycodeMappingsOverrides:
    """Tests for user override merging."""

    def test_override_modifies_keycode(self):
        """User override modifies a keycode mapping."""
        keycodes_config = Keycodes(overrides=[Keycode(keycode="KC_A", target="Custom A")])
        mappings = load_keycode_mappings(keycodes_config)
        keycodes = mappings.get("keycodes", {})

        assert keycodes.get("KC_A") == "Custom A"

    def test_override_adds_new_keycode(self):
        """User override can add a new keycode mapping."""
        keycodes_config = Keycodes(overrides=[Keycode(keycode="CUSTOM_KEY", target="Custom")])
        mappings = load_keycode_mappings(keycodes_config)
        keycodes = mappings.get("keycodes", {})

        assert keycodes.get("CUSTOM_KEY") == "Custom"

    def test_multiple_overrides(self):
        """Multiple overrides are all applied."""
        keycodes_config = Keycodes(
            overrides=[
                Keycode(keycode="KC_A", target="Alpha"),
                Keycode(keycode="KC_B", target="Bravo"),
            ]
        )
        mappings = load_keycode_mappings(keycodes_config)
        keycodes = mappings.get("keycodes", {})

        assert keycodes.get("KC_A") == "Alpha"
        assert keycodes.get("KC_B") == "Bravo"

    def test_pre_process_modifies_preprocessing(self):
        """User pre_process modifies the preprocessing mappings."""
        keycodes_config = Keycodes(pre_process=[Keycode(keycode="OLD_CODE", target="NEW_CODE")])
        mappings = load_keycode_mappings(keycodes_config)
        preprocessing = mappings.get("pre_processing", {})

        assert preprocessing.get("OLD_CODE") == "NEW_CODE"

    def test_combined_pre_process_and_overrides(self):
        """Both pre_process and overrides are applied."""
        keycodes_config = Keycodes(
            pre_process=[Keycode(keycode="PRE", target="POST")],
            overrides=[Keycode(keycode="KC_X", target="X-Ray")],
        )
        mappings = load_keycode_mappings(keycodes_config)

        preprocessing = mappings.get("pre_processing", {})
        keycodes = mappings.get("keycodes", {})

        assert preprocessing.get("PRE") == "POST"
        assert keycodes.get("KC_X") == "X-Ray"


class TestLoadKeycodeMappingsIntegration:
    """Integration tests for load_keycode_mappings."""

    def test_standard_keyboard_letters(self):
        """Standard keyboard letters have single-character labels."""
        keycodes_config = Keycodes()
        mappings = load_keycode_mappings(keycodes_config)
        keycodes = mappings.get("keycodes", {})

        # Most letter keycodes should map to single letters
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            key = f"KC_{letter}"
            if key in keycodes:
                # Should be a short label
                assert len(keycodes[key]) <= 5, f"Long label for {key}: {keycodes[key]}"

    def test_modifier_keys_present(self):
        """Modifier keys are present in mappings."""
        keycodes_config = Keycodes()
        mappings = load_keycode_mappings(keycodes_config)
        keycodes = mappings.get("keycodes", {})

        # Common modifier keycodes
        modifiers = ["KC_LSFT", "KC_RSFT", "KC_LCTL", "KC_RCTL", "KC_LALT", "KC_RALT"]
        for mod in modifiers:
            assert mod in keycodes, f"Missing modifier: {mod}"

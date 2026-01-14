"""Test suite for keycode mapping loader."""

from skim.application.keycode_loader import KeycodeMappingLoader


class TestKeycodeMappingLoader:
    def test_load_bundled_mappings(self):
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        assert mappings is not None
        assert "keycodes" in mappings
        assert "reversed_alias" in mappings
        assert "modifiers" in mappings
        assert "layer_symbols" in mappings

    def test_keycodes_contain_expected_entries(self):
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        keycodes = mappings["keycodes"]
        assert "KC_A" in keycodes
        assert keycodes["KC_A"] == "A"
        assert "KC_ENTER" in keycodes

    def test_modifiers_contain_expected_entries(self):
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        modifiers = mappings["modifiers"]
        assert "S" in modifiers
        assert "C" in modifiers
        assert "A" in modifiers
        assert "G" in modifiers

    def test_layer_symbols_contain_expected_entries(self):
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        layer_symbols = mappings["layer_symbols"]
        assert "MO" in layer_symbols
        assert "TG" in layer_symbols
        assert "DF" in layer_symbols

    def test_reversed_alias_entries(self):
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        reversed_alias = mappings["reversed_alias"]
        assert isinstance(reversed_alias, dict)

    def test_load_from_custom_file(self, tmp_path):
        custom_yaml = tmp_path / "custom-mappings.yaml"
        custom_yaml.write_text("""
keycodes:
  CUSTOM_KEY: "CUSTOM"
reversed_alias: {}
modifiers: {}
layer_symbols: {}
""")

        loader = KeycodeMappingLoader()
        mappings = loader.load_from_file(custom_yaml)

        assert "keycodes" in mappings
        assert mappings["keycodes"]["CUSTOM_KEY"] == "CUSTOM"

    def test_merge_custom_with_bundled(self, tmp_path):
        custom_yaml = tmp_path / "custom.yaml"
        custom_yaml.write_text("""
keycodes:
  KC_A: "CustomA"
  CUSTOM_KEY: "CUSTOM"
reversed_alias: {}
modifiers: {}
layer_symbols: {}
""")

        loader = KeycodeMappingLoader()
        bundled = loader.load_bundled()
        custom = loader.load_from_file(custom_yaml)
        merged = loader.merge_mappings(bundled, custom)

        assert merged["keycodes"]["KC_A"] == "CustomA"
        assert merged["keycodes"]["CUSTOM_KEY"] == "CUSTOM"
        assert "KC_B" in merged["keycodes"]

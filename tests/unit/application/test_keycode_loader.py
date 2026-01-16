"""Test suite for keycode mapping loader."""

from skim.application.keycode_loader import KeycodeMappingLoader


class TestKeycodeMappingLoader:
    def test_load_bundled_mappings(self):
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        assert mappings is not None
        assert "keycodes" in mappings
        assert "reversed_alias" in mappings
        assert "macro_functions" in mappings
        assert "modifier_union" in mappings

    def test_keycodes_contain_expected_entries(self):
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        keycodes = mappings["keycodes"]
        assert "KC_A" in keycodes
        assert keycodes["KC_A"] == "A"
        assert "KC_ENTER" in keycodes

    def test_macro_functions_contain_expected_entries(self):
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        macro_functions = mappings["macro_functions"]
        assert "S" in macro_functions
        assert "C" in macro_functions
        assert "MO" in macro_functions
        assert "LT" in macro_functions
        assert "LSFT_T" in macro_functions

    def test_modifier_union_contain_expected_entries(self):
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        modifier_union = mappings["modifier_union"]
        assert "MOD_LCTL" in modifier_union
        assert "MOD_LSFT" in modifier_union
        assert "MOD_LALT" in modifier_union
        assert "MOD_LGUI" in modifier_union

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
macro_functions: {}
modifier_union: {}
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
""")

        loader = KeycodeMappingLoader()
        bundled = loader.load_bundled()
        custom = loader.load_from_file(custom_yaml)
        merged = loader.merge_mappings(bundled, custom)

        assert merged["keycodes"]["KC_A"] == "CustomA"
        assert merged["keycodes"]["CUSTOM_KEY"] == "CUSTOM"
        assert "KC_B" in merged["keycodes"]

    def test_merge_does_not_override_macro_functions(self, tmp_path):
        custom_yaml = tmp_path / "custom.yaml"
        custom_yaml.write_text("""
keycodes:
  KC_A: "CustomA"
macro_functions:
  CUSTOM_FUNC: "custom template"
""")

        loader = KeycodeMappingLoader()
        bundled = loader.load_bundled()
        custom = loader.load_from_file(custom_yaml)
        merged = loader.merge_mappings(bundled, custom)

        assert "MO" in merged["macro_functions"]
        assert "CUSTOM_FUNC" not in merged["macro_functions"]

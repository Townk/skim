# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.data.trie module.

Tests cover Trie initialization and get_matching_prefix functionality
for efficient prefix matching of QMK macro function names.
"""

import pytest

from skim.data.trie import Trie


class TestTrieInitialization:
    """Tests for Trie initialization."""

    def test_init_with_list(self):
        """Trie can be initialized with a list of words."""
        trie = Trie(["LT", "MO", "TG"])
        assert trie.get_matching_prefix("LT0") == "LT"

    def test_init_with_tuple(self):
        """Trie can be initialized with a tuple of words."""
        trie = Trie(("LT", "MO", "TG"))
        assert trie.get_matching_prefix("MO(1)") == "MO"

    def test_init_with_set(self):
        """Trie can be initialized with a set of words."""
        trie = Trie({"LT", "MO", "TG"})
        assert trie.get_matching_prefix("TG(2)") == "TG"

    def test_init_with_generator(self):
        """Trie can be initialized with a generator."""
        trie = Trie(w.upper() for w in ["lt", "mo", "tg"])
        assert trie.get_matching_prefix("MO(1)") == "MO"

    def test_init_with_empty_iterable(self):
        """Trie can be initialized with empty iterable."""
        trie = Trie([])
        assert trie.get_matching_prefix("anything") is None

    def test_init_with_single_word(self):
        """Trie can be initialized with a single word."""
        trie = Trie(["PREFIX"])
        assert trie.get_matching_prefix("PREFIX_SUFFIX") == "PREFIX"


class TestTrieGetMatchingPrefix:
    """Tests for Trie.get_matching_prefix method."""

    def test_exact_match(self):
        """Exact match returns the word."""
        trie = Trie(["LT", "MO", "TG"])
        assert trie.get_matching_prefix("LT") == "LT"

    def test_prefix_match(self):
        """Prefix match returns the indexed word."""
        trie = Trie(["LT", "MO", "TG"])
        assert trie.get_matching_prefix("LT(1, KC_A)") == "LT"

    def test_no_match_returns_none(self):
        """No match returns None."""
        trie = Trie(["LT", "MO", "TG"])
        assert trie.get_matching_prefix("KC_A") is None

    def test_partial_prefix_no_match(self):
        """Partial prefix that isn't a complete word returns None."""
        trie = Trie(["LT", "MO", "TG"])
        assert trie.get_matching_prefix("L") is None

    def test_empty_string_no_match(self):
        """Empty string returns None."""
        trie = Trie(["LT", "MO", "TG"])
        assert trie.get_matching_prefix("") is None

    def test_longer_word_preferred_when_both_match(self):
        """When multiple words could match, returns shortest matching prefix."""
        trie = Trie(["O", "OSL"])
        assert trie.get_matching_prefix("OSL(1)") == "O"

    def test_case_sensitive(self):
        """Matching is case-sensitive."""
        trie = Trie(["LT", "MO", "TG"])
        assert trie.get_matching_prefix("lt(1)") is None
        assert trie.get_matching_prefix("Lt(1)") is None

    def test_special_characters(self):
        """Words with special characters work correctly."""
        trie = Trie(["KC_", "S("])
        assert trie.get_matching_prefix("KC_A") == "KC_"
        assert trie.get_matching_prefix("S(KC_A)") == "S("

    def test_numeric_prefix(self):
        """Numeric prefixes work correctly."""
        trie = Trie(["123", "456"])
        assert trie.get_matching_prefix("123ABC") == "123"
        assert trie.get_matching_prefix("789") is None

    def test_unicode_characters(self):
        """Unicode characters work correctly."""
        trie = Trie(["cafe", "caf\u00e9"])
        assert trie.get_matching_prefix("cafe_latte") == "cafe"
        assert trie.get_matching_prefix("caf\u00e9_au_lait") == "caf\u00e9"

    def test_single_character_words(self):
        """Single character words work correctly."""
        trie = Trie(["A", "B", "C"])
        assert trie.get_matching_prefix("ABC") == "A"
        assert trie.get_matching_prefix("BCD") == "B"
        assert trie.get_matching_prefix("XYZ") is None


class TestTrieQMKMacros:
    """Tests for Trie with real QMK macro function names."""

    @pytest.fixture
    def qmk_trie(self):
        """Create a trie with common QMK macro prefixes."""
        return Trie(
            [
                "LT",
                "MO",
                "TG",
                "OSL",
                "OSM",
                "MT",
                "LM",
                "TT",
                "DF",
                "TO",
                "S",
                "C",
                "A",
                "G",
                "LCTL",
                "LSFT",
                "LALT",
                "LGUI",
            ]
        )

    def test_layer_tap(self, qmk_trie):
        """LT (Layer-Tap) is recognized."""
        assert qmk_trie.get_matching_prefix("LT(1, KC_A)") == "LT"

    def test_momentary_layer(self, qmk_trie):
        """MO (Momentary layer) is recognized."""
        assert qmk_trie.get_matching_prefix("MO(2)") == "MO"

    def test_toggle_layer(self, qmk_trie):
        """TG (Toggle layer) is recognized."""
        assert qmk_trie.get_matching_prefix("TG(3)") == "TG"

    def test_one_shot_layer(self, qmk_trie):
        """OSL (One-shot layer) is recognized."""
        assert qmk_trie.get_matching_prefix("OSL(1)") == "OSL"

    def test_one_shot_modifier(self, qmk_trie):
        """OSM (One-shot modifier) is recognized."""
        assert qmk_trie.get_matching_prefix("OSM(MOD_LCTL)") == "OSM"

    def test_mod_tap(self, qmk_trie):
        """MT (Mod-Tap) is recognized."""
        assert qmk_trie.get_matching_prefix("MT(MOD_LCTL, KC_A)") == "MT"

    def test_regular_keycode_not_matched(self, qmk_trie):
        """Regular keycodes like KC_A are not matched."""
        assert qmk_trie.get_matching_prefix("KC_A") is None

    def test_ambiguous_prefix_returns_first_match(self, qmk_trie):
        """When 'L' could match 'LT', 'LM', or 'LCTL', shortest wins."""
        assert qmk_trie.get_matching_prefix("LCTL_T(KC_A)") == "LCTL"


class TestTrieEdgeCases:
    """Edge case tests for Trie."""

    def test_overlapping_prefixes(self):
        """Overlapping prefixes are handled correctly."""
        trie = Trie(["A", "AB", "ABC"])
        assert trie.get_matching_prefix("ABCD") == "A"

    def test_no_overlapping_prefixes(self):
        """Non-overlapping prefixes work independently."""
        trie = Trie(["ABC", "DEF", "GHI"])
        assert trie.get_matching_prefix("ABCDEF") == "ABC"
        assert trie.get_matching_prefix("DEFGHI") == "DEF"
        assert trie.get_matching_prefix("GHIJKL") == "GHI"

    def test_duplicate_words_in_init(self):
        """Duplicate words in initialization don't cause issues."""
        trie = Trie(["LT", "LT", "MO", "MO", "LT"])
        assert trie.get_matching_prefix("LT0") == "LT"
        assert trie.get_matching_prefix("MO1") == "MO"

    def test_very_long_word(self):
        """Very long words work correctly."""
        long_word = "A" * 1000
        trie = Trie([long_word])
        assert trie.get_matching_prefix(long_word + "B") == long_word
        assert trie.get_matching_prefix("A" * 999) is None

    def test_very_long_search_string(self):
        """Very long search strings work correctly."""
        trie = Trie(["AB"])
        long_search = "AB" + "C" * 10000
        assert trie.get_matching_prefix(long_search) == "AB"

    def test_whitespace_in_words(self):
        """Whitespace in words is preserved."""
        trie = Trie(["hello world", "foo bar"])
        assert trie.get_matching_prefix("hello world!") == "hello world"
        assert trie.get_matching_prefix("helloworld") is None

    def test_empty_word_in_init(self):
        """Empty string as a word matches empty search."""
        trie = Trie(["", "AB"])
        assert trie.get_matching_prefix("") == ""
        assert trie.get_matching_prefix("anything") == ""

    def test_root_structure(self):
        """Verify trie root structure is a dict."""
        trie = Trie(["AB", "AC"])
        assert isinstance(trie.root, dict)
        assert "A" in trie.root


class TestTrieSlots:
    """Tests for Trie __slots__ optimization."""

    def test_has_slots(self):
        """Trie uses __slots__ for memory efficiency."""
        assert hasattr(Trie, "__slots__")
        assert "root" in Trie.__slots__

    def test_cannot_add_arbitrary_attributes(self):
        """Cannot add arbitrary attributes due to __slots__."""
        trie = Trie(["LT"])
        with pytest.raises(AttributeError):
            trie.custom_attribute = "value"  # type: ignore[attr-defined]

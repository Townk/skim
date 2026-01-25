"""Trie (prefix tree) data structure for efficient prefix matching.

This module provides a Trie implementation optimized for checking whether
a string starts with any of a predefined set of prefixes. It is used
internally by the keycode label adapter to efficiently match QMK macro
function names like "LT", "MO", "TG", etc.

Example:
    >>> from skim.data.trie import Trie
    >>> trie = Trie(["LT", "MO", "TG", "OSL"])
    >>> trie.get_matching_prefix("LT0")
    'LT'
    >>> trie.get_matching_prefix("MO(1)")
    'MO'
    >>> trie.get_matching_prefix("KC_A") is None
    True
"""

from collections.abc import Iterable


class Trie:
    """A trie (prefix tree) for efficient prefix matching.

    This data structure allows O(m) lookup time to check if a string starts
    with any word from a predefined set, where m is the length of the search
    string (or more precisely, the length of the matching prefix).

    The trie is built once during initialization and then supports fast
    prefix queries. It is particularly useful for parsing QMK macro functions
    where we need to identify function names at the start of strings like
    "LT(1, KC_A)" or "MO(2)".

    Attributes:
        root: The root node of the trie, represented as a nested dictionary.
            Each key is a character leading to a child node (another dict),
            except for None which marks the end of a word and stores the
            complete word string.

    Example:
        >>> trie = Trie(["cat", "car", "card"])
        >>> trie.get_matching_prefix("catalog")
        'cat'
        >>> trie.get_matching_prefix("car")
        'car'
        >>> trie.get_matching_prefix("dog") is None
        True
    """

    __slots__ = ["root"]

    def __init__(self, words: Iterable[str]) -> None:
        """Initialize the trie with a collection of words.

        Builds the trie structure by inserting all provided words. Each word
        creates a path through the trie, with the complete word stored at
        the terminal node.

        Args:
            words: An iterable of strings to index in the trie. Can be a list,
                tuple, set, generator, or any other iterable of strings.

        Example:
            >>> trie = Trie(["LT", "MO", "TG"])
            >>> trie.get_matching_prefix("LT0")
            'LT'

            >>> # Can also use generators
            >>> trie = Trie(w.upper() for w in ["lt", "mo", "tg"])
            >>> trie.get_matching_prefix("MO(1)")
            'MO'
        """
        self.root: dict = {}
        for word in words:
            node = self.root
            for char in word:
                node = node.setdefault(char, {})
            node[None] = word

    def get_matching_prefix(self, search_string: str) -> str | None:
        """Find the longest indexed word that is a prefix of the search string.

        Traverses the trie following characters from the search string. If a
        complete indexed word is found (marked by a None key), that word is
        returned. The search continues to find the longest possible match.

        Args:
            search_string: The string to check for a matching prefix.

        Returns:
            The matching prefix word if found, or None if the search string
            doesn't start with any indexed word.

        Example:
            >>> trie = Trie(["LT", "LM", "OSL"])
            >>> trie.get_matching_prefix("LT(1, KC_A)")
            'LT'
            >>> trie.get_matching_prefix("OSL(2)")
            'OSL'
            >>> trie.get_matching_prefix("KC_SPACE") is None
            True
            >>> trie.get_matching_prefix("LT")
            'LT'
        """
        node = self.root
        for char in search_string:
            if None in node:
                return node[None]  # type: ignore[return-value]
            if char not in node:
                return None
            node = node[char]  # type: ignore[assignment]

        return node.get(None)  # type: ignore[return-value]

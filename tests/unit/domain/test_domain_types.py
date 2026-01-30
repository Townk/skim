# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.domain.domain_types module.

Tests for the .opposite property implementations which are not exercised
by other tests in the suite.
"""

from skim.domain.domain_types import Alignment, KeyboardSide, KeyDirection


class TestAlignmentOpposite:
    """Tests for Alignment.opposite property."""

    def test_opposite_start_returns_end(self):
        assert Alignment.START.opposite == Alignment.END

    def test_opposite_end_returns_start(self):
        assert Alignment.END.opposite == Alignment.START

    def test_opposite_center_returns_center(self):
        assert Alignment.CENTER.opposite == Alignment.CENTER


class TestKeyboardSideOpposite:
    """Tests for KeyboardSide.opposite property."""

    def test_opposite_left_returns_right(self):
        assert KeyboardSide.LEFT.opposite == KeyboardSide.RIGHT

    def test_opposite_right_returns_left(self):
        assert KeyboardSide.RIGHT.opposite == KeyboardSide.LEFT


class TestKeyDirectionOpposite:
    """Tests for KeyDirection.opposite property."""

    def test_opposite_north_returns_south(self):
        assert KeyDirection.NORTH.opposite == KeyDirection.SOUTH

    def test_opposite_south_returns_north(self):
        assert KeyDirection.SOUTH.opposite == KeyDirection.NORTH

    def test_opposite_east_returns_west(self):
        assert KeyDirection.EAST.opposite == KeyDirection.WEST

    def test_opposite_west_returns_east(self):
        assert KeyDirection.WEST.opposite == KeyDirection.EAST

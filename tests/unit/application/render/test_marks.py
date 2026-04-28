"""Unit tests for skim.application.render.marks."""

import drawsvg as draw
import pytest

from skim.application.render.marks import (
    SATELLITE_FOLD_CORNER,
    MacroTapDanceCorner,
)


class TestSatelliteFoldCorner:
    def test_clockwise_rotation(self):
        # north (edgeSide bottom) → tr; east (left) → br;
        # south (top) → bl; west (right) → tl
        assert SATELLITE_FOLD_CORNER["bottom"] == "tr"
        assert SATELLITE_FOLD_CORNER["left"] == "br"
        assert SATELLITE_FOLD_CORNER["top"] == "bl"
        assert SATELLITE_FOLD_CORNER["right"] == "tl"


class TestMacroTapDanceCorner:
    def test_creates_drawsvg_group(self):
        m = MacroTapDanceCorner(
            x=0, y=0, w=54, h=54, r=4,
            corner="tr", fill="#89511C",
        )
        assert isinstance(m, draw.Group)

    def test_fold_leg_is_22_for_satellite_size(self):
        m = MacroTapDanceCorner(
            x=0, y=0, w=54, h=54, r=4,
            corner="tr", fill="#89511C",
        )
        assert m.fold_leg == 22

    def test_fold_leg_capped_at_26_for_large_keys(self):
        m = MacroTapDanceCorner(
            x=0, y=0, w=200, h=200, r=4,
            corner="tr", fill="#89511C",
        )
        assert m.fold_leg == 26

    def test_fold_leg_proportional_for_small_keys(self):
        # min(w,h)*0.42 = 30*0.42 = 12.6
        m = MacroTapDanceCorner(
            x=0, y=0, w=30, h=30, r=4,
            corner="tr", fill="#89511C",
        )
        assert m.fold_leg == pytest.approx(12.6, rel=0.01)

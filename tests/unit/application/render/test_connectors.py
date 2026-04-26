"""Unit tests for skim.application.render.connectors module."""

from skim.application.render.connectors import (
    ConnectorStep,
    Direction,
)


class TestDirection:
    def test_has_four_cardinal_directions(self):
        assert {Direction.UP, Direction.RIGHT, Direction.DOWN, Direction.LEFT} == set(Direction)


class TestConnectorStep:
    def test_default_col_x_is_zero(self):
        # path is built lazily in Phase 2; col_X starts at 0 and is set during column allocation
        step = ConnectorStep(
            key=None,
            direction=Direction.UP,
            target_point=(0.0, 0.0),
            target_layer=0,
        )
        assert step.col_X == 0

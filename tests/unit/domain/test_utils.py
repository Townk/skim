from skim.domain.utils import clip


class TestClip:
    def test_value_within_range_unchanged(self):
        assert clip(5, 0, 10) == 5

    def test_value_below_min_returns_min(self):
        assert clip(-5, 0, 10) == 0

    def test_value_above_max_returns_max(self):
        assert clip(15, 0, 10) == 10

    def test_value_equals_min(self):
        assert clip(0, 0, 10) == 0

    def test_value_equals_max(self):
        assert clip(10, 0, 10) == 10

    def test_float_values(self):
        assert clip(0.5, 0.0, 1.0) == 0.5
        assert clip(-0.5, 0.0, 1.0) == 0.0
        assert clip(1.5, 0.0, 1.0) == 1.0

    def test_negative_range(self):
        assert clip(-5, -10, -1) == -5
        assert clip(-15, -10, -1) == -10
        assert clip(0, -10, -1) == -1

    def test_single_value_range(self):
        assert clip(5, 3, 3) == 3
        assert clip(1, 3, 3) == 3

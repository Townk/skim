# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Comprehensive unit tests for skim.data.keyboard module.

Tests cover FingerCluster, ThumbCluster, SplitSide, SvalboardLayout, and
zip_clusters functionality including initialization modes, iteration, zipping,
and error handling.
"""

from dataclasses import FrozenInstanceError, dataclass

import pytest

from skim.data.keyboard import (
    _BUNDLE_CACHE,
    _UNSET,
    FingerCluster,
    SplitSide,
    SvalboardKeymap,
    SvalboardLayout,
    ThumbCluster,
    _ClusterBase,
    _Unset,
    zip_clusters,
    zip_layouts,
)


class TestUnsetSentinel:
    """Tests for the _Unset sentinel class."""

    def test_repr(self):
        """_Unset repr returns '<UNSET>'."""
        assert repr(_UNSET) == "<UNSET>"

    def test_singleton_identity(self):
        """_UNSET is a singleton instance."""
        assert _UNSET is _UNSET
        # Creating new instance is different object
        other = _Unset()
        assert other is not _UNSET
        # But has same repr
        assert repr(other) == "<UNSET>"


class TestFingerClusterInitialization:
    """Tests for FingerCluster initialization modes."""

    def test_init_with_all_explicit_kwargs(self):
        """FingerCluster can be initialized with all fields as kwargs."""
        cluster = FingerCluster(
            center_key="C",
            north_key="N",
            east_key="E",
            south_key="S",
            west_key="W",
            double_south_key="DS",
        )
        assert cluster.center_key == "C"
        assert cluster.north_key == "N"
        assert cluster.east_key == "E"
        assert cluster.south_key == "S"
        assert cluster.west_key == "W"
        assert cluster.double_south_key == "DS"

    def test_init_with_default_value(self):
        """FingerCluster can be initialized with a default value for all keys."""
        cluster = FingerCluster("default")
        assert cluster.center_key == "default"
        assert cluster.north_key == "default"
        assert cluster.east_key == "default"
        assert cluster.south_key == "default"
        assert cluster.west_key == "default"
        assert cluster.double_south_key == "default"

    def test_init_with_default_and_overrides(self):
        """FingerCluster accepts default with specific overrides."""
        cluster = FingerCluster("X", center_key="A", south_key="B")
        assert cluster.center_key == "A"
        assert cluster.north_key == "X"
        assert cluster.east_key == "X"
        assert cluster.south_key == "B"
        assert cluster.west_key == "X"
        assert cluster.double_south_key == "X"

    def test_init_with_none_as_default(self):
        """FingerCluster accepts None as a valid default value."""
        cluster = FingerCluster(None, center_key="A")
        assert cluster.center_key == "A"
        assert cluster.north_key is None
        assert cluster.east_key is None

    def test_init_with_none_as_override(self):
        """FingerCluster accepts None as an override value."""
        cluster = FingerCluster("default", center_key=None)
        assert cluster.center_key is None
        assert cluster.north_key == "default"

    def test_init_missing_required_field_raises_typeerror(self):
        """FingerCluster raises TypeError when required field is missing."""
        with pytest.raises(TypeError) as exc_info:
            FingerCluster(
                center_key="C",
                north_key="N",
                # missing: east_key, south_key, west_key, double_south_key
            )
        assert "missing required keyword argument" in str(exc_info.value)
        assert "east_key" in str(exc_info.value)

    def test_init_with_integer_values(self):
        """FingerCluster supports integer values (generic type)."""
        cluster = FingerCluster(0, center_key=1, north_key=2)
        assert cluster.center_key == 1
        assert cluster.north_key == 2
        assert cluster.east_key == 0

    def test_init_with_complex_objects(self):
        """FingerCluster supports complex object values."""

        class KeyData:
            def __init__(self, code: str, label: str):
                self.code = code
                self.label = label

        default_data = KeyData("KC_NO", "")
        center_data = KeyData("KC_A", "A")

        cluster = FingerCluster(default_data, center_key=center_data)
        assert cluster.center_key.code == "KC_A"
        assert cluster.north_key.code == "KC_NO"


class TestThumbClusterInitialization:
    """Tests for ThumbCluster initialization modes."""

    def test_init_with_all_explicit_kwargs(self):
        """ThumbCluster can be initialized with all fields as kwargs."""
        cluster = ThumbCluster(
            down_key="D",
            pad_key="P",
            up_key="U",
            nail_key="N",
            knuckle_key="K",
            double_down_key="DD",
        )
        assert cluster.down_key == "D"
        assert cluster.pad_key == "P"
        assert cluster.up_key == "U"
        assert cluster.nail_key == "N"
        assert cluster.knuckle_key == "K"
        assert cluster.double_down_key == "DD"

    def test_init_with_default_value(self):
        """ThumbCluster can be initialized with a default value for all keys."""
        cluster = ThumbCluster("default")
        assert cluster.down_key == "default"
        assert cluster.pad_key == "default"
        assert cluster.up_key == "default"
        assert cluster.nail_key == "default"
        assert cluster.knuckle_key == "default"
        assert cluster.double_down_key == "default"

    def test_init_with_default_and_overrides(self):
        """ThumbCluster accepts default with specific overrides."""
        cluster = ThumbCluster("X", down_key="Space", nail_key="Esc")
        assert cluster.down_key == "Space"
        assert cluster.pad_key == "X"
        assert cluster.up_key == "X"
        assert cluster.nail_key == "Esc"
        assert cluster.knuckle_key == "X"
        assert cluster.double_down_key == "X"

    def test_init_missing_required_field_raises_typeerror(self):
        """ThumbCluster raises TypeError when required field is missing."""
        with pytest.raises(TypeError) as exc_info:
            ThumbCluster(
                down_key="D",
                pad_key="P",
                # missing: up_key, nail_key, knuckle_key, double_down_key
            )
        assert "missing required keyword argument" in str(exc_info.value)
        assert "up_key" in str(exc_info.value)


class TestFingerClusterIteration:
    """Tests for FingerCluster iteration and unpacking."""

    def test_iteration_yields_all_values_in_order(self):
        """FingerCluster iteration yields values in field definition order."""
        cluster = FingerCluster(
            center_key="C",
            north_key="N",
            east_key="E",
            south_key="S",
            west_key="W",
            double_south_key="DS",
        )
        values = list(cluster)
        assert values == ["C", "N", "E", "S", "W", "DS"]

    def test_unpacking_to_variables(self):
        """FingerCluster can be unpacked into variables."""
        cluster = FingerCluster("X", center_key="A")
        center, north, east, south, west, dsouth = cluster
        assert center == "A"
        assert north == "X"
        assert east == "X"
        assert south == "X"
        assert west == "X"
        assert dsouth == "X"

    def test_iteration_count(self):
        """FingerCluster iteration yields exactly 6 values."""
        cluster = FingerCluster("")
        assert len(list(cluster)) == 6


class TestThumbClusterIteration:
    """Tests for ThumbCluster iteration and unpacking."""

    def test_iteration_yields_all_values_in_order(self):
        """ThumbCluster iteration yields values in field definition order."""
        cluster = ThumbCluster(
            down_key="D",
            pad_key="P",
            up_key="U",
            nail_key="N",
            knuckle_key="K",
            double_down_key="DD",
        )
        values = list(cluster)
        assert values == ["D", "P", "U", "N", "K", "DD"]

    def test_unpacking_to_variables(self):
        """ThumbCluster can be unpacked into variables."""
        cluster = ThumbCluster("X", down_key="Space")
        down, pad, up, nail, knuckle, ddown = cluster
        assert down == "Space"
        assert pad == "X"
        assert up == "X"
        assert nail == "X"
        assert knuckle == "X"
        assert ddown == "X"

    def test_iteration_count(self):
        """ThumbCluster iteration yields exactly 6 values."""
        cluster = ThumbCluster("")
        assert len(list(cluster)) == 6


class TestClusterRepr:
    """Tests for cluster __repr__ methods."""

    def test_finger_cluster_repr(self):
        """FingerCluster repr shows class name and all fields."""
        cluster = FingerCluster("X", center_key="A")
        repr_str = repr(cluster)
        assert repr_str.startswith("FingerCluster(")
        assert "center_key='A'" in repr_str
        assert "north_key='X'" in repr_str
        assert "east_key='X'" in repr_str
        assert "south_key='X'" in repr_str
        assert "west_key='X'" in repr_str
        assert "double_south_key='X'" in repr_str

    def test_thumb_cluster_repr(self):
        """ThumbCluster repr shows class name and all fields."""
        cluster = ThumbCluster("Y", down_key="Space")
        repr_str = repr(cluster)
        assert repr_str.startswith("ThumbCluster(")
        assert "down_key='Space'" in repr_str
        assert "pad_key='Y'" in repr_str

    def test_repr_with_none_value(self):
        """Cluster repr handles None values correctly."""
        cluster = FingerCluster(None)
        repr_str = repr(cluster)
        assert "center_key=None" in repr_str

    def test_repr_with_integer_value(self):
        """Cluster repr handles integer values correctly."""
        cluster = FingerCluster(42)
        repr_str = repr(cluster)
        assert "center_key=42" in repr_str


class TestFieldsCaching:
    """Tests for the _get_fields caching mechanism."""

    def test_fields_are_cached(self):
        """_get_fields caches results for each class."""
        # Clear cache first
        _ClusterBase._fields_cache.clear()

        # First call should populate cache
        fields1 = FingerCluster._get_fields()
        assert FingerCluster in _ClusterBase._fields_cache

        # Second call should return cached value
        fields2 = FingerCluster._get_fields()
        assert fields1 is fields2

    def test_different_classes_have_separate_cache_entries(self):
        """Each cluster subclass has its own cache entry."""
        _ClusterBase._fields_cache.clear()

        finger_fields = FingerCluster._get_fields()
        thumb_fields = ThumbCluster._get_fields()

        assert FingerCluster in _ClusterBase._fields_cache
        assert ThumbCluster in _ClusterBase._fields_cache
        assert finger_fields is not thumb_fields

    def test_cached_fields_match_actual_fields(self):
        """Cached fields have correct names for each cluster type."""
        finger_names = {f.name for f in FingerCluster._get_fields()}
        thumb_names = {f.name for f in ThumbCluster._get_fields()}

        assert finger_names == {
            "center_key",
            "north_key",
            "east_key",
            "south_key",
            "west_key",
            "double_south_key",
        }
        assert thumb_names == {
            "down_key",
            "pad_key",
            "up_key",
            "nail_key",
            "knuckle_key",
            "double_down_key",
        }


class TestClusterFromSequence:
    """Tests for the from_sequence class method on clusters."""

    def test_finger_cluster_from_list(self):
        """FingerCluster.from_sequence creates cluster from a list."""
        values = ["C", "N", "E", "S", "W", "DS"]
        cluster = FingerCluster.from_sequence(values)

        assert cluster.center_key == "C"
        assert cluster.north_key == "N"
        assert cluster.east_key == "E"
        assert cluster.south_key == "S"
        assert cluster.west_key == "W"
        assert cluster.double_south_key == "DS"

    def test_finger_cluster_from_tuple(self):
        """FingerCluster.from_sequence creates cluster from a tuple."""
        values = ("A", "B", "C", "D", "E", "F")
        cluster = FingerCluster.from_sequence(values)

        assert cluster.center_key == "A"
        assert cluster.double_south_key == "F"

    def test_thumb_cluster_from_list(self):
        """ThumbCluster.from_sequence creates cluster from a list."""
        values = ["D", "P", "U", "N", "K", "DD"]
        cluster = ThumbCluster.from_sequence(values)

        assert cluster.down_key == "D"
        assert cluster.pad_key == "P"
        assert cluster.up_key == "U"
        assert cluster.nail_key == "N"
        assert cluster.knuckle_key == "K"
        assert cluster.double_down_key == "DD"

    def test_thumb_cluster_from_tuple(self):
        """ThumbCluster.from_sequence creates cluster from a tuple."""
        values = ("Space", "Enter", "Tab", "Esc", "Ctrl", "")
        cluster = ThumbCluster.from_sequence(values)

        assert cluster.down_key == "Space"
        assert cluster.double_down_key == ""

    def test_from_sequence_preserves_order(self):
        """from_sequence maps values to fields in iteration order."""
        values = list(range(6))
        cluster = FingerCluster.from_sequence(values)

        # Verify iteration returns same order
        assert list(cluster) == values

    def test_from_sequence_with_integers(self):
        """from_sequence works with integer values."""
        values = [0, 1, 2, 3, 4, 5]
        cluster = FingerCluster.from_sequence(values)

        assert cluster.center_key == 0
        assert cluster.double_south_key == 5

    def test_from_sequence_with_none_values(self):
        """from_sequence works with None values."""
        values = [None, None, None, None, None, None]
        cluster = ThumbCluster.from_sequence(values)

        assert cluster.down_key is None
        assert cluster.nail_key is None

    def test_from_sequence_with_mixed_types(self):
        """from_sequence works with mixed value types."""
        values = ["str", 42, None, 3.14, True, [1, 2]]
        cluster = FingerCluster.from_sequence(values)

        assert cluster.center_key == "str"
        assert cluster.north_key == 42
        assert cluster.east_key is None
        assert cluster.south_key == 3.14
        assert cluster.west_key is True
        assert cluster.double_south_key == [1, 2]

    def test_from_sequence_too_few_values_raises_valueerror(self):
        """from_sequence raises ValueError for fewer than 6 values."""
        values = ["A", "B", "C", "D", "E"]  # Only 5
        with pytest.raises(ValueError) as exc_info:
            FingerCluster.from_sequence(values)
        assert "Expected exactly 6 values" in str(exc_info.value)
        assert "got 5" in str(exc_info.value)

    def test_from_sequence_too_many_values_raises_valueerror(self):
        """from_sequence raises ValueError for more than 6 values."""
        values = ["A", "B", "C", "D", "E", "F", "G"]  # 7 values
        with pytest.raises(ValueError) as exc_info:
            ThumbCluster.from_sequence(values)
        assert "Expected exactly 6 values" in str(exc_info.value)
        assert "got 7" in str(exc_info.value)

    def test_from_sequence_empty_raises_valueerror(self):
        """from_sequence raises ValueError for empty sequence."""
        with pytest.raises(ValueError) as exc_info:
            FingerCluster.from_sequence([])
        assert "Expected exactly 6 values" in str(exc_info.value)
        assert "got 0" in str(exc_info.value)

    def test_from_sequence_result_is_frozen(self):
        """Cluster created by from_sequence is immutable."""
        values = ["A", "B", "C", "D", "E", "F"]
        cluster = FingerCluster.from_sequence(values)

        with pytest.raises(FrozenInstanceError):
            cluster.center_key = "X"

    def test_from_sequence_matches_manual_creation(self):
        """from_sequence creates equivalent cluster to manual kwargs."""
        values = ["C", "N", "E", "S", "W", "DS"]
        from_seq = FingerCluster.from_sequence(values)
        manual = FingerCluster(
            center_key="C",
            north_key="N",
            east_key="E",
            south_key="S",
            west_key="W",
            double_south_key="DS",
        )

        # Compare all fields
        assert list(from_seq) == list(manual)


class TestFromZipped:
    """Tests for the from_zipped class method."""

    def test_basic_zip_two_finger_clusters(self):
        """from_zipped combines two FingerClusters into bundled values."""
        codes = FingerCluster("KC_NO", center_key="KC_A")
        labels = FingerCluster("", center_key="A")

        combined = FingerCluster.from_zipped(codes=codes, labels=labels)

        assert combined.center_key.codes == "KC_A"
        assert combined.center_key.labels == "A"
        assert combined.north_key.codes == "KC_NO"
        assert combined.north_key.labels == ""

    def test_basic_zip_two_thumb_clusters(self):
        """from_zipped combines two ThumbClusters into bundled values."""
        codes = ThumbCluster("KC_NO", down_key="KC_SPC")
        labels = ThumbCluster("", down_key="Space")

        combined = ThumbCluster.from_zipped(codes=codes, labels=labels)

        assert combined.down_key.codes == "KC_SPC"
        assert combined.down_key.labels == "Space"

    def test_zip_three_clusters(self):
        """from_zipped can combine multiple clusters."""
        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")
        colors = FingerCluster("#888")

        combined = FingerCluster.from_zipped(code=codes, label=labels, color=colors)

        assert combined.center_key.code == "KC_NO"
        assert combined.center_key.label == ""
        assert combined.center_key.color == "#888"

    def test_custom_bundle_name(self):
        """from_zipped accepts custom bundle class name."""
        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        combined = FingerCluster.from_zipped(bundle="KeyData", codes=codes, labels=labels)

        # Bundle class should have the custom name
        bundle = combined.center_key
        assert bundle.__class__.__name__ == "KeyData"

    def test_zip_empty_clusters_raises_valueerror(self):
        """from_zipped raises ValueError when no clusters provided."""
        with pytest.raises(ValueError) as exc_info:
            FingerCluster.from_zipped()
        assert "At least one cluster is required" in str(exc_info.value)

    def test_zip_mismatched_fields_raises_typeerror(self):
        """from_zipped raises TypeError when cluster fields don't match."""
        finger = FingerCluster("")
        thumb = ThumbCluster("")

        with pytest.raises(TypeError) as exc_info:
            FingerCluster.from_zipped(finger=finger, thumb=thumb)
        assert "has fields" in str(exc_info.value)
        assert "expected" in str(exc_info.value)

    def test_zipped_bundles_are_frozen(self):
        """Bundle objects created by from_zipped are immutable."""
        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        combined = FingerCluster.from_zipped(codes=codes, labels=labels)

        with pytest.raises(FrozenInstanceError):
            combined.center_key.codes = "KC_B"

    def test_bundle_cache_is_reused(self):
        """Bundle classes are cached and reused for same keys."""
        # Clear the cache first
        _BUNDLE_CACHE.clear()

        codes1 = FingerCluster("KC_NO")
        labels1 = FingerCluster("")
        combined1 = FingerCluster.from_zipped(codes=codes1, labels=labels1)

        codes2 = FingerCluster("KC_A")
        labels2 = FingerCluster("A")
        combined2 = FingerCluster.from_zipped(codes=codes2, labels=labels2)

        # Same bundle class should be reused
        assert type(combined1.center_key) is type(combined2.center_key)

    def test_bundle_cache_differs_for_different_keys(self):
        """Different cluster key names create different bundle classes."""
        _BUNDLE_CACHE.clear()

        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")
        combined1 = FingerCluster.from_zipped(codes=codes, labels=labels)

        keycodes = FingerCluster("KC_NO")
        names = FingerCluster("")
        combined2 = FingerCluster.from_zipped(keycodes=keycodes, names=names)

        # Different bundle classes for different attribute names
        assert type(combined1.center_key) is not type(combined2.center_key)

    def test_bundle_cache_differs_for_different_bundle_names(self):
        """Different bundle_name values create different bundle classes."""
        _BUNDLE_CACHE.clear()

        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        combined1 = FingerCluster.from_zipped(bundle="BundleA", codes=codes, labels=labels)
        combined2 = FingerCluster.from_zipped(bundle="BundleB", codes=codes, labels=labels)

        assert combined1.center_key.__class__.__name__ == "BundleA"
        assert combined2.center_key.__class__.__name__ == "BundleB"
        assert type(combined1.center_key) is not type(combined2.center_key)

    def test_custom_dataclass_type_as_bundle(self):
        """from_zipped accepts a custom dataclass type as the bundle."""

        @dataclass(frozen=True)
        class KeyData:
            codes: str
            labels: str

        codes = FingerCluster("KC_NO", center_key="KC_A")
        labels = FingerCluster("", center_key="A")

        combined = FingerCluster.from_zipped(bundle=KeyData, codes=codes, labels=labels)

        assert isinstance(combined.center_key, KeyData)
        assert combined.center_key.codes == "KC_A"
        assert combined.center_key.labels == "A"
        assert combined.north_key.codes == "KC_NO"
        assert combined.north_key.labels == ""

    def test_custom_dataclass_type_preserves_class_identity(self):
        """Custom dataclass type is used directly, not cached or recreated."""

        @dataclass(frozen=True)
        class MyBundle:
            codes: str
            labels: str

        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        combined = FingerCluster.from_zipped(bundle=MyBundle, codes=codes, labels=labels)

        assert type(combined.center_key) is MyBundle

    def test_custom_dataclass_missing_attribute_raises_typeerror(self):
        """from_zipped raises TypeError when custom class is missing attributes."""

        @dataclass(frozen=True)
        class IncompleteBundle:
            codes: str
            # Missing 'labels' attribute

        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        with pytest.raises(TypeError) as exc_info:
            FingerCluster.from_zipped(bundle=IncompleteBundle, codes=codes, labels=labels)
        assert "IncompleteBundle" in str(exc_info.value)
        assert "missing required attributes" in str(exc_info.value)
        assert "labels" in str(exc_info.value)

    def test_custom_dataclass_with_extra_attributes(self):
        """Custom dataclass with extra attributes is accepted."""

        @dataclass(frozen=True)
        class ExtendedBundle:
            codes: str
            labels: str
            extra_field: str = "default"

        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        # Should work - extra attributes are fine
        combined = FingerCluster.from_zipped(bundle=ExtendedBundle, codes=codes, labels=labels)

        assert isinstance(combined.center_key, ExtendedBundle)
        assert combined.center_key.codes == "KC_NO"
        assert combined.center_key.labels == ""

    def test_regular_class_as_bundle(self):
        """from_zipped accepts a regular (non-dataclass) class as the bundle."""

        class RegularBundle:
            def __init__(self, codes: str, labels: str):
                self.codes = codes
                self.labels = labels

        codes = FingerCluster("KC_NO", center_key="KC_A")
        labels = FingerCluster("", center_key="A")

        combined = FingerCluster.from_zipped(bundle=RegularBundle, codes=codes, labels=labels)

        assert isinstance(combined.center_key, RegularBundle)
        assert combined.center_key.codes == "KC_A"
        assert combined.center_key.labels == "A"

    def test_regular_class_missing_attribute_raises_typeerror(self):
        """from_zipped raises TypeError when regular class is missing init params."""

        class PartialBundle:
            def __init__(self, codes: str):
                self.codes = codes

        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        with pytest.raises(TypeError) as exc_info:
            FingerCluster.from_zipped(bundle=PartialBundle, codes=codes, labels=labels)
        assert "PartialBundle" in str(exc_info.value)
        assert "missing required attributes" in str(exc_info.value)
        assert "labels" in str(exc_info.value)


class TestClusterMap:
    """Tests for the map method on clusters."""

    def test_finger_cluster_map_basic(self):
        """FingerCluster.map transforms all values."""
        cluster = FingerCluster("a", center_key="b", south_key="c")
        result = cluster.map(str.upper)

        assert result.center_key == "B"
        assert result.north_key == "A"
        assert result.south_key == "C"
        assert result.east_key == "A"

    def test_thumb_cluster_map_basic(self):
        """ThumbCluster.map transforms all values."""
        cluster = ThumbCluster("x", down_key="y", nail_key="z")
        result = cluster.map(str.upper)

        assert result.down_key == "Y"
        assert result.pad_key == "X"
        assert result.nail_key == "Z"

    def test_map_returns_same_cluster_type(self):
        """map returns the same cluster type as the source."""
        finger = FingerCluster("a")
        thumb = ThumbCluster("b")

        finger_result = finger.map(str.upper)
        thumb_result = thumb.map(str.upper)

        assert isinstance(finger_result, FingerCluster)
        assert isinstance(thumb_result, ThumbCluster)

    def test_map_with_type_change(self):
        """map can change the value type."""
        cluster = FingerCluster("abc", center_key="a", south_key="hello")
        result = cluster.map(len)

        assert result.center_key == 1
        assert result.north_key == 3
        assert result.south_key == 5

    def test_map_preserves_field_order(self):
        """map preserves the field order."""
        cluster = FingerCluster.from_sequence(["a", "b", "c", "d", "e", "f"])
        result = cluster.map(str.upper)

        assert list(result) == ["A", "B", "C", "D", "E", "F"]

    def test_map_chaining(self):
        """map can be chained."""
        cluster = FingerCluster("hello")
        result = cluster.map(str.upper).map(lambda s: s + "!")

        assert result.center_key == "HELLO!"
        assert result.north_key == "HELLO!"

    def test_map_with_lambda(self):
        """map works with lambda functions."""
        cluster = FingerCluster(1, center_key=2, south_key=3)
        result = cluster.map(lambda x: x * 10)

        assert result.center_key == 20
        assert result.north_key == 10
        assert result.south_key == 30

    def test_map_result_is_frozen(self):
        """Mapped cluster is immutable."""
        cluster = FingerCluster("a")
        result = cluster.map(str.upper)

        with pytest.raises(FrozenInstanceError):
            result.center_key = "X"

    def test_map_with_none_values(self):
        """map handles None values correctly."""
        cluster = FingerCluster(None, center_key="a")
        result = cluster.map(lambda x: x.upper() if x else "NONE")

        assert result.center_key == "A"
        assert result.north_key == "NONE"


class TestZipClustersFunction:
    """Tests for the zip_clusters public function."""

    def test_zip_finger_clusters(self):
        """zip_clusters combines FingerClusters correctly."""
        codes = FingerCluster("KC_NO", center_key="KC_A")
        labels = FingerCluster("", center_key="A")

        combined = zip_clusters(FingerCluster, codes=codes, labels=labels)

        assert combined.center_key.codes == "KC_A"
        assert combined.center_key.labels == "A"

    def test_zip_thumb_clusters(self):
        """zip_clusters combines ThumbClusters correctly."""
        codes = ThumbCluster("KC_NO", down_key="KC_SPC")
        labels = ThumbCluster("", down_key="Space")

        combined = zip_clusters(ThumbCluster, codes=codes, labels=labels)

        assert combined.down_key.codes == "KC_SPC"
        assert combined.down_key.labels == "Space"

    def test_zip_with_custom_bundle_name(self):
        """zip_clusters accepts custom bundle name as second positional arg."""
        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        combined = zip_clusters(FingerCluster, "MyBundle", codes=codes, labels=labels)

        assert combined.center_key.__class__.__name__ == "MyBundle"

    def test_zip_empty_clusters_raises_valueerror(self):
        """zip_clusters raises ValueError when no clusters provided."""
        with pytest.raises(ValueError) as exc_info:
            zip_clusters(FingerCluster)
        assert "At least one cluster required" in str(exc_info.value)

    def test_zip_returns_correct_cluster_type(self):
        """zip_clusters returns instance of the specified cluster type."""
        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        result = zip_clusters(FingerCluster, codes=codes, labels=labels)
        assert isinstance(result, FingerCluster)

        thumb_codes = ThumbCluster("KC_NO")
        thumb_labels = ThumbCluster("")

        thumb_result = zip_clusters(ThumbCluster, codes=thumb_codes, labels=thumb_labels)
        assert isinstance(thumb_result, ThumbCluster)

    def test_zip_with_custom_dataclass_type(self):
        """zip_clusters accepts custom dataclass type as second positional arg."""

        @dataclass(frozen=True)
        class CustomKeyData:
            codes: str
            labels: str

        codes = FingerCluster("KC_NO", center_key="KC_A")
        labels = FingerCluster("", center_key="A")

        combined = zip_clusters(FingerCluster, CustomKeyData, codes=codes, labels=labels)

        assert isinstance(combined.center_key, CustomKeyData)
        assert combined.center_key.codes == "KC_A"
        assert combined.center_key.labels == "A"

    def test_zip_with_custom_dataclass_missing_attribute(self):
        """zip_clusters raises TypeError when custom class is missing attributes."""

        @dataclass(frozen=True)
        class PartialBundle:
            codes: str

        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")

        with pytest.raises(TypeError) as exc_info:
            zip_clusters(FingerCluster, PartialBundle, codes=codes, labels=labels)
        assert "PartialBundle" in str(exc_info.value)
        assert "missing required attributes" in str(exc_info.value)


class TestClusterEquality:
    """Tests for cluster equality and identity."""

    def test_clusters_with_same_values_are_not_identical(self):
        """Two clusters with same values are different objects."""
        cluster1 = FingerCluster("A")
        cluster2 = FingerCluster("A")
        assert cluster1 is not cluster2

    def test_cluster_values_accessible_after_creation(self):
        """Cluster values remain accessible and unchanged after creation."""
        cluster = FingerCluster("initial", center_key="modified")
        # Access multiple times to ensure stability
        assert cluster.center_key == "modified"
        assert cluster.center_key == "modified"
        assert cluster.north_key == "initial"


class TestClusterImmutability:
    """Tests for cluster immutability (frozen dataclasses)."""

    def test_finger_cluster_is_frozen(self):
        """FingerCluster cannot be modified after creation."""
        cluster = FingerCluster("X")
        with pytest.raises(FrozenInstanceError):
            cluster.center_key = "Y"

    def test_thumb_cluster_is_frozen(self):
        """ThumbCluster cannot be modified after creation."""
        cluster = ThumbCluster("X")
        with pytest.raises(FrozenInstanceError):
            cluster.down_key = "Space"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_string_default(self):
        """Empty string is a valid default value."""
        cluster = FingerCluster("")
        assert cluster.center_key == ""
        assert all(v == "" for v in cluster)

    def test_zero_default(self):
        """Zero is a valid default value."""
        cluster = FingerCluster(0)
        assert cluster.center_key == 0
        assert all(v == 0 for v in cluster)

    def test_false_default(self):
        """False is a valid default value."""
        cluster = FingerCluster(False)
        assert cluster.center_key is False
        assert all(v is False for v in cluster)

    def test_list_as_value(self):
        """Lists can be used as cluster values."""
        default_list = [1, 2, 3]
        custom_list = [4, 5, 6]
        cluster = FingerCluster(default_list, center_key=custom_list)
        assert cluster.center_key == [4, 5, 6]
        assert cluster.north_key == [1, 2, 3]

    def test_dict_as_value(self):
        """Dictionaries can be used as cluster values."""
        cluster = FingerCluster({}, center_key={"key": "value"})
        assert cluster.center_key == {"key": "value"}
        assert cluster.north_key == {}

    def test_callable_as_value(self):
        """Callables can be used as cluster values."""

        def my_func():
            return "called"

        cluster = FingerCluster(None, center_key=my_func)
        assert cluster.center_key() == "called"

    def test_all_fields_override_with_default(self):
        """All fields can be overridden even when default is provided."""
        cluster = FingerCluster(
            "default",  # This should be ignored
            center_key="C",
            north_key="N",
            east_key="E",
            south_key="S",
            west_key="W",
            double_south_key="DS",
        )
        assert cluster.center_key == "C"
        assert cluster.north_key == "N"
        assert cluster.east_key == "E"
        assert cluster.south_key == "S"
        assert cluster.west_key == "W"
        assert cluster.double_south_key == "DS"


class TestZippedClusterIteration:
    """Tests for iterating over zipped clusters."""

    def test_zipped_cluster_is_iterable(self):
        """Zipped cluster can be iterated."""
        codes = FingerCluster("KC_NO")
        labels = FingerCluster("")
        combined = zip_clusters(FingerCluster, codes=codes, labels=labels)

        values = list(combined)
        assert len(values) == 6
        # Each value should be a bundle
        assert all(hasattr(v, "codes") and hasattr(v, "labels") for v in values)

    def test_zipped_cluster_can_be_unpacked(self):
        """Zipped cluster can be unpacked into variables."""
        codes = FingerCluster("KC_NO", center_key="KC_A")
        labels = FingerCluster("", center_key="A")
        combined = zip_clusters(FingerCluster, codes=codes, labels=labels)

        center, north, east, south, west, dsouth = combined
        assert center.codes == "KC_A"
        assert center.labels == "A"
        assert north.codes == "KC_NO"
        assert north.labels == ""


# --- SplitSide Tests ---


def make_finger_cluster(prefix: str) -> FingerCluster[str]:
    """Helper to create a FingerCluster with unique values."""
    return FingerCluster(
        center_key=f"{prefix}_C",
        north_key=f"{prefix}_N",
        east_key=f"{prefix}_E",
        south_key=f"{prefix}_S",
        west_key=f"{prefix}_W",
        double_south_key=f"{prefix}_DS",
    )


def make_thumb_cluster(prefix: str) -> ThumbCluster[str]:
    """Helper to create a ThumbCluster with unique values."""
    return ThumbCluster(
        down_key=f"{prefix}_D",
        pad_key=f"{prefix}_P",
        up_key=f"{prefix}_U",
        nail_key=f"{prefix}_N",
        knuckle_key=f"{prefix}_K",
        double_down_key=f"{prefix}_DD",
    )


def make_split_side(side: str) -> SplitSide[str]:
    """Helper to create a SplitSide with unique values."""
    return SplitSide(
        index=make_finger_cluster(f"{side}_I"),
        middle=make_finger_cluster(f"{side}_M"),
        ring=make_finger_cluster(f"{side}_R"),
        pinky=make_finger_cluster(f"{side}_P"),
        thumb=make_thumb_cluster(f"{side}_T"),
    )


class TestSplitSideInitialization:
    """Tests for SplitSide initialization."""

    def test_init_with_all_clusters(self):
        """SplitSide requires all clusters to be provided."""
        side = SplitSide(
            index=FingerCluster("I"),
            middle=FingerCluster("M"),
            ring=FingerCluster("R"),
            pinky=FingerCluster("P"),
            thumb=ThumbCluster("T"),
        )
        assert side.index.center_key == "I"
        assert side.middle.center_key == "M"
        assert side.ring.center_key == "R"
        assert side.pinky.center_key == "P"
        assert side.thumb.down_key == "T"

    def test_init_missing_cluster_raises_typeerror(self):
        """SplitSide raises TypeError when a cluster is missing."""
        with pytest.raises(TypeError):
            SplitSide(
                index=FingerCluster("I"),
                middle=FingerCluster("M"),
                # missing ring, pinky, thumb
            )

    def test_is_frozen(self):
        """SplitSide is immutable."""
        side = make_split_side("L")
        with pytest.raises(FrozenInstanceError):
            side.index = FingerCluster("X")

    def test_generic_type_support(self):
        """SplitSide supports generic types."""
        side = SplitSide(
            index=FingerCluster(1),
            middle=FingerCluster(2),
            ring=FingerCluster(3),
            pinky=FingerCluster(4),
            thumb=ThumbCluster(5),
        )
        assert side.index.center_key == 1
        assert side.thumb.down_key == 5


class TestSplitSideIteration:
    """Tests for SplitSide iteration."""

    def test_iteration_yields_all_clusters(self):
        """SplitSide iteration yields all 5 clusters."""
        side = make_split_side("L")
        clusters = list(side)
        assert len(clusters) == 5

    def test_iteration_order(self):
        """SplitSide iterates in order: index, middle, ring, pinky, thumb."""
        side = SplitSide(
            index=FingerCluster("I"),
            middle=FingerCluster("M"),
            ring=FingerCluster("R"),
            pinky=FingerCluster("P"),
            thumb=ThumbCluster("T"),
        )
        clusters = list(side)
        assert clusters[0].center_key == "I"  # index
        assert clusters[1].center_key == "M"  # middle
        assert clusters[2].center_key == "R"  # ring
        assert clusters[3].center_key == "P"  # pinky
        assert clusters[4].down_key == "T"  # thumb

    def test_unpacking_clusters(self):
        """SplitSide can be unpacked into variables."""
        side = make_split_side("L")
        index, middle, ring, pinky, thumb = side
        assert index is side.index
        assert middle is side.middle
        assert ring is side.ring
        assert pinky is side.pinky
        assert thumb is side.thumb


class TestSplitSideFingersProperty:
    """Tests for SplitSide.fingers property."""

    def test_fingers_returns_tuple_of_four(self):
        """fingers property returns tuple of 4 finger clusters."""
        side = make_split_side("L")
        fingers = side.fingers
        assert isinstance(fingers, tuple)
        assert len(fingers) == 4

    def test_fingers_order(self):
        """fingers are in order: index, middle, ring, pinky."""
        side = SplitSide(
            index=FingerCluster("I"),
            middle=FingerCluster("M"),
            ring=FingerCluster("R"),
            pinky=FingerCluster("P"),
            thumb=ThumbCluster("T"),
        )
        fingers = side.fingers
        assert fingers[0].center_key == "I"
        assert fingers[1].center_key == "M"
        assert fingers[2].center_key == "R"
        assert fingers[3].center_key == "P"

    def test_fingers_does_not_include_thumb(self):
        """fingers property excludes thumb cluster."""
        side = make_split_side("L")
        fingers = side.fingers
        assert side.thumb not in fingers


class TestSplitSideGetItem:
    """Tests for SplitSide.__getitem__ indexing."""

    def test_index_finger_keys(self):
        """Indices 0-5 access index finger keys."""
        side = make_split_side("L")
        # Index finger is first cluster
        assert side[0] == "L_I_C"  # center
        assert side[1] == "L_I_N"  # north
        assert side[2] == "L_I_E"  # east
        assert side[3] == "L_I_S"  # south
        assert side[4] == "L_I_W"  # west
        assert side[5] == "L_I_DS"  # double_south

    def test_middle_finger_keys(self):
        """Indices 6-11 access middle finger keys."""
        side = make_split_side("L")
        assert side[6] == "L_M_C"
        assert side[11] == "L_M_DS"

    def test_ring_finger_keys(self):
        """Indices 12-17 access ring finger keys."""
        side = make_split_side("L")
        assert side[12] == "L_R_C"
        assert side[17] == "L_R_DS"

    def test_pinky_finger_keys(self):
        """Indices 18-23 access pinky finger keys."""
        side = make_split_side("L")
        assert side[18] == "L_P_C"
        assert side[23] == "L_P_DS"

    def test_thumb_keys(self):
        """Indices 24-29 access thumb keys."""
        side = make_split_side("L")
        assert side[24] == "L_T_D"  # down
        assert side[25] == "L_T_P"  # pad
        assert side[26] == "L_T_U"  # up
        assert side[27] == "L_T_N"  # nail
        assert side[28] == "L_T_K"  # knuckle
        assert side[29] == "L_T_DD"  # double_down

    def test_negative_index_raises_indexerror(self):
        """Negative indices raise IndexError."""
        side = make_split_side("L")
        with pytest.raises(IndexError) as exc_info:
            _ = side[-1]
        assert "out of range" in str(exc_info.value)

    def test_index_30_raises_indexerror(self):
        """Index 30 raises IndexError (only 30 keys: 0-29)."""
        side = make_split_side("L")
        with pytest.raises(IndexError) as exc_info:
            _ = side[30]
        assert "out of range" in str(exc_info.value)

    def test_large_index_raises_indexerror(self):
        """Large indices raise IndexError."""
        side = make_split_side("L")
        with pytest.raises(IndexError):
            _ = side[100]

    def test_all_30_keys_accessible(self):
        """All 30 keys are accessible via indexing."""
        side = make_split_side("L")
        keys = [side[i] for i in range(30)]
        assert len(keys) == 30
        # All should be non-empty strings
        assert all(isinstance(k, str) and k for k in keys)


# --- SvalboardLayout Tests ---


class TestSvalboardLayoutInitialization:
    """Tests for SvalboardLayout initialization."""

    def test_init_with_both_sides(self):
        """SvalboardLayout requires both left and right sides."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        assert layout.left.index.center_key == "L_I_C"
        assert layout.right.index.center_key == "R_I_C"

    def test_init_missing_side_raises_typeerror(self):
        """SvalboardLayout raises TypeError when a side is missing."""
        with pytest.raises(TypeError):
            SvalboardLayout(left=make_split_side("L"))

    def test_is_frozen(self):
        """SvalboardLayout is immutable."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        with pytest.raises(FrozenInstanceError):
            layout.left = make_split_side("X")

    def test_generic_type_support(self):
        """SvalboardLayout supports generic types."""
        int_side = SplitSide(
            index=FingerCluster(1),
            middle=FingerCluster(2),
            ring=FingerCluster(3),
            pinky=FingerCluster(4),
            thumb=ThumbCluster(5),
        )
        layout = SvalboardLayout(left=int_side, right=int_side)
        assert layout.left.index.center_key == 1


class TestSvalboardLayoutIteration:
    """Tests for SvalboardLayout iteration."""

    def test_iteration_yields_60_keys(self):
        """SvalboardLayout iteration yields all 60 keys."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        keys = list(layout)
        assert len(keys) == 60

    def test_iteration_order_right_fingers_first(self):
        """Iteration starts with right hand finger keys."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        keys = list(layout)
        # First 24 keys are right hand fingers
        assert keys[0] == "R_I_C"  # Right index center
        assert keys[6] == "R_M_C"  # Right middle center
        assert keys[12] == "R_R_C"  # Right ring center
        assert keys[18] == "R_P_C"  # Right pinky center

    def test_iteration_order_left_fingers_second(self):
        """Iteration continues with left hand finger keys."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        keys = list(layout)
        # Keys 24-47 are left hand fingers
        assert keys[24] == "L_I_C"  # Left index center
        assert keys[30] == "L_M_C"  # Left middle center

    def test_iteration_order_thumbs_last(self):
        """Iteration ends with thumb keys (right then left)."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        keys = list(layout)
        # Keys 48-53 are right thumb
        assert keys[48] == "R_T_D"  # Right thumb down
        # Keys 54-59 are left thumb
        assert keys[54] == "L_T_D"  # Left thumb down
        assert keys[59] == "L_T_DD"  # Left thumb double_down (last key)


class TestSvalboardLayoutGetItem:
    """Tests for SvalboardLayout.__getitem__ indexing."""

    def test_right_finger_keys(self):
        """Indices 0-23 access right hand finger keys."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        assert layout[0] == "R_I_C"  # Right index center
        assert layout[6] == "R_M_C"  # Right middle center
        assert layout[12] == "R_R_C"  # Right ring center
        assert layout[18] == "R_P_C"  # Right pinky center
        assert layout[23] == "R_P_DS"  # Right pinky double_south

    def test_left_finger_keys(self):
        """Indices 24-47 access left hand finger keys."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        assert layout[24] == "L_I_C"  # Left index center
        assert layout[30] == "L_M_C"  # Left middle center
        assert layout[36] == "L_R_C"  # Left ring center
        assert layout[42] == "L_P_C"  # Left pinky center
        assert layout[47] == "L_P_DS"  # Left pinky double_south

    def test_right_thumb_keys(self):
        """Indices 48-53 access right thumb keys."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        assert layout[48] == "R_T_D"  # down
        assert layout[49] == "R_T_P"  # pad
        assert layout[50] == "R_T_U"  # up
        assert layout[51] == "R_T_N"  # nail
        assert layout[52] == "R_T_K"  # knuckle
        assert layout[53] == "R_T_DD"  # double_down

    def test_left_thumb_keys(self):
        """Indices 54-59 access left thumb keys."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        assert layout[54] == "L_T_D"  # down
        assert layout[55] == "L_T_P"  # pad
        assert layout[56] == "L_T_U"  # up
        assert layout[57] == "L_T_N"  # nail
        assert layout[58] == "L_T_K"  # knuckle
        assert layout[59] == "L_T_DD"  # double_down

    def test_negative_index_raises_indexerror(self):
        """Negative indices raise IndexError."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        with pytest.raises(IndexError) as exc_info:
            _ = layout[-1]
        assert "out of range" in str(exc_info.value)

    def test_index_60_raises_indexerror(self):
        """Index 60 raises IndexError (only 60 keys: 0-59)."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        with pytest.raises(IndexError) as exc_info:
            _ = layout[60]
        assert "out of range" in str(exc_info.value)

    def test_large_index_raises_indexerror(self):
        """Large indices raise IndexError."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        with pytest.raises(IndexError):
            _ = layout[100]

    def test_all_60_keys_accessible(self):
        """All 60 keys are accessible via indexing."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        keys = [layout[i] for i in range(60)]
        assert len(keys) == 60
        assert all(isinstance(k, str) and k for k in keys)

    def test_getitem_matches_iteration(self):
        """__getitem__ returns same values as iteration in same order."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        iter_keys = list(layout)
        getitem_keys = [layout[i] for i in range(60)]
        assert iter_keys == getitem_keys


class TestSvalboardLayoutEdgeCases:
    """Edge case tests for SvalboardLayout."""

    def test_boundary_indices(self):
        """Test boundary indices between regions."""
        layout = SvalboardLayout(
            left=make_split_side("L"),
            right=make_split_side("R"),
        )
        # Boundary between right fingers and left fingers
        assert layout[23] == "R_P_DS"  # Last right finger
        assert layout[24] == "L_I_C"  # First left finger

        # Boundary between left fingers and right thumb
        assert layout[47] == "L_P_DS"  # Last left finger
        assert layout[48] == "R_T_D"  # First right thumb

        # Boundary between right thumb and left thumb
        assert layout[53] == "R_T_DD"  # Last right thumb
        assert layout[54] == "L_T_D"  # First left thumb


class TestSvalboardLayoutFromSequence:
    """Tests for SvalboardLayout.from_sequence classmethod."""

    def test_from_sequence_with_list(self):
        """from_sequence creates layout from a list of 60 values."""
        values = [f"KEY_{i}" for i in range(60)]
        layout = SvalboardLayout.from_sequence(values)

        # Check first and last values
        assert layout[0] == "KEY_0"
        assert layout[59] == "KEY_59"

    def test_from_sequence_with_tuple(self):
        """from_sequence creates layout from a tuple of 60 values."""
        values = tuple(f"KEY_{i}" for i in range(60))
        layout = SvalboardLayout.from_sequence(values)

        assert layout[0] == "KEY_0"
        assert layout[59] == "KEY_59"

    def test_from_sequence_preserves_order(self):
        """from_sequence preserves index-to-value mapping."""
        values = [f"V{i}" for i in range(60)]
        layout = SvalboardLayout.from_sequence(values)

        # Every index should map to its corresponding value
        for i in range(60):
            assert layout[i] == f"V{i}"

    def test_from_sequence_matches_iteration(self):
        """Layout from from_sequence iterates in same order as input."""
        values = list(range(60))
        layout = SvalboardLayout.from_sequence(values)

        assert list(layout) == values

    def test_from_sequence_right_finger_clusters(self):
        """from_sequence correctly populates right finger clusters."""
        values = [f"V{i}" for i in range(60)]
        layout = SvalboardLayout.from_sequence(values)

        # Right index finger (0-5)
        assert layout.right.index.center_key == "V0"
        assert layout.right.index.north_key == "V1"
        assert layout.right.index.east_key == "V2"
        assert layout.right.index.south_key == "V3"
        assert layout.right.index.west_key == "V4"
        assert layout.right.index.double_south_key == "V5"

        # Right middle finger (6-11)
        assert layout.right.middle.center_key == "V6"

        # Right ring finger (12-17)
        assert layout.right.ring.center_key == "V12"

        # Right pinky finger (18-23)
        assert layout.right.pinky.center_key == "V18"
        assert layout.right.pinky.double_south_key == "V23"

    def test_from_sequence_left_finger_clusters(self):
        """from_sequence correctly populates left finger clusters."""
        values = [f"V{i}" for i in range(60)]
        layout = SvalboardLayout.from_sequence(values)

        # Left index finger (24-29)
        assert layout.left.index.center_key == "V24"
        assert layout.left.index.double_south_key == "V29"

        # Left middle finger (30-35)
        assert layout.left.middle.center_key == "V30"

        # Left ring finger (36-41)
        assert layout.left.ring.center_key == "V36"

        # Left pinky finger (42-47)
        assert layout.left.pinky.center_key == "V42"
        assert layout.left.pinky.double_south_key == "V47"

    def test_from_sequence_thumb_clusters(self):
        """from_sequence correctly populates thumb clusters."""
        values = [f"V{i}" for i in range(60)]
        layout = SvalboardLayout.from_sequence(values)

        # Right thumb (48-53)
        assert layout.right.thumb.down_key == "V48"
        assert layout.right.thumb.pad_key == "V49"
        assert layout.right.thumb.up_key == "V50"
        assert layout.right.thumb.nail_key == "V51"
        assert layout.right.thumb.knuckle_key == "V52"
        assert layout.right.thumb.double_down_key == "V53"

        # Left thumb (54-59)
        assert layout.left.thumb.down_key == "V54"
        assert layout.left.thumb.pad_key == "V55"
        assert layout.left.thumb.up_key == "V56"
        assert layout.left.thumb.nail_key == "V57"
        assert layout.left.thumb.knuckle_key == "V58"
        assert layout.left.thumb.double_down_key == "V59"

    def test_from_sequence_too_few_values_raises_valueerror(self):
        """from_sequence raises ValueError for fewer than 60 values."""
        values = ["key"] * 59
        with pytest.raises(ValueError) as exc_info:
            SvalboardLayout.from_sequence(values)
        assert "Expected exactly 60 values" in str(exc_info.value)
        assert "got 59" in str(exc_info.value)

    def test_from_sequence_too_many_values_raises_valueerror(self):
        """from_sequence raises ValueError for more than 60 values."""
        values = ["key"] * 61
        with pytest.raises(ValueError) as exc_info:
            SvalboardLayout.from_sequence(values)
        assert "Expected exactly 60 values" in str(exc_info.value)
        assert "got 61" in str(exc_info.value)

    def test_from_sequence_empty_raises_valueerror(self):
        """from_sequence raises ValueError for empty sequence."""
        with pytest.raises(ValueError) as exc_info:
            SvalboardLayout.from_sequence([])
        assert "Expected exactly 60 values" in str(exc_info.value)

    def test_from_sequence_with_integers(self):
        """from_sequence works with integer values."""
        values = list(range(60))
        layout = SvalboardLayout.from_sequence(values)

        assert layout[0] == 0
        assert layout[59] == 59
        assert layout.right.index.center_key == 0

    def test_from_sequence_with_none_values(self):
        """from_sequence works with None values."""
        values = [None] * 60
        layout = SvalboardLayout.from_sequence(values)

        assert layout[0] is None
        assert layout[59] is None

    def test_from_sequence_with_mixed_types(self):
        """from_sequence works with mixed value types."""
        values = [i if i % 2 == 0 else str(i) for i in range(60)]
        layout = SvalboardLayout.from_sequence(values)

        assert layout[0] == 0
        assert layout[1] == "1"
        assert layout[58] == 58
        assert layout[59] == "59"

    def test_from_sequence_result_is_frozen(self):
        """Layout created by from_sequence is immutable."""
        values = ["key"] * 60
        layout = SvalboardLayout.from_sequence(values)

        with pytest.raises(FrozenInstanceError):
            layout.left = make_split_side("X")


class TestSvalboardLayoutMap:
    """Tests for SvalboardLayout.map method."""

    def test_map_transforms_all_values(self):
        """map transforms all 60 key values."""
        layout = SvalboardLayout.from_sequence([f"key_{i}" for i in range(60)])
        result = layout.map(str.upper)

        assert result[0] == "KEY_0"
        assert result[30] == "KEY_30"
        assert result[59] == "KEY_59"

    def test_map_returns_svalboard_layout(self):
        """map returns a SvalboardLayout instance."""
        layout = SvalboardLayout.from_sequence(["a"] * 60)
        result = layout.map(str.upper)

        assert isinstance(result, SvalboardLayout)

    def test_map_with_type_change(self):
        """map can change the value type."""
        layout = SvalboardLayout.from_sequence([f"{'x' * (i + 1)}" for i in range(60)])
        result = layout.map(len)

        assert result[0] == 1
        assert result[5] == 6
        assert result[59] == 60

    def test_map_preserves_position_order(self):
        """map preserves the position ordering."""
        layout = SvalboardLayout.from_sequence(list(range(60)))
        result = layout.map(lambda x: x * 2)

        for i in range(60):
            assert result[i] == i * 2

    def test_map_chaining(self):
        """map can be chained."""
        layout = SvalboardLayout.from_sequence(["hello"] * 60)
        result = layout.map(str.upper).map(lambda s: s + "!")

        assert result[0] == "HELLO!"
        assert result[59] == "HELLO!"

    def test_map_with_lambda(self):
        """map works with lambda functions."""
        layout = SvalboardLayout.from_sequence(list(range(60)))
        result = layout.map(lambda x: x * 10)

        assert result[0] == 0
        assert result[1] == 10
        assert result[59] == 590

    def test_map_result_is_frozen(self):
        """Mapped layout is immutable."""
        layout = SvalboardLayout.from_sequence(["a"] * 60)
        result = layout.map(str.upper)

        with pytest.raises(FrozenInstanceError):
            result.left = make_split_side("X")

    def test_map_accessible_via_hierarchy(self):
        """Mapped values accessible via side/cluster hierarchy."""
        layout = SvalboardLayout.from_sequence([f"v{i}" for i in range(60)])
        result = layout.map(str.upper)

        # Access via hierarchy
        assert result.right.index.center_key == "V0"
        assert result.left.thumb.down_key == "V54"


class TestSvalboardLayoutFromZipped:
    """Tests for SvalboardLayout.from_zipped classmethod."""

    def test_from_zipped_two_layouts(self):
        """from_zipped combines two layouts into bundled values."""
        codes = SvalboardLayout.from_sequence([f"KC_{i}" for i in range(60)])
        labels = SvalboardLayout.from_sequence([f"L{i}" for i in range(60)])

        combined = SvalboardLayout.from_zipped(codes=codes, labels=labels)

        assert combined[0].codes == "KC_0"
        assert combined[0].labels == "L0"
        assert combined[59].codes == "KC_59"
        assert combined[59].labels == "L59"

    def test_from_zipped_three_layouts(self):
        """from_zipped can combine multiple layouts."""
        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)
        colors = SvalboardLayout.from_sequence(["#F00"] * 60)

        combined = SvalboardLayout.from_zipped(code=codes, label=labels, color=colors)

        assert combined[0].code == "KC_A"
        assert combined[0].label == "A"
        assert combined[0].color == "#F00"

    def test_from_zipped_custom_bundle_name(self):
        """from_zipped accepts custom bundle class name."""
        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)

        combined = SvalboardLayout.from_zipped(bundle="KeyData", codes=codes, labels=labels)

        assert combined[0].__class__.__name__ == "KeyData"

    def test_from_zipped_preserves_all_positions(self):
        """from_zipped correctly maps all 60 positions."""
        codes = SvalboardLayout.from_sequence([f"C{i}" for i in range(60)])
        labels = SvalboardLayout.from_sequence([f"L{i}" for i in range(60)])

        combined = SvalboardLayout.from_zipped(codes=codes, labels=labels)

        for i in range(60):
            assert combined[i].codes == f"C{i}"
            assert combined[i].labels == f"L{i}"

    def test_from_zipped_bundles_are_frozen(self):
        """Bundle objects created by from_zipped are immutable."""
        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)

        combined = SvalboardLayout.from_zipped(codes=codes, labels=labels)

        with pytest.raises(FrozenInstanceError):
            combined[0].codes = "KC_B"

    def test_from_zipped_empty_raises_valueerror(self):
        """from_zipped raises ValueError when no layouts provided."""
        with pytest.raises(ValueError) as exc_info:
            SvalboardLayout.from_zipped()
        assert "At least one layout is required" in str(exc_info.value)

    def test_from_zipped_result_is_iterable(self):
        """Layout from from_zipped can be iterated."""
        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)

        combined = SvalboardLayout.from_zipped(codes=codes, labels=labels)

        values = list(combined)
        assert len(values) == 60
        assert all(hasattr(v, "codes") and hasattr(v, "labels") for v in values)

    def test_from_zipped_accessible_via_hierarchy(self):
        """Zipped layout values accessible via side/cluster hierarchy."""
        codes = SvalboardLayout.from_sequence([f"C{i}" for i in range(60)])
        labels = SvalboardLayout.from_sequence([f"L{i}" for i in range(60)])

        combined = SvalboardLayout.from_zipped(codes=codes, labels=labels)

        # Access via hierarchy
        assert combined.right.index.center_key.codes == "C0"
        assert combined.right.index.center_key.labels == "L0"
        assert combined.left.thumb.down_key.codes == "C54"
        assert combined.left.thumb.down_key.labels == "L54"

    def test_from_zipped_custom_dataclass_type(self):
        """from_zipped accepts a custom dataclass type as the bundle."""

        @dataclass(frozen=True)
        class LayoutKeyData:
            codes: str
            labels: str

        codes = SvalboardLayout.from_sequence([f"KC_{i}" for i in range(60)])
        labels = SvalboardLayout.from_sequence([f"L{i}" for i in range(60)])

        combined = SvalboardLayout.from_zipped(bundle=LayoutKeyData, codes=codes, labels=labels)

        assert isinstance(combined[0], LayoutKeyData)
        assert combined[0].codes == "KC_0"
        assert combined[0].labels == "L0"
        assert combined[59].codes == "KC_59"
        assert combined[59].labels == "L59"

    def test_from_zipped_custom_dataclass_missing_attribute(self):
        """from_zipped raises TypeError when custom class is missing attributes."""

        @dataclass(frozen=True)
        class IncompleteLayoutBundle:
            codes: str

        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)

        with pytest.raises(TypeError) as exc_info:
            SvalboardLayout.from_zipped(bundle=IncompleteLayoutBundle, codes=codes, labels=labels)
        assert "IncompleteLayoutBundle" in str(exc_info.value)
        assert "missing required attributes" in str(exc_info.value)
        assert "labels" in str(exc_info.value)

    def test_from_zipped_custom_dataclass_with_three_sources(self):
        """from_zipped works with custom dataclass for three sources."""

        @dataclass(frozen=True)
        class FullKeyData:
            code: str
            label: str
            color: str

        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)
        colors = SvalboardLayout.from_sequence(["#F00"] * 60)

        combined = SvalboardLayout.from_zipped(
            bundle=FullKeyData, code=codes, label=labels, color=colors
        )

        assert isinstance(combined[0], FullKeyData)
        assert combined[0].code == "KC_A"
        assert combined[0].label == "A"
        assert combined[0].color == "#F00"


# --- SvalboardKeymap Tests ---


class TestSvalboardKeymapInitialization:
    """Tests for SvalboardKeymap initialization."""

    def test_init_with_layers(self):
        """SvalboardKeymap can be initialized with a list of layers."""
        layer0 = SvalboardLayout.from_sequence(["L0"] * 60)
        layer1 = SvalboardLayout.from_sequence(["L1"] * 60)

        keymap = SvalboardKeymap(layers=[layer0, layer1])

        assert len(keymap.layers) == 2
        assert keymap.layers[0][0] == "L0"
        assert keymap.layers[1][0] == "L1"

    def test_init_single_layer(self):
        """SvalboardKeymap can have a single layer."""
        layer = SvalboardLayout.from_sequence(["KEY"] * 60)
        keymap = SvalboardKeymap(layers=[layer])

        assert len(keymap.layers) == 1

    def test_init_many_layers(self):
        """SvalboardKeymap supports many layers."""
        layers = [SvalboardLayout.from_sequence([f"L{i}"] * 60) for i in range(10)]
        keymap = SvalboardKeymap(layers=layers)

        assert len(keymap.layers) == 10
        assert keymap.layers[5][0] == "L5"

    def test_is_frozen(self):
        """SvalboardKeymap is immutable."""
        layer = SvalboardLayout.from_sequence(["KEY"] * 60)
        keymap = SvalboardKeymap(layers=[layer])

        with pytest.raises(FrozenInstanceError):
            keymap.layers = []

    def test_layers_list_is_mutable(self):
        """The layers list itself can be modified (dataclass doesn't deep-freeze)."""
        layer0 = SvalboardLayout.from_sequence(["L0"] * 60)
        layer1 = SvalboardLayout.from_sequence(["L1"] * 60)
        keymap = SvalboardKeymap(layers=[layer0])

        # The list reference is frozen, but list contents can change
        # This is expected Python behavior for frozen dataclasses with mutable fields
        keymap.layers.append(layer1)
        assert len(keymap.layers) == 2


class TestSvalboardKeymapAccess:
    """Tests for accessing SvalboardKeymap data."""

    def test_access_layer_by_index(self):
        """Layers can be accessed by index."""
        layers = [SvalboardLayout.from_sequence([f"L{i}_KEY"] * 60) for i in range(3)]
        keymap = SvalboardKeymap(layers=layers)

        assert keymap.layers[0][0] == "L0_KEY"
        assert keymap.layers[1][0] == "L1_KEY"
        assert keymap.layers[2][0] == "L2_KEY"

    def test_access_key_in_layer(self):
        """Individual keys can be accessed via layer index."""
        layer = SvalboardLayout.from_sequence([f"K{i}" for i in range(60)])
        keymap = SvalboardKeymap(layers=[layer])

        assert keymap.layers[0][0] == "K0"
        assert keymap.layers[0][59] == "K59"

    def test_iterate_over_layers(self):
        """Layers can be iterated."""
        layers = [SvalboardLayout.from_sequence([f"L{i}"] * 60) for i in range(3)]
        keymap = SvalboardKeymap(layers=layers)

        layer_values = [layer[0] for layer in keymap.layers]
        assert layer_values == ["L0", "L1", "L2"]

    def test_empty_layers_list(self):
        """SvalboardKeymap can have empty layers list."""
        keymap = SvalboardKeymap(layers=[])
        assert len(keymap.layers) == 0


class TestSvalboardKeymapWithZippedLayers:
    """Tests for SvalboardKeymap with zipped layout layers."""

    def test_keymap_with_zipped_layers(self):
        """SvalboardKeymap works with zipped layouts."""
        codes_l0 = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels_l0 = SvalboardLayout.from_sequence(["A"] * 60)
        layer0 = SvalboardLayout.from_zipped(code=codes_l0, label=labels_l0)

        codes_l1 = SvalboardLayout.from_sequence(["KC_1"] * 60)
        labels_l1 = SvalboardLayout.from_sequence(["1"] * 60)
        layer1 = SvalboardLayout.from_zipped(code=codes_l1, label=labels_l1)

        keymap = SvalboardKeymap(layers=[layer0, layer1])

        assert keymap.layers[0][0].code == "KC_A"
        assert keymap.layers[0][0].label == "A"
        assert keymap.layers[1][0].code == "KC_1"
        assert keymap.layers[1][0].label == "1"


class TestZipLayoutsFunction:
    """Tests for the zip_layouts public function."""

    def test_zip_two_layouts(self):
        """zip_layouts combines two layouts correctly."""
        codes = SvalboardLayout.from_sequence([f"KC_{i}" for i in range(60)])
        labels = SvalboardLayout.from_sequence([f"L{i}" for i in range(60)])

        combined = zip_layouts(codes=codes, labels=labels)

        assert combined[0].codes == "KC_0"
        assert combined[0].labels == "L0"

    def test_zip_with_custom_bundle_name(self):
        """zip_layouts accepts custom bundle name as first positional arg."""
        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)

        combined = zip_layouts("MyBundle", codes=codes, labels=labels)

        assert combined[0].__class__.__name__ == "MyBundle"

    def test_zip_empty_raises_valueerror(self):
        """zip_layouts raises ValueError when no layouts provided."""
        with pytest.raises(ValueError) as exc_info:
            zip_layouts()
        assert "At least one layout required" in str(exc_info.value)

    def test_zip_returns_svalboard_layout(self):
        """zip_layouts returns a SvalboardLayout instance."""
        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)

        result = zip_layouts(codes=codes, labels=labels)

        assert isinstance(result, SvalboardLayout)

    def test_zip_three_layouts(self):
        """zip_layouts can combine multiple layouts."""
        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)
        colors = SvalboardLayout.from_sequence(["#F00"] * 60)

        combined = zip_layouts("KeyData", code=codes, label=labels, color=colors)

        assert combined[0].code == "KC_A"
        assert combined[0].label == "A"
        assert combined[0].color == "#F00"

    def test_zip_preserves_all_positions(self):
        """zip_layouts correctly maps all 60 positions."""
        codes = SvalboardLayout.from_sequence([f"C{i}" for i in range(60)])
        labels = SvalboardLayout.from_sequence([f"L{i}" for i in range(60)])

        combined = zip_layouts(codes=codes, labels=labels)

        for i in range(60):
            assert combined[i].codes == f"C{i}"
            assert combined[i].labels == f"L{i}"

    def test_zip_with_custom_dataclass_type(self):
        """zip_layouts accepts custom dataclass type as first positional arg."""

        @dataclass(frozen=True)
        class ZipKeyData:
            codes: str
            labels: str

        codes = SvalboardLayout.from_sequence([f"KC_{i}" for i in range(60)])
        labels = SvalboardLayout.from_sequence([f"L{i}" for i in range(60)])

        combined = zip_layouts(ZipKeyData, codes=codes, labels=labels)

        assert isinstance(combined[0], ZipKeyData)
        assert combined[0].codes == "KC_0"
        assert combined[0].labels == "L0"

    def test_zip_with_custom_dataclass_missing_attribute(self):
        """zip_layouts raises TypeError when custom class is missing attributes."""

        @dataclass(frozen=True)
        class PartialLayoutBundle:
            codes: str

        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)

        with pytest.raises(TypeError) as exc_info:
            zip_layouts(PartialLayoutBundle, codes=codes, labels=labels)
        assert "PartialLayoutBundle" in str(exc_info.value)
        assert "missing required attributes" in str(exc_info.value)

    def test_zip_with_custom_dataclass_preserves_class_identity(self):
        """Custom dataclass type is used directly by zip_layouts."""

        @dataclass(frozen=True)
        class DirectBundle:
            codes: str
            labels: str

        codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
        labels = SvalboardLayout.from_sequence(["A"] * 60)

        combined = zip_layouts(DirectBundle, codes=codes, labels=labels)

        # Verify all positions use the exact same class
        assert type(combined[0]) is DirectBundle
        assert type(combined[30]) is DirectBundle
        assert type(combined[59]) is DirectBundle

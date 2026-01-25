"""Keyboard cluster data structures for Svalboard key layouts.

This module provides generic container classes for representing key clusters
on the Svalboard keyboard. The Svalboard has a unique 3D layout with two types
of clusters:

- **Finger clusters**: 5-directional keys (center, north, east, south, west)
  plus an optional double-south key. Each hand has 4 finger clusters (pinky,
  ring, middle, index).
- **Thumb clusters**: 6 keys (down, pad, up, nail, knuckle, double-down).
  Each hand has 1 thumb cluster.

Both cluster types are generic containers that can hold any type of value,
making them suitable for storing keycodes, labels, colors, or any other
per-key data.

Example:
    Creating clusters with a default value and overrides::

        from skim.data.keyboard import FingerCluster, ThumbCluster

        # All keys set to empty string, except south_key
        finger = FingerCluster("", south_key="A")

        # Clusters are iterable and unpackable
        center, north, east, south, west, dsouth = finger

    Zipping multiple clusters together::

        from skim.data.keyboard import FingerCluster, zip_clusters

        keycodes = FingerCluster("KC_NO", center_key="KC_A")
        labels = FingerCluster("", center_key="A")

        # Create a cluster where each position contains both values
        combined = zip_clusters(FingerCluster, "KeyData", codes=keycodes, labels=labels)
        # combined.center_key.codes == "KC_A"
        # combined.center_key.labels == "A"
"""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import Field, dataclass, fields, make_dataclass
from typing import Any, ClassVar, Generic, TypeVar, overload

from typing_extensions import Self

T = TypeVar("T")
"""TypeVar for the value type stored in cluster positions."""

U = TypeVar("U")
"""TypeVar for the mapped value type in map operations."""

__all__ = [
    "ClusterT",
    "FingerCluster",
    "ThumbCluster",
    "SplitSide",
    "SvalboardLayout",
    "SvalboardKeymap",
    "zip_clusters",
    "zip_layouts",
]

SVALBOARD_KEY_COUNT = 60
"""Constant value representing how many keys a Svalboard keyboard has."""

SVALBOARD_SIDE_KEY_COUNT = SVALBOARD_KEY_COUNT / 2
"""Constant representing how many keys a single sides of the Svalboard has."""

SVALBOARD_CLUSTER_KEY_COUNT = 6
"""Constant value representing how many keys a single key cluster has."""


class _Unset:
    """Sentinel class for distinguishing 'not provided' from valid values.

    This internal class creates a unique sentinel value that can be distinguished
    from any valid value, including None. It is used in cluster initialization
    to determine whether a field was explicitly provided or should use the
    default value.

    Attributes:
        __slots__: Empty tuple to prevent instance dictionary creation.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        """Return a string representation of the sentinel.

        Returns:
            The string "<UNSET>" for debugging purposes.
        """
        return "<UNSET>"


_UNSET = _Unset()
"""Singleton instance of the _Unset sentinel."""

_BUNDLE_CACHE: dict[tuple[str, tuple[str, ...]], type] = {}
"""Cache for dynamically created bundle dataclasses used in zip operations."""


def _resolve_bundle_class(
    bundle: str | type,
    keys: tuple[str, ...],
) -> type:
    """Resolve or create a bundle dataclass for zipping operations.

    This helper function either returns a user-provided dataclass type or
    creates/caches a dynamic dataclass for bundling values together.

    Args:
        bundle: Either a string name for a dynamically created dataclass,
            or an existing dataclass type to use directly.
        keys: Tuple of attribute names expected in the bundle (must be sorted).
            Used for cache key when creating dynamic classes, and for
            validation when using existing classes.

    Returns:
        A dataclass type suitable for bundling values.

    Raises:
        TypeError: If bundle is a type that's missing required attributes.
    """
    if isinstance(bundle, type):
        # Validate the provided class has all required attributes
        # For dataclasses, check __dataclass_fields__; otherwise fall back to __init__
        if hasattr(bundle, "__dataclass_fields__"):
            available = set(bundle.__dataclass_fields__.keys())
        else:
            # For non-dataclass types, check __init__ parameters
            import inspect

            sig = inspect.signature(bundle.__init__)
            available = set(sig.parameters.keys()) - {"self"}

        missing = set(keys) - available
        if missing:
            raise TypeError(
                f"Bundle class '{bundle.__name__}' is missing required "
                f"attributes: {sorted(missing)}"
            )
        return bundle

    # Create or retrieve cached dynamic dataclass
    cache_key = (bundle, keys)
    if cache_key not in _BUNDLE_CACHE:
        _BUNDLE_CACHE[cache_key] = make_dataclass(
            bundle,
            [(k, Any) for k in keys],
            frozen=True,
            slots=True,
        )
    return _BUNDLE_CACHE[cache_key]


@dataclass(init=False, slots=True, frozen=True)
class _ClusterBase(Generic[T]):
    """Internal base class providing common functionality for cluster types.

    This abstract base class implements the shared behavior for both
    FingerCluster and ThumbCluster, including initialization logic,
    iteration support, and the ability to zip multiple clusters together.

    The class is generic over type T, which represents the type of value
    stored at each key position in the cluster.

    Attributes:
        _fields_cache: Class-level cache mapping concrete subclass types to
            their dataclass field tuples. Populated lazily on first access
            for each subclass.

    Note:
        This class should not be instantiated directly. Use FingerCluster
        or ThumbCluster instead.
    """

    _fields_cache: ClassVar[dict[type, tuple[Field[Any], ...]]] = {}

    @classmethod
    def _get_fields(cls) -> tuple[Field[Any], ...]:
        """Return the dataclass fields for this class, with caching.

        This method lazily populates a class-level cache of dataclass fields
        to avoid repeated calls to the dataclasses.fields() function.

        Returns:
            A tuple of Field objects describing each attribute of the cluster.
        """
        if cls not in _ClusterBase._fields_cache:
            _ClusterBase._fields_cache[cls] = fields(cls)
        return _ClusterBase._fields_cache[cls]

    def __repr__(self) -> str:
        """Return a detailed string representation of the cluster.

        Returns:
            A string in the format "ClassName(field1=value1, field2=value2, ...)"
            showing all field names and their current values.
        """
        cls_name = self.__class__.__name__
        field_strings = [f"{f.name}={getattr(self, f.name)!r}" for f in self._get_fields()]
        return f"{cls_name}({', '.join(field_strings)})"

    def __iter__(self) -> Iterator[T]:
        """Iterate over cluster values in field definition order.

        This enables unpacking syntax like::

            center, north, east, south, west, dsouth = finger_cluster

        Yields:
            The value stored at each key position, in the order the fields
            are defined in the class.
        """
        for f in self._get_fields():
            yield getattr(self, f.name)

    def map(self, fn: Callable[[T], U]) -> "_ClusterBase[U]":
        """Create a new cluster by applying a function to each value.

        This method transforms each value in the cluster using the provided
        function, returning a new cluster of the same type with the
        transformed values.

        Args:
            fn: A callable that takes a value of type T and returns a value
                of type U. Applied to each key position in the cluster.

        Returns:
            A new cluster instance with transformed values. The cluster type
            is preserved (FingerCluster returns FingerCluster, ThumbCluster
            returns ThumbCluster).

        Example:
            Transforming cluster values::

                codes = FingerCluster("KC_NO", center_key="KC_A")
                labels = codes.map(keycode_to_label)

                # Chain multiple transformations
                result = cluster.map(fn1).map(fn2)

                # Use with lambdas
                upper = labels.map(str.upper)
        """
        raise NotImplementedError("Subclasses must implement map")

    @classmethod
    def from_sequence(cls, values: Sequence[T]) -> Self:
        """Create a cluster from a flat sequence of values.

        Constructs a cluster from a linear sequence of values, mapping each
        index to its corresponding field position using the field definition
        order (same as ``__iter__``).

        For FingerCluster, the order is:
        center_key, north_key, east_key, south_key, west_key, double_south_key.

        For ThumbCluster, the order is:
        down_key, pad_key, up_key, nail_key, knuckle_key, double_down_key.

        Note:
            The order chooseng for the cluster is following what the Svalboard
            firmware uses in its keymap code.

        Args:
            values: A sequence of exactly 6 values to populate the cluster.
                Can be a list, tuple, or any object supporting ``len()`` and
                index access.

        Returns:
            A new cluster instance with values distributed across all fields.

        Raises:
            ValueError: If the sequence does not contain exactly 6 values.

        Example:
            Creating clusters from lists::

                finger = FingerCluster.from_sequence(["C", "N", "E", "S", "W", "DS"])
                finger.center_key  # "C"
                finger.south_key  # "S"

                thumb = ThumbCluster.from_sequence(["D", "P", "U", "N", "K", "DD"])
                thumb.down_key  # "D"
                thumb.nail_key  # "N"
        """
        raise NotImplementedError("Subclasses must implement from_sequence")

    def _setup_cluster(self, default: T | _Unset, kwargs: dict[str, Any]) -> None:
        """Initialize cluster fields from keyword arguments and/or a default.

        This internal method handles the two initialization modes:
        1. All fields provided explicitly via kwargs
        2. A default value with optional field overrides

        Uses object.__setattr__ to bypass frozen dataclass restrictions
        during initialization.

        Args:
            default: The default value to use for fields not in kwargs.
                If _UNSET, all fields must be provided in kwargs.
            kwargs: Mapping of field names to their values.

        Raises:
            TypeError: If default is _UNSET and a required field is missing
                from kwargs.
        """
        cls_name = self.__class__.__name__
        for f in self._get_fields():
            val = kwargs.get(f.name, _UNSET)
            if val is _UNSET:
                if default is _UNSET:
                    raise TypeError(
                        f"{cls_name}.__init__() missing required keyword argument: '{f.name}'"
                    )
                object.__setattr__(self, f.name, default)
            else:
                object.__setattr__(self, f.name, val)

    @classmethod
    def from_zipped(
        cls, *, bundle: str | type = "KeyValues", **clusters: "_ClusterBase[Any]"
    ) -> Self:
        """Create a new cluster by zipping values from multiple source clusters.

        This class method combines multiple clusters of the same type into a
        single cluster where each position contains a bundle of values from
        all source clusters. The bundle can be either a dynamically created
        frozen dataclass or a user-provided dataclass type.

        Args:
            bundle: Either a string name for a dynamically created bundle
                dataclass, or an existing dataclass type to use. Defaults
                to "KeyValues".
            **clusters: Keyword arguments mapping names to source clusters.
                All clusters must have the same field structure as the target
                cluster type.

        Returns:
            A new cluster instance where each field contains a bundle object
            with attributes from each source cluster.

        Raises:
            ValueError: If no clusters are provided.
            TypeError: If any cluster has fields that don't match the target
                cluster type, or if a provided bundle class is missing
                required attributes.

        Example:
            Using a dynamic bundle class::

                codes = FingerCluster("KC_NO", center_key="KC_A")
                labels = FingerCluster("", center_key="A")
                combined = FingerCluster.from_zipped(bundle="KeyData", codes=codes, labels=labels)
                combined.center_key.codes  # "KC_A"
                combined.center_key.labels  # "A"

            Using a custom dataclass::

                @dataclass(frozen=True)
                class KeyData:
                    codes: str
                    labels: str


                combined = FingerCluster.from_zipped(bundle=KeyData, codes=codes, labels=labels)
        """
        if not clusters:
            raise ValueError("At least one cluster is required")

        # Validate that all clusters have matching fields
        expected_fields = {f.name for f in cls._get_fields()}
        for name, cluster in clusters.items():
            cluster_fields = {f.name for f in cluster._get_fields()}
            if cluster_fields != expected_fields:
                raise TypeError(
                    f"Cluster '{name}' has fields {cluster_fields}, "
                    f"expected {expected_fields} for {cls.__name__}"
                )

        sorted_keys = tuple(sorted(clusters.keys()))
        bundle_class = _resolve_bundle_class(bundle, sorted_keys)
        field_names = [f.name for f in cls._get_fields()]

        zipped_payload = {
            name: bundle_class(**{k: getattr(c, name) for k, c in clusters.items()})
            for name in field_names
        }

        instance = cls.__new__(cls)
        instance._setup_cluster(_UNSET, zipped_payload)
        return instance


ClusterT = TypeVar("ClusterT", bound=_ClusterBase[Any])
"""TypeVar bound to cluster types for writing generic cluster functions.

This TypeVar is constrained to FingerCluster or ThumbCluster (or any subclass
of _ClusterBase), enabling type-safe generic functions that work with any
cluster type.

Example:
    Writing a generic function that works with any cluster::

        from skim.data.keyboard import ClusterT, FingerCluster, ThumbCluster

        def count_non_empty(cluster: ClusterT) -> int:
            return sum(1 for value in cluster if value)

        finger = FingerCluster("", center_key="A")
        thumb = ThumbCluster("X")

        count_non_empty(finger)  # Works with FingerCluster
        count_non_empty(thumb)   # Works with ThumbCluster
"""


@dataclass(init=False, slots=True, frozen=True)
class FingerCluster(_ClusterBase[T]):
    """A container for values associated with a Svalboard finger cluster.

    Each finger on the Svalboard has a 5-directional key cluster arranged in
    a cross pattern, plus an optional double-south key for chording. The
    physical layout corresponds to pushing the finger in different directions:

    - **center_key**: The home/rest position (pressing straight down)
    - **north_key**: Pushing the finger forward (away from palm)
    - **east_key**: Pushing the finger toward the thumb
    - **south_key**: Pulling the finger backward (toward palm)
    - **west_key**: Pushing the finger away from the thumb
    - **double_south_key**: A secondary south key on certain Svalboard boards

    This class is generic and can store any type of value at each position,
    making it suitable for keycodes, labels, styling information, or any
    other per-key data.

    The class supports two initialization modes:
    1. Explicit: All six fields must be provided as keyword arguments
    2. Default with overrides: A default value fills all positions, with
       optional keyword arguments to override specific positions

    Attributes:
        center_key: Value for the center (home) position.
        north_key: Value for the north (forward) position.
        east_key: Value for the east (thumb-ward) position.
        south_key: Value for the south (backward) position.
        west_key: Value for the west (away from thumb) position.
        double_south_key: Value for the double-south position.

    Example:
        Creating with all explicit values::

            cluster = FingerCluster(
                center_key="A",
                north_key="B",
                east_key="C",
                south_key="D",
                west_key="E",
                double_south_key="F",
            )

        Creating with a default and overrides::

            cluster = FingerCluster("", south_key="Space")
            # center="", north="", east="", south="Space", west="", dsouth=""

        Unpacking values::

            center, north, east, south, west, dsouth = cluster
    """

    center_key: T
    north_key: T
    east_key: T
    south_key: T
    west_key: T
    double_south_key: T

    @overload
    def __init__(
        self,
        *,
        center_key: T,
        north_key: T,
        east_key: T,
        south_key: T,
        west_key: T,
        double_south_key: T,
    ) -> None: ...

    @overload
    def __init__(
        self,
        default: T,
        *,
        center_key: T = ...,
        north_key: T = ...,
        east_key: T = ...,
        south_key: T = ...,
        west_key: T = ...,
        double_south_key: T = ...,
    ) -> None: ...

    def __init__(self, default: T | _Unset = _UNSET, **kwargs: Any) -> None:
        """Initialize the finger cluster.

        Args:
            default: Optional default value for all positions. If provided,
                any position not explicitly set via kwargs will use this value.
                If not provided, all positions must be set via kwargs.
            **kwargs: Key position values. Valid keys are: center_key,
                north_key, east_key, south_key, west_key, double_south_key.

        Raises:
            TypeError: If default is not provided and any required key
                position is missing from kwargs.
        """
        self._setup_cluster(default, kwargs)

    @classmethod
    def from_sequence(cls, values: Sequence[T]) -> "FingerCluster[T]":
        """Create a FingerCluster from a sequence of 6 values.

        See :meth:`_ClusterBase.from_sequence` for full documentation.
        """
        if len(values) != 6:
            raise ValueError(f"Expected exactly 6 values, got {len(values)}")
        field_names = [f.name for f in cls._get_fields()]
        return cls(**dict(zip(field_names, values, strict=True)))

    def map(self, fn: Callable[[T], U]) -> "FingerCluster[U]":
        """Create a new FingerCluster by applying a function to each value.

        See :meth:`_ClusterBase.map` for full documentation.
        """
        return FingerCluster.from_sequence([fn(v) for v in self])


@dataclass(init=False, slots=True, frozen=True)
class ThumbCluster(_ClusterBase[T]):
    """A container for values associated with a Svalboard thumb cluster.

    Each thumb on the Svalboard has a cluster of keys operated by different
    parts of the thumb and in different directions. The physical layout
    corresponds to:

    - **down_key**: Pressing the thumb straight down
    - **pad_key**: Using the thumb pad (fleshy part)
    - **up_key**: Pressing upward with the thumb
    - **nail_key**: Using the thumbnail area
    - **knuckle_key**: Using the thumb knuckle
    - **double_down_key**: A secondary down position activated by exercing
        extra force to the down key

    This class is generic and can store any type of value at each position,
    making it suitable for keycodes, labels, styling information, or any
    other per-key data.

    The class supports two initialization modes:
    1. Explicit: All six fields must be provided as keyword arguments
    2. Default with overrides: A default value fills all positions, with
       optional keyword arguments to override specific positions

    Attributes:
        down_key: Value for the down (pressing) position.
        pad_key: Value for the thumb pad position.
        up_key: Value for the up position.
        nail_key: Value for the thumbnail position.
        knuckle_key: Value for the thumb knuckle position.
        double_down_key: Value for the double-down position.

    Example:
        Creating with all explicit values::

            cluster = ThumbCluster(
                down_key="Space",
                pad_key="Enter",
                up_key="Tab",
                nail_key="Esc",
                knuckle_key="Ctrl",
                double_down_key="",
            )

        Creating with a default and overrides::

            cluster = ThumbCluster("", down_key="Space")
            # down="Space", pad="", up="", nail="", knuckle="", ddown=""

        Unpacking values::

            down, pad, up, nail, knuckle, ddown = cluster
    """

    down_key: T
    pad_key: T
    up_key: T
    nail_key: T
    knuckle_key: T
    double_down_key: T

    @overload
    def __init__(
        self,
        *,
        down_key: T,
        pad_key: T,
        up_key: T,
        nail_key: T,
        knuckle_key: T,
        double_down_key: T,
    ) -> None: ...

    @overload
    def __init__(
        self,
        default: T,
        *,
        down_key: T = ...,
        pad_key: T = ...,
        up_key: T = ...,
        nail_key: T = ...,
        knuckle_key: T = ...,
        double_down_key: T = ...,
    ) -> None: ...

    def __init__(self, default: T | _Unset = _UNSET, **kwargs: Any) -> None:
        """Initialize the thumb cluster.

        Args:
            default: Optional default value for all positions. If provided,
                any position not explicitly set via kwargs will use this value.
                If not provided, all positions must be set via kwargs.
            **kwargs: Key position values. Valid keys are: down_key,
                pad_key, up_key, nail_key, knuckle_key, double_down_key.

        Raises:
            TypeError: If default is not provided and any required key
                position is missing from kwargs.
        """
        self._setup_cluster(default, kwargs)

    @classmethod
    def from_sequence(cls, values: Sequence[T]) -> "ThumbCluster[T]":
        """Create a ThumbCluster from a sequence of 6 values.

        See :meth:`_ClusterBase.from_sequence` for full documentation.
        """
        if len(values) != 6:
            raise ValueError(f"Expected exactly 6 values, got {len(values)}")
        field_names = [f.name for f in cls._get_fields()]
        return cls(**dict(zip(field_names, values, strict=True)))

    def map(self, fn: Callable[[T], U]) -> "ThumbCluster[U]":
        """Create a new ThumbCluster by applying a function to each value.

        See :meth:`_ClusterBase.map` for full documentation.
        """
        return ThumbCluster.from_sequence([fn(v) for v in self])


@dataclass(frozen=True, slots=True)
class SplitSide(Generic[T]):
    """A container representing one side (left or right) of a Svalboard keyboard.

    Each side of the Svalboard consists of four finger clusters (index, middle,
    ring, pinky) and one thumb cluster. This class provides a generic container
    that can hold any type of per-key data for an entire side of the keyboard.

    The class is generic over type T, which represents the type of value stored
    at each key position, allowing it to be used for keycodes, labels, colors,
    or any other per-key data.

    Attributes:
        index: The index finger cluster (6 keys).
        middle: The middle finger cluster (6 keys).
        ring: The ring finger cluster (6 keys).
        pinky: The pinky finger cluster (6 keys).
        thumb: The thumb cluster (6 keys).

    Example:
        Creating a side with string values::

            from skim.data.keyboard import SplitSide, FingerCluster, ThumbCluster

            side = SplitSide(
                index=FingerCluster(""),
                middle=FingerCluster(""),
                ring=FingerCluster(""),
                pinky=FingerCluster(""),
                thumb=ThumbCluster(""),
            )

        Accessing keys by linear index::

            key = side[0]  # First key of index finger (center)
            key = side[24]  # First key of thumb (down)

        Iterating over all clusters::

            for cluster in side:
                print(cluster)
    """

    _FINGER_ORDER: ClassVar[tuple[str, ...]] = ("index", "middle", "ring", "pinky")
    _THUMB_ORDER: ClassVar[tuple[str, ...]] = (
        "down_key",
        "pad_key",
        "up_key",
        "nail_key",
        "knuckle_key",
        "double_down_key",
    )

    _THUMB_FIRST_INDEX = SVALBOARD_CLUSTER_KEY_COUNT * 4

    index: FingerCluster[T]
    middle: FingerCluster[T]
    ring: FingerCluster[T]
    pinky: FingerCluster[T]
    thumb: ThumbCluster[T]

    def __iter__(self) -> Iterator[FingerCluster[T] | ThumbCluster[T]]:
        """Iterate over all clusters in the side.

        Yields clusters in order: index, middle, ring, pinky, thumb.

        Yields:
            Each cluster on this side of the keyboard, starting with finger
            clusters and ending with the thumb cluster.
        """
        yield self.index
        yield self.middle
        yield self.ring
        yield self.pinky
        yield self.thumb

    def __getitem__(self, idx: int) -> T:
        """Access a key value by linear index.

        Provides flat indexing across all 30 keys on this side. Keys 0-23 are
        the finger clusters (6 keys each × 4 fingers), and keys 24-29 are the
        thumb cluster.

        Args:
            idx: Linear index from 0-29. Indices 0-5 are index finger,
                6-11 are middle finger, 12-17 are ring finger, 18-23 are
                pinky finger, and 24-29 are thumb.

        Returns:
            The value stored at the specified key position.

        Raises:
            IndexError: If idx is outside the valid range (0-29).

        Example:
            Accessing individual keys::

                side[0]  # Index finger center key
                side[6]  # Middle finger center key
                side[24]  # Thumb down key
        """
        if 0 <= idx < 24:
            cluster_idx, key_idx = divmod(idx, SVALBOARD_CLUSTER_KEY_COUNT)
            cluster = getattr(self, self._FINGER_ORDER[cluster_idx])
            # noinspection PyProtectedMember
            return getattr(cluster, cluster._get_fields()[key_idx].name)
        if 24 <= idx < 30:
            return getattr(self.thumb, self._THUMB_ORDER[idx - SplitSide._THUMB_FIRST_INDEX])
        raise IndexError(f"Index {idx} out of range for SplitSide (0-29)")

    @property
    def fingers(self) -> tuple[FingerCluster[T], ...]:
        """Return all finger clusters as a tuple.

        Returns:
            A tuple of the four finger clusters in order:
            (index, middle, ring, pinky).
        """
        return self.index, self.middle, self.ring, self.pinky


@dataclass(frozen=True, slots=True)
class SvalboardLayout(Generic[T]):
    """A container representing the complete Svalboard keyboard layout.

    The Svalboard is a split ergonomic keyboard with a unique 3D key arrangement.
    This class provides a container for storing per-key data across the entire
    keyboard, with support for both hierarchical access (side → cluster → key)
    and flat linear indexing.

    The keyboard has 60 total keys:
    - Left side: 24 finger keys (4 clusters × 6 keys) + 6 thumb keys = 30 keys
    - Right side: 24 finger keys (4 clusters × 6 keys) + 6 thumb keys = 30 keys

    The class is generic over type T, which represents the type of value stored
    at each key position.

    Attributes:
        left: The left side of the keyboard (30 keys).
        right: The right side of the keyboard (30 keys).

    Example:
        Creating a layout with string values::

            from skim.data.keyboard import (
                SvalboardLayout,
                SplitSide,
                FingerCluster,
                ThumbCluster,
            )


            def make_side():
                return SplitSide(
                    index=FingerCluster(""),
                    middle=FingerCluster(""),
                    ring=FingerCluster(""),
                    pinky=FingerCluster(""),
                    thumb=ThumbCluster(""),
                )


            layout = SvalboardLayout(left=make_side(), right=make_side())

        Accessing keys by linear index::

            key = layout[0]  # Right index finger center
            key = layout[24]  # Left index finger center
            key = layout[48]  # Right thumb down
            key = layout[54]  # Left thumb down

        Iterating over all keys::

            for key in layout:
                print(key)  # Prints all 60 keys
    """

    _RIGHT_FINGER_CLUSTER_KEYS = range(0, SVALBOARD_CLUSTER_KEY_COUNT * 4)
    _LEFT_FINGER_CLUSTER_KEYS = range(
        _RIGHT_FINGER_CLUSTER_KEYS.stop,
        _RIGHT_FINGER_CLUSTER_KEYS.stop + SVALBOARD_CLUSTER_KEY_COUNT * 4,
    )
    _RIGHT_THUMB_CLUSTER_KEYS = range(
        _LEFT_FINGER_CLUSTER_KEYS.stop, _LEFT_FINGER_CLUSTER_KEYS.stop + SVALBOARD_CLUSTER_KEY_COUNT
    )
    _LEFT_THUMB_CLUSTER_KEYS = range(
        _RIGHT_THUMB_CLUSTER_KEYS.stop, _RIGHT_THUMB_CLUSTER_KEYS.stop + SVALBOARD_CLUSTER_KEY_COUNT
    )

    left: SplitSide[T]
    right: SplitSide[T]

    def __iter__(self) -> Iterator[T]:
        """Iterate over all key values in the layout.

        Yields keys in the standard Svalboard order:
        1. Right hand finger clusters (index → pinky, 24 keys)
        2. Left hand finger clusters (index → pinky, 24 keys)
        3. Right thumb cluster (6 keys)
        4. Left thumb cluster (6 keys)

        This order matches the typical QMK keymap array layout for the Svalboard.

        Yields:
            Each key value in the layout, totaling 60 values.
        """
        for finger in self.right.fingers:
            yield from finger
        for finger in self.left.fingers:
            yield from finger
        yield from self.right.thumb
        yield from self.left.thumb

    def __getitem__(self, idx: int) -> T:
        """Access a key value by linear index.

        Provides flat indexing across all 60 keys in the layout using the
        standard Svalboard key ordering:
        - 0-23: Right hand finger keys
        - 24-47: Left hand finger keys
        - 48-53: Right thumb keys
        - 54-59: Left thumb keys

        Args:
            idx: Linear index from 0-59.

        Returns:
            The value stored at the specified key position.

        Raises:
            IndexError: If idx is outside the valid range (0-59).

        Example:
            Accessing individual keys::

                layout[0]  # Right index finger center
                layout[24]  # Left index finger center
                layout[48]  # Right thumb down
                layout[54]  # Left thumb down
        """
        if idx in SvalboardLayout._RIGHT_FINGER_CLUSTER_KEYS:
            return self.right[idx]
        if idx in SvalboardLayout._LEFT_FINGER_CLUSTER_KEYS:
            return self.left[idx - SvalboardLayout._LEFT_FINGER_CLUSTER_KEYS.start]
        if idx in SvalboardLayout._RIGHT_THUMB_CLUSTER_KEYS:
            # noinspection PyProtectedMember
            return getattr(
                self.right.thumb,
                SplitSide._THUMB_ORDER[idx - SvalboardLayout._RIGHT_THUMB_CLUSTER_KEYS.start],
            )
        if idx in SvalboardLayout._LEFT_THUMB_CLUSTER_KEYS:
            # noinspection PyProtectedMember
            return getattr(
                self.left.thumb,
                SplitSide._THUMB_ORDER[idx - SvalboardLayout._LEFT_THUMB_CLUSTER_KEYS.start],
            )
        raise IndexError(f"Index {idx} out of range for SvalboardLayout (0-59)")

    @classmethod
    def from_sequence(cls, values: Sequence[T]) -> "SvalboardLayout[T]":
        """Create a SvalboardLayout from a flat sequence of 60 values.

        Constructs a complete keyboard layout from a linear sequence of values,
        mapping each index to its corresponding key position using the standard
        Svalboard ordering (same as ``__getitem__`` and ``__iter__``).

        The mapping is:
        - 0-23: Right hand finger keys (index, middle, ring, pinky clusters)
        - 24-47: Left hand finger keys (index, middle, ring, pinky clusters)
        - 48-53: Right thumb keys
        - 54-59: Left thumb keys

        Within each finger cluster, the 6 keys are ordered:
        center, north, east, south, west, double_south.

        Within each thumb cluster, the 6 keys are ordered:
        down, pad, up, nail, knuckle, double_down.

        Args:
            values: A sequence of exactly 60 values to populate the layout.
                Can be a list, tuple, or any object supporting ``len()`` and
                index access.

        Returns:
            A new SvalboardLayout with values distributed across all key
            positions.

        Raises:
            ValueError: If the sequence does not contain exactly 60 values.

        Example:
            Creating a layout from a list::

                keys = ["KC_A"] * 60  # 60 identical values
                layout = SvalboardLayout.from_sequence(keys)

                # Or with distinct values
                keys = [f"KEY_{i}" for i in range(60)]
                layout = SvalboardLayout.from_sequence(keys)
                layout[0]  # "KEY_0" (right index center)
                layout[59]  # "KEY_59" (left thumb double_down)
        """
        if len(values) != 60:
            raise ValueError(f"Expected exactly 60 values, got {len(values)}")

        def make_side(finger_start: int, thumb_start: int) -> SplitSide[T]:
            return SplitSide(
                index=FingerCluster.from_sequence(values[finger_start : finger_start + 6]),
                middle=FingerCluster.from_sequence(values[finger_start + 6 : finger_start + 12]),
                ring=FingerCluster.from_sequence(values[finger_start + 12 : finger_start + 18]),
                pinky=FingerCluster.from_sequence(values[finger_start + 18 : finger_start + 24]),
                thumb=ThumbCluster.from_sequence(values[thumb_start : thumb_start + 6]),
            )

        return cls(
            right=make_side(finger_start=0, thumb_start=48),
            left=make_side(finger_start=24, thumb_start=54),
        )

    @classmethod
    def from_zipped(
        cls,
        *,
        bundle: str | type = "KeyValues",
        **layouts: "SvalboardLayout[Any]",
    ) -> "SvalboardLayout[Any]":
        """Create a new layout by zipping values from multiple source layouts.

        This class method combines multiple SvalboardLayout instances into a
        single layout where each key position contains a bundle of values from
        all source layouts. The bundle can be either a dynamically created
        frozen dataclass or a user-provided dataclass type.

        This is useful when you need to associate multiple pieces of data with
        each key position, such as pairing keycodes with their display labels,
        or combining styling information from multiple sources.

        Args:
            bundle: Either a string name for a dynamically created bundle
                dataclass, or an existing dataclass type to use. Defaults
                to "KeyValues".
            **layouts: Keyword arguments mapping names to source layouts.
                Each name becomes an attribute on the bundle objects.

        Returns:
            A new SvalboardLayout where each key position contains a frozen
            dataclass instance with attributes from each source layout.

        Raises:
            ValueError: If no layouts are provided.
            TypeError: If a provided bundle class is missing required attributes.

        Example:
            Using a dynamic bundle class::

                codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
                labels = SvalboardLayout.from_sequence(["A"] * 60)

                combined = SvalboardLayout.from_zipped(
                    bundle="KeyData",
                    code=codes,
                    label=labels,
                )

                combined[0].code  # "KC_A"
                combined[0].label  # "A"

            Using a custom dataclass::

                @dataclass(frozen=True)
                class KeyData:
                    code: str
                    label: str


                combined = SvalboardLayout.from_zipped(bundle=KeyData, code=codes, label=labels)
        """
        if not layouts:
            raise ValueError("At least one layout is required")

        sorted_keys = tuple(sorted(layouts.keys()))
        bundle_class = _resolve_bundle_class(bundle, sorted_keys)

        # Zip all 60 positions
        zipped_values = [
            bundle_class(**{name: layout[i] for name, layout in layouts.items()}) for i in range(60)
        ]

        return cls.from_sequence(zipped_values)

    def map(self, fn: Callable[[T], U]) -> "SvalboardLayout[U]":
        """Create a new layout by applying a function to each key value.

        This method transforms each of the 60 key values in the layout using
        the provided function, returning a new SvalboardLayout with the
        transformed values.

        Args:
            fn: A callable that takes a value of type T and returns a value
                of type U. Applied to each key position in the layout.

        Returns:
            A new SvalboardLayout with transformed values.

        Example:
            Transforming layout values::

                codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
                labels = codes.map(keycode_to_label)

                # Chain multiple transformations
                result = layout.map(fn1).map(fn2)

                # Use with lambdas
                upper = labels.map(str.upper)
        """
        return SvalboardLayout.from_sequence([fn(v) for v in self])


@dataclass(frozen=True, slots=True)
class SvalboardKeymap(Generic[T]):
    """A complete Svalboard keymap containing multiple layers.

    A keymap represents the full key configuration for a Svalboard keyboard,
    organized into multiple layers. Each layer is a complete SvalboardLayout
    containing all 60 keys. Users typically switch between layers to access
    different key bindings (e.g., base layer, symbols layer, navigation layer).

    The class is generic over type T, which represents the type of value stored
    at each key position, allowing it to be used for keycodes, labels, colors,
    or any other per-key data.

    Attributes:
        layers: A list of SvalboardLayout objects, one per layer. Layer 0 is
            typically the base/default layer.

    Example:
        Creating a keymap with multiple layers::

            from skim.data.keyboard import SvalboardKeymap, SvalboardLayout

            # Create layouts for each layer
            base_layer = SvalboardLayout.from_sequence(["KC_A"] * 60)
            symbol_layer = SvalboardLayout.from_sequence(["KC_1"] * 60)
            nav_layer = SvalboardLayout.from_sequence(["KC_LEFT"] * 60)

            keymap = SvalboardKeymap(layers=[base_layer, symbol_layer, nav_layer])

        Accessing layers::

            keymap.layers[0]  # Base layer
            keymap.layers[1][0]  # First key of symbol layer
            len(keymap.layers)  # Number of layers
    """

    layers: list[SvalboardLayout[T]]


@overload
def zip_clusters(
    cluster_type: type[ClusterT],
    bundle: str = "KeyValues",
    /,
    **clusters: _ClusterBase[Any],
) -> ClusterT: ...


@overload
def zip_clusters(
    cluster_type: type[ClusterT],
    bundle: type,
    /,
    **clusters: _ClusterBase[Any],
) -> ClusterT: ...


def zip_clusters(
    cluster_type: type[ClusterT],
    bundle: str | type = "KeyValues",
    /,
    **clusters: _ClusterBase[Any],
) -> ClusterT:
    """Zip multiple clusters into a single cluster of bundled values.

    This function combines multiple clusters of the same category (all
    FingerCluster or all ThumbCluster) into a new cluster where each
    position contains a bundle object holding values from all source
    clusters.

    This is useful when you need to associate multiple pieces of data
    with each key position, such as pairing keycodes with their display
    labels, or combining styling information from multiple sources.

    Args:
        cluster_type: The type of cluster to create (FingerCluster or
            ThumbCluster). This also determines the expected field
            structure for all source clusters.
        bundle: Either a string name for a dynamically created bundle
            dataclass, or an existing dataclass type to use. Defaults
            to "KeyValues".
        **clusters: Keyword arguments mapping names to source clusters.
            Each name becomes an attribute on the bundle objects. All
            clusters must have the same field structure as cluster_type.

    Returns:
        A new cluster of the specified type where each field contains a
        frozen dataclass instance with attributes from each source cluster.

    Raises:
        ValueError: If no clusters are provided.
        TypeError: If any source cluster has fields that don't match the
            target cluster type, or if a provided bundle class is missing
            required attributes.

    Example:
        Using a dynamic bundle class::

            from skim.data.keyboard import FingerCluster, zip_clusters

            keycodes = FingerCluster("KC_NO", center_key="KC_A", south_key="KC_SPC")
            labels = FingerCluster("", center_key="A", south_key="Space")
            colors = FingerCluster("#888", center_key="#F00", south_key="#0F0")

            combined = zip_clusters(
                FingerCluster, "KeyData", code=keycodes, label=labels, color=colors
            )

            # Access bundled values
            combined.center_key.code  # "KC_A"
            combined.center_key.label  # "A"
            combined.center_key.color  # "#F00"

        Using a custom dataclass::

            @dataclass(frozen=True)
            class KeyData:
                code: str
                label: str
                color: str


            combined = zip_clusters(
                FingerCluster, KeyData, code=keycodes, label=labels, color=colors
            )
    """
    if not clusters:
        raise ValueError("At least one cluster required")
    return cluster_type.from_zipped(bundle=bundle, **clusters)


@overload
def zip_layouts(
    bundle: str = "KeyValues",
    /,
    **layouts: "SvalboardLayout[Any]",
) -> "SvalboardLayout[Any]": ...


@overload
def zip_layouts(
    bundle: type,
    /,
    **layouts: "SvalboardLayout[Any]",
) -> "SvalboardLayout[Any]": ...


def zip_layouts(
    bundle: str | type = "KeyValues",
    /,
    **layouts: "SvalboardLayout[Any]",
) -> "SvalboardLayout[Any]":
    """Zip multiple layouts into a single layout of bundled values.

    This function combines multiple SvalboardLayout instances into a new layout
    where each key position contains a bundle object holding values from all
    source layouts.

    This is useful when you need to associate multiple pieces of data with
    each key position, such as pairing keycodes with their display labels,
    or combining styling information from multiple sources.

    Args:
        bundle: Either a string name for a dynamically created bundle
            dataclass, or an existing dataclass type to use. Defaults
            to "KeyValues".
        **layouts: Keyword arguments mapping names to source layouts.
            Each name becomes an attribute on the bundle objects.

    Returns:
        A new SvalboardLayout where each key position contains a frozen
        dataclass instance with attributes from each source layout.

    Raises:
        ValueError: If no layouts are provided.
        TypeError: If a provided bundle class is missing required attributes.

    Example:
        Using a dynamic bundle class::

            from skim.data.keyboard import SvalboardLayout, zip_layouts

            codes = SvalboardLayout.from_sequence(["KC_A"] * 60)
            labels = SvalboardLayout.from_sequence(["A"] * 60)
            colors = SvalboardLayout.from_sequence(["#F00"] * 60)

            combined = zip_layouts("KeyData", code=codes, label=labels, color=colors)

            # Access bundled values
            combined[0].code  # "KC_A"
            combined[0].label  # "A"
            combined[0].color  # "#F00"

        Using a custom dataclass::

            @dataclass(frozen=True)
            class KeyData:
                code: str
                label: str
                color: str


            combined = zip_layouts(KeyData, code=codes, label=labels, color=colors)
    """
    if not layouts:
        raise ValueError("At least one layout required")
    return SvalboardLayout.from_zipped(bundle=bundle, **layouts)

# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Utility functions for the skim domain layer.

This module provides general-purpose utility functions used throughout
the domain layer of the skim application.

Example:
    ```pycon
    >>> from skim.domain.utils import clip
    >>> clip(15, 0, 10)
    10
    >>> clip(-5, 0, 10)
    0
    >>> clip(5, 0, 10)
    5

    ```
"""


def clip(n: int | float, min_val: int | float, max_val: int | float) -> int | float:
    """Constrain a numeric value to a specified range.

    Clamps the input value to ensure it falls within the inclusive range
    [min_val, max_val]. Values below min_val are raised to min_val, and
    values above max_val are lowered to max_val.

    Args:
        n: The value to constrain.
        min_val: The minimum allowed value (inclusive).
        max_val: The maximum allowed value (inclusive).

    Returns:
        The clamped value. If n < min_val, returns min_val. If n > max_val,
        returns max_val. Otherwise, returns n unchanged. The return type
        matches the most precise input type (float if any input is float).

    Example:
        ```pycon
        >>> clip(5, 0, 10)
        5
        >>> clip(-5, 0, 10)
        0
        >>> clip(15, 0, 10)
        10
        >>> clip(0.5, 0, 1)
        0.5
        >>> clip(1.5, 0.0, 1.0)
        1.0

        ```
    """
    return max(min_val, min(n, max_val))

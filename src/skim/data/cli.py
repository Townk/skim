# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Data transfer objects for CLI argument handling.

This module defines frozen dataclasses used to pass parsed CLI arguments
between the command-line interface and the application layer. These DTOs
provide type-safe, immutable containers for input/output file specifications
and layer selection options.

Example:
    >>> from skim.data import InputFiles, OutputFiles, KeymapGeneratorTargets
    >>> from pathlib import Path

    >>> inputs = InputFiles(config=Path("config.yaml"), keymap=Path("keymap.kbi"))
    >>> outputs = OutputFiles(output_dir=Path("./images"), output_format="png")
    >>> targets = KeymapGeneratorTargets.from_args(("1", "3-5", "overview"))
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RenderEngine(Enum):
    """Available render engines for non-vector image generation.

    Attributes:
        CHROMIUM: Use Playwright with Chromium browser for rendering.
        CAIRO: Use Cairo graphics library for rendering.
    """

    CHROMIUM = "chromium"
    CAIRO = "cairo"


@dataclass(frozen=True, slots=True)
class OutputFiles:
    """Configuration for output file generation.

    Specifies where and how to write generated keymap images. This is a
    frozen dataclass, meaning instances are immutable after creation.

    Attributes:
        output_dir: Directory path where generated images will be written.
            The directory will be created if it doesn't exist. Defaults to
            the current working directory.
        output_format: Image format for output files. Supported values are
            "svg", "png", "jpeg", "webp", and "avif". Defaults to "svg".
        force_overwrite: Whether to overwrite existing files without
            prompting for confirmation. Defaults to False.
        use_system_fonts: Whether to use system fonts instead of embedding
            fonts in SVG. Defaults to False.
        render_engine: Which render engine to use for non-vector formats.
            Options are CHROMIUM (Playwright) or CAIRO. If None, uses the
            first available engine. Defaults to None.

    Example:
        >>> output = OutputFiles(
        ...     output_dir=Path("./images"),
        ...     output_format="png",
        ...     force_overwrite=True,
        ... )
        >>> output.output_format
        'png'
    """

    output_dir: Path = field(default_factory=Path)
    output_format: str = "svg"
    force_overwrite: bool = False
    use_system_fonts: bool = False
    render_engine: RenderEngine | None = None


@dataclass(frozen=True, slots=True)
class InputFiles:
    """Configuration for input file sources.

    Specifies the source files for keymap data and optional configuration.
    This is a frozen dataclass, meaning instances are immutable after creation.

    Attributes:
        config: Optional path to a YAML configuration file. When provided,
            settings from this file override the default configuration.
            Defaults to None (use default configuration).
        keymap: Optional path to the keymap file (.kbi, .vil, or .json).
            When None, keymap data is read from stdin. Defaults to None.
        force_stdin_keymap: Whether to read keymap data from stdin instead
            of a file. When True, the keymap is ignored and stdin is used.
            Defaults to False.

    Example:
        >>> # Read keymap from file with custom config
        >>> inputs = InputFiles(
        ...     config=Path("my-config.yaml"),
        ...     keymap=Path("my-keymap.kbi"),
        ... )

        >>> # Read keymap from stdin
        >>> inputs = InputFiles(force_stdin_keymap=True)
    """

    config: Path | None = None
    keymap: Path | None = None
    force_stdin_keymap: bool = False


@dataclass(frozen=True, slots=True)
class KeymapGeneratorTargets:
    """Specification of which layers and views to generate.

    Defines the target outputs for keymap generation, including which
    individual layers to render and whether to generate an overview image.
    This is a frozen dataclass, meaning instances are immutable after creation.

    Attributes:
        all_layers: Whether to generate images for all layers in the keymap.
            When True, selected_layers is ignored. Defaults to False.
        overview: Whether to generate an overview image showing all layers
            in a grid layout. Defaults to False.
        selected_layers: List of specific layer indices to generate. Only
            used when all_layers is False. Layer indices are 1-based in
            CLI input but stored as 0-based internally. Defaults to an
            empty list.

    Example:
        >>> # Generate specific layers and overview
        >>> targets = KeymapGeneratorTargets(
        ...     overview=True,
        ...     selected_layers=[0, 2, 4],
        ... )
        >>> targets.overview
        True

        >>> # Generate all layers
        >>> targets = KeymapGeneratorTargets(all_layers=True, overview=True)
    """

    all_layers: bool = False
    overview: bool = False
    macros: bool = False
    tap_dances: bool = False
    special_keys: bool = False
    selected_layers: list[int] = field(default_factory=list)

    @classmethod
    def from_args(
        cls, layer: tuple[str, ...], logger: Callable[[str], None] = print
    ) -> "KeymapGeneratorTargets":
        """Parse CLI layer arguments into a KeymapGeneratorTargets instance.

        Interprets various layer selection formats from command-line arguments
        and constructs the appropriate targets configuration. Supports ranges,
        comma-separated values, and special keywords.

        Args:
            layer: Tuple of layer specification strings from the CLI. Each
                string can be:

                - A single number: "1", "3" (generates that layer)
                - A range: "1-3" (generates layers 1, 2, and 3)
                - Comma-separated: "1,3,5" (generates layers 1, 3, and 5)
                - "overview": Generates only the overview image
                - "all-layers": Generates all individual layers
                - "all": Generates all layers plus overview (default behavior)

            logger: Callable for warning messages about invalid input.
                Defaults to print. Called with a string message when
                invalid layer specifications are encountered.

        Returns:
            A KeymapGeneratorTargets instance configured according to the
            parsed arguments.

        Example:
            >>> # No arguments = all layers + overview
            >>> targets = KeymapGeneratorTargets.from_args(())
            >>> targets.all_layers
            True
            >>> targets.overview
            True

            >>> # Specific layers
            >>> targets = KeymapGeneratorTargets.from_args(("1", "3-5"))
            >>> targets.selected_layers
            [1, 3, 4, 5]

            >>> # Keywords
            >>> targets = KeymapGeneratorTargets.from_args(("overview",))
            >>> targets.overview
            True
            >>> targets.all_layers
            False
        """
        if not layer:
            return KeymapGeneratorTargets(all_layers=True, overview=True, selected_layers=[])

        tokens = [token.strip() for item in layer for token in item.split(",")]

        all_layers = False
        overview = False
        macros = False
        tap_dances = False
        special_keys = False
        selected_layers: list[int] = []

        for token in tokens:
            if not token:
                continue

            match token:
                case "all":
                    # Skip the combined ``special-keys`` image: the
                    # macros and tap-dances images already show the
                    # same content individually, so generating both
                    # would be redundant. Users who want the combined
                    # layout can still opt in via ``-l special-keys``.
                    return KeymapGeneratorTargets(
                        all_layers=True,
                        overview=True,
                        macros=True,
                        tap_dances=True,
                        special_keys=False,
                        selected_layers=[],
                    )
                case "all-layers":
                    all_layers = True
                    selected_layers.clear()
                case "overview":
                    overview = True
                case "macros":
                    macros = True
                case "tap-dances":
                    tap_dances = True
                case "special-keys":
                    special_keys = True
                case _ if "-" in token:
                    try:
                        start_str, end_str = token.split("-")
                        start, end = int(start_str), int(end_str) + 1
                        selected_layers.extend(range(start, end))
                    except ValueError:
                        logger(f"Skipping invalid layer range: {token} ...")
                case _:
                    if all_layers:
                        continue

                    try:
                        selected_layers.append(int(token))
                    except ValueError:
                        logger(f"Skipping invalid layer selection: {token} ...")

        return cls(
            all_layers=all_layers,
            overview=overview,
            macros=macros,
            tap_dances=tap_dances,
            special_keys=special_keys,
            selected_layers=selected_layers,
        )

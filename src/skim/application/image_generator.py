"""Image Generator Service for keyboard layout visualization.

This module provides the :class:`ImageGenerator` which orchestrates the complete
pipeline for generating keymap visualization images. It coordinates parsing,
transformation, and compilation to produce SVG or PNG output files.

The generation pipeline consists of:
    1. Load and merge configuration (user + defaults)
    2. Parse keymap file (c2json, Vial, or Keybard format)
    3. Transform keycodes to display labels
    4. Build layer color gradients and toggle matrices
    5. Compile Typst templates to output images

Example:
    Basic usage from CLI::

        generator = ImageGenerator(
            config_path=Path("config.yaml"),
            output_dir=Path("./output"),
            format="svg",
        )
        generator.generate(keymap_path=Path("keymap.kbi"))

    Generating specific layers::

        generator.generate(
            keymap_path=Path("keymap.vil"),
            layers=["1", "2", "overview"],
        )
"""

import json
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

from skim.application.keycode_loader import KeycodeMappingLoader
from skim.application.keycode_transformer import KeycodeTransformer
from skim.application.parsers.c2json_parser import C2JsonParser
from skim.application.parsers.keybard_parser import KeybardParser
from skim.application.parsers.vial_parser import VialParser
from skim.application.typst_compiler import TypstCompiler
from skim.domain.colors import generate_gradient
from skim.domain.config import SkimConfig
from skim.domain.models import KeymapData, Layer

logger = logging.getLogger(__name__)


def batched(input_list: list[Any], chunk_size: int) -> Generator[list[Any], None, None]:
    """Yield successive fixed-size chunks from input_list.

    A utility generator for splitting lists into equal-sized batches.
    Used for converting flat keycode lists into the 10x6 matrix format
    required by Layer objects.

    Args:
        input_list: The list to split into chunks.
        chunk_size: The size of each chunk.

    Yields:
        List slices of chunk_size elements.

    Example:
        >>> list(batched([1, 2, 3, 4, 5, 6], 2))
        [[1, 2], [3, 4], [5, 6]]
    """
    for i in range(0, len(input_list), chunk_size):
        yield input_list[i : i + chunk_size]


class ImageGenerator:
    """Orchestrates the generation of keymap visualization images.

    This is the main service class that coordinates all components of the
    skim image generation pipeline. It handles configuration loading,
    keymap parsing, keycode transformation, and Typst compilation.

    The generator supports multiple input formats (c2json, Vial, Keybard)
    and can produce both individual layer images and overview images
    showing all layers together.

    Attributes:
        _config_path: Path to user configuration file, or None for defaults.
        _output_dir: Directory where generated images will be saved.
        _format: Output format, either "svg" or "png".
        _assets_path: Path to bundled asset files (templates, fonts).

    Example:
        >>> generator = ImageGenerator(
        ...     config_path=None,  # Use defaults
        ...     output_dir=Path("./images"),
        ...     format="svg",
        ... )
        >>> generator.generate(keymap_path=Path("my-keymap.kbi"))
        # Creates ./images/keymap-1.svg, ./images/keymap-2.svg, etc.
    """

    def __init__(
        self,
        config_path: Path | None,
        output_dir: Path,
        format: str,
    ) -> None:
        """Initialize the image generator.

        Args:
            config_path: Path to user configuration YAML file. If None,
                bundled default configuration will be used.
            output_dir: Directory path where output images will be written.
                Will be created if it doesn't exist.
            format: Output image format. Must be "svg" or "png".

        Example:
            >>> generator = ImageGenerator(
            ...     config_path=Path("skim-config.yaml"),
            ...     output_dir=Path("./output"),
            ...     format="png",
            ... )
        """
        self._config_path = config_path
        self._output_dir = output_dir
        self._format = format
        self._assets_path = Path(__file__).parent.parent / "assets"

    def generate(
        self,
        keymap_path: Path | None = None,
        keymap_content: str | None = None,
        layers: list[str] | None = None,
    ) -> None:
        """Generate keymap visualization images.

        Main entry point for the generation pipeline. Accepts keymap data
        either as a file path or raw content string, parses it, and generates
        the requested layer images.

        The generation process:
            1. Load configuration (user config merged with defaults)
            2. Parse keymap content and detect format
            3. Setup keycode transformer with mappings
            4. Build Layer objects with labels, colors, and toggles
            5. Compile Typst templates to output images

        Args:
            keymap_path: Path to keymap file (.kbi, .vil, or .json).
                Either this or keymap_content must be provided.
            keymap_content: Raw JSON string content of keymap.
                Used when reading from stdin or other sources.
            layers: Optional list of layer specifiers to generate.
                Supported values:
                - "all" or "all-layers": Generate all individual layers
                - "overview": Generate overview image with all layers
                - "N": Generate layer N (1-indexed)
                - "N-M": Generate layers N through M (inclusive, 1-indexed)
                If None, generates all layers plus overview.

        Raises:
            ValueError: If no keymap is provided, or if the keymap
                format cannot be detected or is unsupported.
            FileNotFoundError: If keymap_path doesn't exist.

        Example:
            >>> # Generate all layers from file
            >>> generator.generate(keymap_path=Path("layout.kbi"))

            >>> # Generate specific layers from content
            >>> generator.generate(
            ...     keymap_content=json_string,
            ...     layers=["1", "2", "overview"],
            ... )
        """
        logger.info("Loading configuration...", extra={"emoji": "⚙️ "})
        if self._config_path:
            import yaml

            with open(self._config_path) as f:
                user_data = yaml.safe_load(f)

            user_config = SkimConfig.from_dict(user_data)
            config = user_config.merge_with_defaults()
            logger.info(
                f"Loaded configuration from {self._config_path}", extra={"emoji": "⚙️ "}
            )
        else:
            config = SkimConfig.load_default()
            logger.info("Loaded default configuration", extra={"emoji": "⚙️ "})

        logger.debug(f"Config layers: {len(config.layers)}")

        if not config.appearance:
            raise ValueError("Configuration missing appearance settings")

        logger.info("Reading and parsing keymap...", extra={"emoji": "🗺️ "})
        if keymap_path:
            content = keymap_path.read_text()
            fmt = self._detect_format_from_path(keymap_path)
            logger.debug(f"Detected format from path {keymap_path}: {fmt}")
        elif keymap_content:
            content = keymap_content
            fmt = self._detect_format(content)
            logger.debug(f"Detected format from content: {fmt}")
        else:
            raise ValueError("No keymap provided")

        logger.info(f"Keymap format: {fmt}", extra={"emoji": "🔍"})

        if fmt == "c2json":
            raw_layers = C2JsonParser().parse(content)
        elif fmt == "vial":
            raw_layers = VialParser().parse(content)
        elif fmt == "keybard":
            raw_layers = KeybardParser().parse(content)
        else:
            raise ValueError(f"Unknown keymap format: {fmt}")

        logger.info(f"Parsed {len(raw_layers)} layers.", extra={"emoji": "🗺️ "})

        logger.debug("Setting up keycode transformer...")
        loader = KeycodeMappingLoader()
        mappings = loader.load_bundled()

        if config.keycodes:
            mappings["keycodes"].update(config.keycodes)

        if config.reversed_alias:
            mappings["reversed_alias"].update(config.reversed_alias)

        transformer = KeycodeTransformer(
            mappings["keycodes"],
            mappings["reversed_alias"],
            mappings["modifiers"],
            mappings["layer_symbols"],
        )

        layer_id_to_index = {}
        if config.layers:
            for idx, l_conf in enumerate(config.layers):
                if l_conf.id:
                    layer_id_to_index[l_conf.id] = idx

        logger.info("Processing layers...", extra={"emoji": "🏗️ "})
        processed_layers = []
        for i, raw_keycodes in enumerate(raw_layers):
            logger.debug(f"Processing layer {i}...")
            labels = transformer.transform_list(raw_keycodes)

            toggles_flat = []
            for kc in raw_keycodes:
                target_id = None
                if config.layer_keycode and kc in config.layer_keycode:
                    entry = config.layer_keycode[kc]
                    if isinstance(entry, dict) and "target" in entry:
                        target_id = str(entry["target"])

                if target_id is None:
                    target_id = transformer.extract_layer_id(kc)

                if target_id is None:
                    toggles_flat.append(None)
                    continue

                try:
                    target_idx = int(target_id)
                    toggles_flat.append(target_idx)
                except ValueError:
                    layer = config.layers[target_id]
                    if layer.is_valid():
                        toggles_flat.append(layer.index)
                    else:
                        toggles_flat.append(None)

            toggles_matrix = list(batched(toggles_flat, 6))

            if config.layers:
                layer_config = config.layers[i % len(config.layers)]
                base_color = layer_config.base_color
                layer_name = layer_config.name or f"Layer {i}"
            else:
                base_color = "#cccccc"
                layer_name = f"Layer {i}"

            if (
                not base_color.startswith("#")
                and config.appearance
                and config.appearance.colors.named_colors
                and base_color in config.appearance.colors.named_colors
            ):
                base_color = config.appearance.colors.named_colors[base_color]

            gradient = generate_gradient(base_color, 2)
            colors = gradient + [config.appearance.colors.neutral]

            processed_layers.append(
                Layer(
                    name=layer_name,
                    labels=list(batched(labels, 6)),
                    colors=colors,
                    primary_color=2,
                    secondary_color=6,
                    layer_toggles=toggles_matrix,
                )
            )

        keymap_data = KeymapData(layers=processed_layers)

        selected_layer_indices: list[int] = []
        gen_overview = False
        include_all = False
        all_indices = list(range(len(processed_layers)))

        if not layers:
            selected_layer_indices = all_indices
            gen_overview = True
        else:
            target_set = set()
            for layer_spec in layers:
                if layer_spec in ["all", "all-layers"]:
                    include_all = True
                elif layer_spec == "overview":
                    gen_overview = True
                elif layer_spec == "all":
                    pass
                else:
                    parts = layer_spec.split(",")
                    for p in parts:
                        if "-" in p:
                            start, end = map(int, p.split("-"))
                            target_set.update(range(start - 1, end))
                        else:
                            target_set.add(int(p) - 1)

            if include_all:
                selected_layer_indices = all_indices
            elif target_set:
                selected_layer_indices = sorted(
                    [i for i in target_set if 0 <= i < len(processed_layers)]
                )

        logger.info("Preparing compilation...", extra={"emoji": "🔨"})
        compiler = TypstCompiler()
        typst_assets = self._assets_path / "typst"

        keymap_dict = keymap_data.to_dict()
        keymap_dict["selectedLayers"] = selected_layer_indices

        sys_inputs = {
            "keymap": json.dumps(keymap_dict),
            "appearance": json.dumps(config.appearance.to_dict()),
        }

        if logger.isEnabledFor(logging.DEBUG):
            debug_view = {}
            for k, v in sys_inputs.items():
                try:
                    debug_view[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    debug_view[k] = v
            logger.debug(f"Sys Inputs:\n{json.dumps(debug_view, indent=2)}")

        self._output_dir.mkdir(parents=True, exist_ok=True)

        if selected_layer_indices:
            logger.info(
                f"Compiling {len(selected_layer_indices)} layer images...",
                extra={"emoji": "🖼️ "},
            )
            compiler.compile(
                input_path=typst_assets / "keymap-layers.typ",
                output_path=self._output_dir / f"keymap-{{p}}.{self._format}",
                sys_inputs=sys_inputs,
                font_paths=[typst_assets / "fonts"],
            )

            if not include_all and layers:
                logger.debug(
                    "Cleaning up unwanted layer files...", extra={"emoji": "🧹"}
                )
                for i in range(len(processed_layers)):
                    page_num = i + 1
                    file_path = self._output_dir / f"keymap-{page_num}.{self._format}"
                    if i not in selected_layer_indices and file_path.exists():
                        file_path.unlink()
                        logger.debug(f"Deleted {file_path}")

        if gen_overview:
            logger.info("Compiling overview image...", extra={"emoji": "📊"})
            compiler.compile(
                input_path=typst_assets / "keymap-overview.typ",
                output_path=self._output_dir / f"keymap-overview.{self._format}",
                sys_inputs=sys_inputs,
                font_paths=[typst_assets / "fonts"],
            )

        logger.info(
            f"Generation complete. Output directory: {self._output_dir}",
            extra={"emoji": "✨"},
        )

    def _detect_format_from_path(self, path: Path) -> str:
        """Detect keymap format from file extension and content.

        Examines the file extension first, then falls back to content
        analysis for ambiguous cases like .json files.

        Args:
            path: Path to the keymap file.

        Returns:
            Format string: "c2json", "vial", or "keybard".

        Raises:
            ValueError: If format cannot be determined.
        """
        if path.suffix == ".json":
            return self._detect_format(path.read_text())
        elif path.suffix == ".vil":
            return "vial"
        elif path.suffix == ".kbi":
            return "keybard"
        return self._detect_format(path.read_text())

    def _detect_format(self, content: str) -> str:
        """Detect keymap format from JSON content structure.

        Analyzes the JSON structure to identify which keymap format
        the content represents.

        Detection rules:
            - Has "layout" + "version" → Vial format
            - Has "keymap" as list → Keybard format
            - Has "layers" as list → c2json format

        Args:
            content: JSON string to analyze.

        Returns:
            Format string: "c2json", "vial", or "keybard".

        Raises:
            ValueError: If JSON is invalid or format is unrecognized.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON content") from e

        if "layout" in data and "version" in data:
            return "vial"
        elif "keymap" in data and isinstance(data["keymap"], list):
            return "keybard"
        elif "layers" in data and isinstance(data["layers"], list):
            return "c2json"

        raise ValueError("Unknown keymap format")

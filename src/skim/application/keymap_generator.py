# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Main orchestration module for keymap image generation.

This module provides the primary entry point for generating Svalboard keymap
visualization images. It coordinates the loading of configuration and keymap
files, transformation of keycodes to display labels, rendering of SVG
drawings, and export to image files.

The generation pipeline follows these steps:
1. Load configuration (with gradient generation for layer colors)
2. Load keymap from file or stdin
3. Transform keycodes to renderable target keys
4. Draw SVG images for requested layers
5. Export drawings to output directory

Example:
    >>> from pathlib import Path
    >>> from skim.data.cli import InputFiles, OutputFiles, KeymapGeneratorTargets
    >>> from skim.application.keymap_generator import generate_keymap
    >>> inputs = InputFiles(keymap=Path("keymap.kbi"))
    >>> outputs = OutputFiles(output_dir=Path("./images"), output_format="png")
    >>> targets = KeymapGeneratorTargets(all_layers=True, overview=True)
    >>> generate_keymap(inputs, outputs, targets)
"""

import logging
from pathlib import Path

from skim.data import InputFiles, KeymapGeneratorTargets, OutputFiles, SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey
from skim.domain.adapters import KeycodeLabelAdapter, KeymapTargetAdapter

from .exporter import save_drawings
from .loaders import load_keycode_mappings, load_keymap, load_skim_config
from .render import draw_keymap, make_gradient

logger = logging.getLogger(__name__)
"""Module-level logger for keymap generation operations."""


def _derive_default_config_from_keymap(keymap_path: Path) -> SkimConfig:
    """Build a SkimConfig from a keymap file using the configurator's defaults.

    Mirrors what ``skim configure -k <keymap>`` produces in memory so the
    ``generate`` command behaves consistently when invoked without an explicit
    ``--config``.
    """
    import yaml

    from skim.application.config_generator import ConfigGenerator

    yaml_str = ConfigGenerator().generate_from_keymap(keymap_path.read_text(encoding="utf-8"))
    return SkimConfig.model_validate(yaml.safe_load(yaml_str))


def _get_config(
    config_path: Path | None,
    use_system_fonts: bool = False,
    keymap_for_defaults: Path | None = None,
    show_special_keys_legend: bool = True,
) -> SkimConfig:
    """Load and enhance configuration with generated gradients.

    Loads the skim configuration from the specified file (or uses defaults)
    and generates color gradients for any layer colors that don't have
    explicit gradient definitions.

    Args:
        config_path: Path to the configuration YAML file, or None to use
            default configuration.
        use_system_fonts: Whether to use system fonts instead of embedding
            fonts in the SVG output.
        keymap_for_defaults: When ``config_path`` is None, the keymap file used
            to derive default ``keyboard.layers`` and ``palette.layers`` so the
            generator behaves like the configurator does for an unconfigured
            keymap. Ignored when ``config_path`` is provided.

    Returns:
        A SkimConfig instance with all layer colors having gradient tuples
        populated.
    """
    config: SkimConfig
    if config_path is None and keymap_for_defaults is not None and keymap_for_defaults.is_file():
        config = _derive_default_config_from_keymap(keymap_for_defaults)
    else:
        config = load_skim_config(config_path)

    new_layers = tuple(
        layer.model_copy(update={"gradient": make_gradient(layer.base_color, layer.color_index)})
        if layer.gradient is None
        else layer
        for layer in config.output.style.palette.layers
    )

    new_palette = config.output.style.palette.model_copy(update={"layers": new_layers})
    new_style = config.output.style.model_copy(
        update={
            "palette": new_palette,
            "use_system_fonts": use_system_fonts,
            "show_special_keys_legend": show_special_keys_legend,
        }
    )
    new_output = config.output.model_copy(update={"style": new_style})
    return config.model_copy(update={"output": new_output})


def _get_input_keymap(inputs: InputFiles, config: SkimConfig) -> SvalboardKeymap[str]:
    """Load the raw keymap from the specified input source.

    Args:
        inputs: Input file configuration specifying the keymap source
            (file path or stdin).
        config: The skim configuration containing layer index mappings.

    Returns:
        A SvalboardKeymap containing raw keycode strings for all layers.
    """
    layer_indices = [layer.index for layer in config.keyboard.layers] or None
    return load_keymap(
        None if inputs.force_stdin_keymap else inputs.keymap,
        layer_indices=layer_indices,
    )


def _resolve_keymap(
    config: SkimConfig, input_keymap: SvalboardKeymap[str]
) -> SvalboardKeymap[SvalboardTargetKey]:
    """Transform raw keycodes to renderable target keys.

    Applies keycode-to-label transformation using the configured mappings
    and extracts layer-switching metadata for each key.

    Args:
        config: The skim configuration containing keycode mappings.
        input_keymap: A keymap containing raw QMK keycode strings.

    Returns:
        A keymap containing SvalboardTargetKey objects with display labels
        and layer metadata.
    """
    mappings = load_keycode_mappings(config.keycodes)
    label_adapter: KeycodeLabelAdapter = KeycodeLabelAdapter(config.keyboard, mappings)
    keymap_adapter = KeymapTargetAdapter(
        label_adapter,
        fallthrough_to_layer_zero=config.output.style.show_transparent_fallthrough,
    )

    keymap: SvalboardKeymap[SvalboardTargetKey] = keymap_adapter.transform(input_keymap)
    return keymap


def generate_keymap(
    inputs: InputFiles,
    outputs: OutputFiles,
    targets: KeymapGeneratorTargets,
    show_special_keys_legend: bool = True,
) -> None:
    """Generate keymap visualization images.

    Main entry point for the keymap generation pipeline. Loads configuration
    and keymap data, transforms keycodes to display labels, renders SVG
    drawings, and exports them to the specified output directory.

    Args:
        inputs: Configuration for input files (keymap path, config path,
            stdin flag).
        outputs: Configuration for output (directory, format, overwrite flag).
        targets: Specification of which layers and views to generate.

    Raises:
        SystemExit: If the output directory path exists but is not a directory.

    Note:
        The output directory is created if it doesn't exist. Existing files
        may be overwritten depending on the outputs.force_overwrite setting.
    """
    if not outputs.output_dir.is_dir():
        logger.error(f"The specified output directory is not a directory: {outputs.output_dir}")
        exit(1)

    if not outputs.output_dir.exists():
        outputs.output_dir.mkdir()

    keymap_for_defaults = None if inputs.force_stdin_keymap else inputs.keymap
    config: SkimConfig = _get_config(
        inputs.config,
        outputs.use_system_fonts,
        keymap_for_defaults=keymap_for_defaults,
        show_special_keys_legend=show_special_keys_legend,
    )
    input_keymap = _get_input_keymap(inputs, config)
    keymap = _resolve_keymap(config, input_keymap)
    drawings = draw_keymap(config, keymap, targets)
    save_drawings(outputs, drawings, outputs.render_engine)

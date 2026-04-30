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
import re
from pathlib import Path

from skim.data import InputFiles, KeymapGeneratorTargets, OutputFiles, SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey
from skim.domain.adapters import KeycodeLabelAdapter, KeymapTargetAdapter

from .exporter import save_drawings
from .loaders import load_keycode_mappings, load_keymap, load_skim_config
from .render import draw_keymap, make_gradient
from .render.styling import adjust_color

logger = logging.getLogger(__name__)
"""Module-level logger for keymap generation operations."""


def _derive_title_from_filename(keymap_path: Path) -> str:
    """Build a human-readable overview title from a keymap filename.

    ``vial-sample.vil`` → ``"Vial Sample Layers Layout"``.
    """
    stem = re.sub(r"[-_]+", " ", keymap_path.stem).strip()
    return f"{stem.title()} Layers Layout" if stem else "Layers Layout"


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
    show_symbol_legend: bool = True,
    symbol_legend_flow: str | None = None,
    title_override: str | None = None,
    copyright_override: str | None = None,
    double_south_override: bool = False,
    adjust_lightness: float | None = None,
    adjust_saturation: float | None = None,
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
        symbol_legend_flow: Override for the symbol legend flow direction
            (``"row"`` or ``"column"``).  ``None`` means use the config value.

    Returns:
        A SkimConfig instance with all layer colors having gradient tuples
        populated.
    """
    from skim.data import SymbolLegendFlow

    config: SkimConfig
    if config_path is None and keymap_for_defaults is not None and keymap_for_defaults.is_file():
        config = _derive_default_config_from_keymap(keymap_for_defaults)
    else:
        config = load_skim_config(config_path)

    apply_color_adjust = config_path is None and (
        adjust_lightness is not None or adjust_saturation is not None
    )

    def _maybe_adjust(color: str) -> str:
        if not apply_color_adjust:
            return color
        return adjust_color(color, adjust_lightness, adjust_saturation)

    new_layers = tuple(
        layer.model_copy(
            update={
                "base_color": _maybe_adjust(layer.base_color),
                "gradient": make_gradient(_maybe_adjust(layer.base_color), layer.color_index),
            }
        )
        if layer.gradient is None or apply_color_adjust
        else layer
        for layer in config.output.style.palette.layers
    )

    style_updates: dict = {
        "palette": config.output.style.palette.model_copy(update={"layers": new_layers}),
        "use_system_fonts": use_system_fonts,
        "show_special_keys_legend": show_special_keys_legend,
        "show_symbol_legend": show_symbol_legend,
    }
    if symbol_legend_flow is not None:
        style_updates["symbol_legend_flow"] = SymbolLegendFlow(symbol_legend_flow)

    new_style = config.output.style.model_copy(update=style_updates)

    output_updates: dict = {"style": new_style}
    if title_override is not None:
        output_updates["keymap_title"] = title_override
    elif config.output.keymap_title is None and keymap_for_defaults is not None:
        # No explicit title (config or CLI) — fall back to the keymap filename
        # so the overview reads better than the generic "Layer 0 Layers Layout".
        output_updates["keymap_title"] = _derive_title_from_filename(keymap_for_defaults)

    new_output = config.output.model_copy(update=output_updates)

    if copyright_override is not None:
        new_output = new_output.model_copy(update={"copyright": copyright_override})

    keyboard_updates: dict = {}
    if double_south_override:
        new_features = config.keyboard.features.model_copy(update={"double_south": True})
        keyboard_updates["features"] = new_features

    config_updates: dict = {"output": new_output}
    if keyboard_updates:
        config_updates["keyboard"] = config.keyboard.model_copy(update=keyboard_updates)
    return config.model_copy(update=config_updates)


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
    show_symbol_legend: bool = True,
    symbol_legend_flow: str | None = None,
    title: str | None = None,
    copyright_text: str | None = None,
    double_south: bool = False,
    adjust_lightness: float | None = None,
    adjust_saturation: float | None = None,
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
        show_symbol_legend=show_symbol_legend,
        symbol_legend_flow=symbol_legend_flow,
        title_override=title,
        copyright_override=copyright_text,
        double_south_override=double_south,
        adjust_lightness=adjust_lightness,
        adjust_saturation=adjust_saturation,
    )
    input_keymap = _get_input_keymap(inputs, config)
    keymap = _resolve_keymap(config, input_keymap)
    keycode_mappings = load_keycode_mappings(config.keycodes)
    drawings = draw_keymap(
        config,
        keymap,
        targets,
        raw_keymap=input_keymap,
        keycode_mappings=keycode_mappings,
    )
    save_drawings(outputs, drawings, outputs.render_engine)

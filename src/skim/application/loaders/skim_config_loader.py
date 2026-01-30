# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Loader for skim configuration files.

This module provides a function for loading skim configuration from
YAML files. If no configuration file is specified or the file doesn't
exist, a default configuration is returned.

Example:
    >>> from pathlib import Path
    >>> from skim.application.loaders.skim_config_loader import load_skim_config
    >>> config = load_skim_config(Path("my-config.yaml"))
    >>> config.output.layout.width
    800
"""

from pathlib import Path

import yaml

from skim.data import SkimConfig


def load_skim_config(config_path: Path | None = None) -> SkimConfig:
    """Load skim configuration from a YAML file.

    Loads and validates configuration from the specified YAML file. If no
    path is provided or the path doesn't point to an existing file, returns
    a default SkimConfig with all default values.

    Args:
        config_path: Optional path to a YAML configuration file. If None
            or if the file doesn't exist, returns default configuration.

    Returns:
        A validated SkimConfig instance, either loaded from the file or
        with default values.

    Raises:
        pydantic.ValidationError: If the YAML content doesn't match the
            expected configuration schema.
        yaml.YAMLError: If the file content is not valid YAML.

    Example:
        >>> # Load from file
        >>> config = load_skim_config(Path("custom-config.yaml"))

        >>> # Get default config
        >>> config = load_skim_config()
        >>> config.output.layout.width
        800
    """
    path = config_path or Path("")
    if path.is_file():
        return SkimConfig.model_validate(
            yaml.safe_load(path.read_text()), strict=True, extra="forbid"
        )
    return SkimConfig()

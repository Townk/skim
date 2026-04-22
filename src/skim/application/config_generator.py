# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Configuration generator for creating skim config YAML files.

Provides :class:`ConfigGenerator` which can produce default configuration
templates or extract metadata from Keybard (.kbi) files to generate
pre-populated configuration files.

Example:
    Generate default config::

        generator = ConfigGenerator()
        print(generator.generate_default())

    Generate from Keybard file::

        generator = ConfigGenerator()
        yaml_config = generator.generate_from_keybard(
            Path("layout.kbi").read_text(),
            adjust_lightness=0.31,
        )
        Path("skim-config.yaml").write_text(yaml_config)
"""

import yaml

from skim.data.config import SkimConfig


class ConfigGenerator:
    """Generates skim configuration YAML from defaults or source files."""

    def generate_default(self) -> str:
        """Generate YAML from SkimConfig defaults.

        Returns:
            YAML string containing the default skim configuration.
        """
        config = SkimConfig()
        data = config.model_dump(mode="json")
        return yaml.dump(data, sort_keys=False, default_flow_style=False)

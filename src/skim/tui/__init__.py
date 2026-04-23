# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""TUI package for interactive skim configuration editing."""

from pathlib import Path
from typing import Any


def launch_tui(
    config_data: dict[str, Any],
    output_path: Path | None = None,
    config_path: Path | None = None,
    force: bool = False,
) -> None:
    """Launch the interactive configuration editor.

    Args:
        config_data: Config dict (from SkimConfig.model_dump(mode="json")).
        output_path: File path to save config to (from -o flag).
        config_path: File path the config was loaded from (from -c flag).
        force: Skip overwrite confirmation.
    """
    from skim.tui.app import SkimConfigApp

    app = SkimConfigApp(
        config_data=config_data,
        output_path=output_path,
        config_path=config_path,
        force=force,
    )
    app.run()

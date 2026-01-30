# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Application layer package for skim.

This package contains the core application logic (use cases), including:
- Keymap generation orchestration
- Configuration generation
- Exporters and loaders
- Rendering pipeline components
"""

from .keymap_generator import generate_keymap
from .logging_config import setup_logging

__all__ = [
    "generate_keymap",
    "setup_logging",
]

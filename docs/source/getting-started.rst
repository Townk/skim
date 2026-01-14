Getting Started
===============

This guide will help you install skim and generate your first keyboard layout
images.

Requirements
------------

- Python 3.10 or higher
- A keymap file from Keybard (``.kbi``), Vial (``.vil``), or QMK c2json (``.json``)

Installation
------------

Using pip
^^^^^^^^^

.. code-block:: bash

   pip install skim

Using uv (recommended)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   uv tool install skim

From source
^^^^^^^^^^^

.. code-block:: bash

   git clone https://github.com/Townk/skim.git
   cd skim
   uv sync
   uv run skim --version

Verify Installation
-------------------

After installation, verify skim is working:

.. code-block:: bash

   skim --version

You should see output like:

.. code-block:: text

   Svalboard Keymap Image Maker (skim), version 0.4.0

Quick Start
-----------

Generate Images from a Keymap File
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The most common use case is generating images from a keymap file:

.. code-block:: bash

   skim generate --keymap my-layout.kbi --output-dir ./images

This will:

1. Parse your keymap file
2. Generate an SVG image for each layer
3. Generate an overview image showing all layers
4. Save all images to the ``./images`` directory

Specify Output Format
^^^^^^^^^^^^^^^^^^^^^

By default, skim generates SVG files. For PNG output:

.. code-block:: bash

   skim generate -k my-layout.kbi -o ./images -f png

Generate Specific Layers
^^^^^^^^^^^^^^^^^^^^^^^^

If you only need certain layers:

.. code-block:: bash

   # Only the overview image
   skim generate -k my-layout.kbi -l overview

   # Only layer 1 (1-indexed)
   skim generate -k my-layout.kbi -l 1

   # Layers 1, 2, and 3
   skim generate -k my-layout.kbi -l 1-3

   # Multiple specific layers
   skim generate -k my-layout.kbi -l 1 -l 4 -l 7

Generate a Default Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To customize layer colors and names, start with a default configuration:

.. code-block:: bash

   skim configure -o skim-config.yaml

Then use it when generating images:

.. code-block:: bash

   skim generate -k my-layout.kbi -c skim-config.yaml -o ./images

Extract Configuration from Keybard
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you use Keybard, skim can extract layer colors and custom keycodes
directly from your ``.kbi`` file:

.. code-block:: bash

   skim configure -k my-layout.kbi -o skim-config.yaml

Command Reference
-----------------

skim
^^^^

The main command group. Common options:

.. code-block:: text

   --version          Show version and exit
   -v, --verbosity    Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL, NONE)
   -q, --quiet        Silence all output

skim generate
^^^^^^^^^^^^^

Generate keymap visualization images.

.. code-block:: text

   -k, --keymap PATH      Keymap file (.kbi, .vil, .json)
   -c, --config PATH      Configuration file (YAML)
   -o, --output-dir PATH  Output directory (default: current directory)
   -f, --format FORMAT    Output format: svg (default) or png
   -l, --layer LAYER      Layer selection (can be repeated)

Layer selection options:

- ``overview`` - Generate only the overview image
- ``all`` or ``all-layers`` - Generate all individual layers
- ``N`` - Generate layer N (1-indexed)
- ``N-M`` - Generate layers N through M

skim configure
^^^^^^^^^^^^^^

Generate or output configuration files.

.. code-block:: text

   -k, --keybard-keymap PATH   Extract config from Keybard file
   -o, --output PATH           Output file path
   -f, --force                 Overwrite existing file
   -C, --qmk-color-header PATH Import colors from QMK color.h
   -l, --adjust-lightness N    Adjust color lightness (0.0-1.0)
   -s, --adjust-saturation N   Adjust color saturation (0.0-1.0)

Reading from Stdin
------------------

skim can read keymap data from stdin, useful for scripting:

.. code-block:: bash

   cat my-layout.kbi | skim generate - -o ./images

   # Or directly from a c2json output
   qmk c2json \
      -kb svalboard/trackball/pmw3389/right \
      -km MyKeymap \
      --no-cpp \
      ./keyboards/svalboard/keymaps/MyKeymap/keymap.c | skim generate -o ./images -

   # Or with curl
   curl -s https://example.com/layout.json | skim generate - -o ./images

Next Steps
----------

- :doc:`configuration` - Customize colors, layer names, and appearance
- :doc:`api/index` - API documentation for developers

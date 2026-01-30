Getting Started
===============

Installation
------------

Skim is a Python tool that can be installed using various package managers. We recommend using ``uv`` or ``pipx`` to install it in an isolated environment.

Using uv (Recommended)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    uv tool install qmk-skim

Using pipx
^^^^^^^^^^

.. code-block:: bash

    pipx install qmk-skim

Using pip
^^^^^^^^^

.. code-block:: bash

    pip install qmk-skim

System Dependencies
-------------------

Skim generates SVG images by default, which requires no external dependencies. However, if you want to generate raster images (PNG, JPEG, WEBP, AVIF), you need to install additional software.

Chromium (Playwright)
^^^^^^^^^^^^^^^^^^^^^

To use the Chromium render engine (recommended for best quality):

1. Install the package with the ``playwright`` extra (if using pip):

   .. code-block:: bash

       pip install "qmk-skim[playwright]"

2. Install the browser binaries:

   .. code-block:: bash

       playwright install chromium

Cairo
^^^^^

To use the Cairo render engine:

- **macOS:** Install ``cairo`` via Homebrew:

  .. code-block:: bash

      brew install cairo

- **Linux (Debian/Ubuntu):** Install ``libcairo2``:

  .. code-block:: bash

      sudo apt-get install libcairo2

- **Windows:** GTK+ runtime is required (instructions vary).

Quick Start
-----------

1. **Generate a default configuration:**

   .. code-block:: bash

       skim configure --output skim-config.yaml

2. **Generate images from a keymap:**

   .. code-block:: bash

       skim generate --keymap my-keymap.json --config skim-config.yaml

   This will generate SVG images for all layers in the current directory.

3. **Explore options:**

   .. code-block:: bash

       skim generate --help
Introduction
============

**skim** (Svalboard Keymap Image Maker) is a command-line tool that generates
beautiful, publication-ready images of your keyboard layouts. It takes keymap
configuration files from popular keyboard firmware tools and produces SVG or
PNG images that you can use for documentation, reference cards, or sharing
your layouts with the community.

What is skim?
-------------

If you use a Svalboard split keyboard with QMK firmware, you've probably wanted
to visualize your keymap layout. Maybe you want to:

- Create a quick reference card to keep nearby while learning a new layout
- Document your configuration for others to learn from
- Share your layout on forums, Reddit, or Discord
- Generate images for a blog post or keyboard guide

.. container:: keymap-hero

   .. image:: _static/keymap-1.svg
      :alt: Example Keymap Layer
      :align: center
      :width: 80%

**skim** automates this process by reading your keymap files directly and
generating consistent, professional-looking images.

Supported Formats
-----------------

skim can read keymap files from three popular sources:

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Format
     - Extension
     - Description
   * - **Keybard**
     - ``.kbi``
     - Keybard's native export format (JSON)
   * - **Vial**
     - ``.vil``
     - Vial's layout format (JSON)
   * - **QMK c2json**
     - ``.json``
     - QMK's ``qmk c2json`` output format

Use Cases
---------

Personal Reference Cards
^^^^^^^^^^^^^^^^^^^^^^^^

Generate images of your keyboard layers to print or keep on your desktop.
This is especially helpful when learning a new layout or switching between
different layer configurations.

.. code-block:: bash

   skim generate -k my-layout.kbi -o ~/Desktop/keymap-reference/

Documentation
^^^^^^^^^^^^^

If you maintain a keyboard configuration repository or write about keyboards,
skim can generate consistent images for all your documentation needs.

.. code-block:: bash

   skim generate -k layout.vil -f png -o ./docs/images/

Sharing Layouts
^^^^^^^^^^^^^^^

Generate overview images showing all your layers at once, perfect for sharing
on social media or keyboard forums.

.. code-block:: bash

   skim generate -k layout.kbi -l overview -o ./

Selective Layer Export
^^^^^^^^^^^^^^^^^^^^^^

Only need specific layers? skim can generate just the layers you want.

.. code-block:: bash

   # Generate only layer 1
   skim generate -k layout.kbi -l 1

   # Generate layers 1 through 3
   skim generate -k layout.kbi -l 1-3

   # Generate specific layers
   skim generate -k layout.kbi -l 1 -l 3 -l 5

Key Features
------------

- **Multiple input formats**: Supports Keybard, Vial, and QMK c2json files
- **Flexible output**: Generate SVG (scalable) or PNG (raster) images
- **Layer selection**: Generate all layers, specific layers, or overview images
- **Customizable appearance**: Configure colors, borders, and layer names
- **QMK color import**: Import named colors from your QMK ``color.h`` file
- **Stdin support**: Pipe keymap data directly for scripting workflows

Next Steps
----------

- :doc:`getting-started` - Install skim and generate your first images
- :doc:`configuration` - Customize colors, layer names, and appearance

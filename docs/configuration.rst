Configuration
=============

Skim is highly configurable, allowing you to customize everything from layout
dimensions and spacing to colors and keycode display.

Configuration File
------------------

The configuration is defined in a YAML file. You can generate a default configuration file using the `configure` command:

.. code-block:: bash

    skim configure --output skim-config.yaml

Structure
---------

The configuration file is organized into three main sections:

- ``keyboard``: Hardware features and layer definitions.
- ``keycodes``: Custom keycode transformations and overrides.
- ``output``: Visual styling and layout dimensions.

Keyboard Section
^^^^^^^^^^^^^^^^

This section defines the physical properties of the keyboard and the layers in your keymap.

.. code-block:: yaml

    keyboard:
      features:
        double_south: false  # Enable/disable double-south keys
      layers:
        - label: "1"
          name: "Base Layer"
          id: "base"         # Optional ID for layer lookup
        - label: "2"
          name: "Symbols"

Keycodes Section
^^^^^^^^^^^^^^^^

This section allows you to customize how keycodes are displayed. You can transform keycodes before processing or override their final display label.

.. code-block:: yaml

    keycodes:
      pre_process:
        - keycode: "LCTL_T(KC_A)"
          target: "MT(MOD_LCTL,KC_A)"
      overrides:
        - keycode: "KC_SPC"
          target: "Space"
        - keycode: "KC_ENT"
          target: "Enter"

Output Section
^^^^^^^^^^^^^^

This section controls the visual appearance of the generated images.

.. code-block:: yaml

    output:
      layout:
        width: 800
        spacing:
          margin: 0
          inset: 20
      style:
        use_layer_colors_on_keys: true
        hold_symbol_position: "outward"  # "inward", "outward", or "qmk"
        border:
          width: 2
          radius: 10
        palette:
          background_color: "white"
          text_color: "black"
          key_label_color: "white"
          neutral_color: "#6F768B"
          layers:
            - base_color: "#3366CC"  # Simple color
            - base_color: "#CC6633"
              gradient:              # Custom gradient (6 colors)
                - "#CC6633"
                - "#AA5522"
                - "#884411"
                - "#663300"
                - "#442200"
                - "#221100"

Render Engines
--------------

For generating non-vector images (PNG, JPEG, WEBP, AVIF), Skim requires a render engine. Two options are supported:

1. **Chromium (Playwright):** Uses a headless browser to render the SVG and capture a screenshot. This usually produces the most accurate results but requires installing Playwright browsers.
2. **Cairo:** Uses the Cairo graphics library. This is faster and lighter but requires system dependencies (libcairo) to be installed.

You can specify the render engine using the ``--render-engine`` flag or let Skim choose the first available one.

.. code-block:: bash

    # Use Chromium
    skim generate --keymap my.kbi --format png --render-engine chromium

    # Use Cairo
    skim generate --keymap my.kbi --format png --render-engine cairo

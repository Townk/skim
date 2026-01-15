Configuration
=============

skim uses YAML configuration files to customize the appearance of generated
images. This page explains all available configuration options.

Generating a Configuration File
-------------------------------

Start with a default configuration:

.. code-block:: bash

   skim configure -o skim-config.yaml

Or extract configuration from a Keybard file:

.. code-block:: bash

   skim configure -k my-layout.kbi -o skim-config.yaml

Configuration File Format
-------------------------

Here's a complete configuration file with all options:

.. code-block:: yaml

   layers:
     - id: _BASE
       name: "Base Layer"
       label: "BASE"
       base_color: "#347156"
     - id: _NAV
       name: "Navigation"
       label: "NAV"
       base_color: "#89511C"

   layer_keycode:
     CKC_NAV:
       target: _NAV
       type: "MO"
     CUSTOM_NUM:
       target: 2
       type: "TG"

   keycodes:
     CKC_BSPC: "%%nf-md-brain; @@KC_BACKSPACE;"
     MKC_COPY: "@@KC_LEFT_CTRL; C"

   reversed_alias:
     "LSFT(KC_TAB)": "@@MKC_BKTAB;"

   appearance:
     colors:
       text: "#000000"
       background: "#FFFFFF"
       neutral: "#70768B"
       named_colors:
         CORAL: "#763c27"
         TEAL: "#277676"
     border:
       color: "#000000"
       radius: 20

Configuration Sections
----------------------

layers
^^^^^^

Defines configuration for each layer in the keymap. Layers are matched by
index (0-based internally, 1-based in output).

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Option
     - Type
     - Description
   * - ``id``
     - string
     - Identifier used in the keymap instead of a layer number when
       activating a layer. Useful for QMK Userspace keymaps with ``#define``
       statements representing layer numbers (e.g., ``_BASE``, ``_NAV``).
   * - ``name``
     - string
     - Display name shown in the generated keymap image header.
   * - ``label``
     - string
     - Short label used on layer activation keys instead of the layer number.
       If not provided, the 1-indexed layer number is used.
   * - ``base_color``
     - string
     - Base color for generating a gradient representing key clusters.
       Can be a hex code (``#347156``) or a named color from
       ``appearance.colors.named_colors``.

Example:

.. code-block:: yaml

   layers:
     - id: _BASE
       name: "COLEMAK"
       label: "BASE"
       base_color: "#347156"
     - id: _NAV
       name: "Navigation"
       label: "NAV"
       base_color: "#89511C"
     - id: _NUM
       name: "Numbers"
       label: "NUM"
       base_color: "#41687E"
     - id: "6"
       name: "Unused"
       label: "-"
       base_color: "PINK"    # Uses named color

If ``name`` is not provided, skim uses "Layer N" where N is the layer number.

layer_keycode
^^^^^^^^^^^^^

Maps custom keycodes to layer activation behavior. This is essential for
QMK Userspace keymaps with custom keys that activate layers, or for
``#define`` macros that translate to layer activation functions.

Each entry maps a keycode name to an object with:

.. list-table::
   :header-rows: 1
   :widths: 15 15 70

   * - Option
     - Type
     - Description
   * - ``target``
     - string/int
     - The layer number (int) or layer ID (string) activated by this key.
   * - ``type``
     - string
     - Layer activation function type. One of: ``DF``, ``PDF``, ``MO``,
       ``LM``, ``LT``, ``OSL``, ``TG``, ``TO``, or ``TT``.

Layer activation types:

- ``MO`` - Momentary: layer active while key is held
- ``TG`` - Toggle: toggles layer on/off
- ``TO`` - Turn on: switches to layer, turns off other layers
- ``DF`` - Default: sets the default layer
- ``OSL`` - One-shot layer: layer active for one keypress
- ``LT`` - Layer-tap: tap for keycode, hold for layer
- ``TT`` - Tap-toggle: tap to toggle, hold for momentary

Example:

.. code-block:: yaml

   layer_keycode:
     CKC_BSPC:
       target: 1           # Layer number
       type: "MO"
     CKC_SPC:
       target: _NUM        # Layer ID (matches layers[].id)
       type: "MO"
     CKC_TAB:
       target: 3
       type: "MO"
     TOGGLE_SYS:
       target: _SYS
       type: "TG"

keycodes
^^^^^^^^

Custom keycode display mappings. Use this to provide human-readable labels
for custom keycodes in your firmware.

Values can be:

- Plain strings: ``"Copy"``
- Special references (must end with ``;``):

  - ``@@KEYCODE;`` - Reference another keycode (resolved recursively)
  - ``%%icon;`` - NerdFont icon (use the icon "Class" name from nerdfonts.com)

You can combine multiple references in one label.

Example:

.. code-block:: yaml

   keycodes:
     # Plain text label
     MY_MACRO: "Custom"

     # Reference to another keycode
     CKC_SPC: "@@KC_SPACE;"

     # NerdFont icon + keycode reference
     CKC_BSPC: "%%nf-md-brain; @@KC_BACKSPACE;"

     # Multiple keycode references (for key combos)
     MKC_COPY: "@@KC_LEFT_CTRL; C"
     MKC_APPWIN: "@@KC_LEFT_CTRL; @@KC_LEFT_GUI; @@KC_DOWN;"

     # Pure icon
     MKC_SHDKT: "%%nf-md-monitor;"

     # Keybard aliases pointing to custom keys
     USER20: "@@CKC_BSPC;"
     USER21: "@@CKC_SPC;"

reversed_alias
^^^^^^^^^^^^^^

Maps complex keycode expressions back to simpler labels. Useful when your
keymap uses modifier functions like ``LSFT(KC_TAB)`` that you want to
display with a custom label.

Example:

.. code-block:: yaml

   reversed_alias:
     "LSFT(KC_TAB)": "@@MKC_BKTAB;"
     "LCTL(KC_C)": "Copy"

appearance
^^^^^^^^^^

Controls the visual appearance of generated images.

appearance.colors
"""""""""""""""""

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Option
     - Type
     - Description
   * - ``text``
     - string
     - Color for all non-key text in the image (hex code).
   * - ``background``
     - string
     - Image background color. Set to ``null`` for transparent background.
   * - ``neutral``
     - string
     - Color for neutral/inactive elements like some thumb keys (hex code).
   * - ``named_colors``
     - object
     - Map of color names to hex values. These can be referenced by name
       in ``layers[].base_color``.

Example:

.. code-block:: yaml

   appearance:
     colors:
       text: "#1b1b1b"
       background: "#FFFFFF"    # Use null for transparent
       neutral: "#70768B"
       named_colors:
         AZURE: "#276e76"
         CORAL: "#763c27"
         TEAL: "#277676"
         PINK: "#76274e"
         GOLD: "#766a27"

Named colors are case-insensitive and can be used in layer configurations:

.. code-block:: yaml

   layers:
     - name: "Layer 1"
       base_color: "CORAL"    # References named_colors.CORAL

appearance.border
"""""""""""""""""

Defines the border style for generated images. Omit this section entirely
if you don't want borders.

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Option
     - Type
     - Description
   * - ``color``
     - string
     - Border color (hex code).
   * - ``radius``
     - integer
     - Corner radius for rounded borders. Set to ``0`` for square corners.
       Uses pixel-independent units.

Example:

.. code-block:: yaml

   appearance:
     border:
       color: "#000000"
       radius: 20    # Rounded corners

Importing QMK Colors
--------------------

QMK provides a set of named colors for you to use in your ``keymap.c`` file. If
you want to use the same names in your keymap image, skim can parse the QMK
``color.h`` file (usually located at ``$QMK_FIRMWARE/quantum/color.h``) and
generate the ``named_colors`` entry in the ``appearance`` section of the
configuration for you.

.. code-block:: bash

   skim configure -k layout.kbi -C $QMK_FIRMWARE/quantum/color.h -o skim-config.yaml

This reads HSV color definitions from the QMK ``color.h`` and converts them to
hex codes in the configuration.

Color Adjustments
^^^^^^^^^^^^^^^^^

When importing colors, you can adjust lightness and saturation to ensure
good contrast in generated images:

.. code-block:: bash

   skim configure -k layout.kbi -C color.h \
       --adjust-lightness 0.6 \
       --adjust-saturation 0.8 \
       -o skim-config.yaml

These values are NOT multipliers! They replace the lightness and saturation of
the color ranging from ``0.0`` to ``1.0``.

Importing Information from Keybard
----------------------------------

Similarly to the QMK color names, if you use Keybard to configure your
Svalboard, you can go on the UI and change your layer names and save your
layout to a ``.kbi`` file. After that, you can ask skim to generate a
configuration using this ``.kbi`` file to fill the basic information from your
layers.

When using a ``.kbi`` to generate a configuration, skim will also import custom
keys defined by the firmware, filling also the ``keycodes`` section of the
configuration file.

.. code-block:: bash

   skim configure -k layout.kbi

When importing layer information, you can also use the lightness and saturation
adjustments to change the layer colors.

Using Configuration with Generate
---------------------------------

Pass your configuration file when generating images:

.. code-block:: bash

   skim generate -k layout.kbi -c skim-config.yaml -o ./images

The configuration affects:

- Layer names and labels displayed in images
- Color scheme for each layer
- Key label mappings (including icons)
- Layer activation key indicators
- Overall appearance (borders, background, etc.)

Complete Example
----------------

Here's a comprehensive configuration example:

.. code-block:: yaml

   layers:
     - id: _BASE
       name: "COLEMAK"
       label: "BASE"
       base_color: "#347156"
     - id: _NAV
       name: "Navigation"
       label: "NAV"
       base_color: "#89511C"
     - id: _NUM
       name: "Numbers"
       label: "NUM"
       base_color: "#41687E"
     - id: _SYM
       name: "Symbols"
       label: "SYM"
       base_color: "#8C3B2C"
     - id: _FUN
       name: "Function Keys"
       label: "FN"
       base_color: "#5F4B7E"
     - id: _SYS
       name: "System"
       label: "SYS"
       base_color: "#9C2927"

   layer_keycode:
     CKC_BSPC:
       target: _NAV
       type: "MO"
     CKC_SPC:
       target: _NUM
       type: "MO"
     CKC_TAB:
       target: _SYM
       type: "MO"

   keycodes:
     CKC_BSPC: "%%nf-md-brain; @@KC_BACKSPACE;"
     CKC_SPC: "@@KC_SPACE;"
     CKC_TAB: "@@KC_TAB;"
     MKC_COPY: "@@KC_LEFT_CTRL; C"
     MKC_PASTE: "@@KC_LEFT_CTRL; V"

   reversed_alias:
     "LSFT(KC_TAB)": "%%nf-md-keyboard_tab_reverse;"

   appearance:
     border:
       color: "#000000"
       radius: 20
     colors:
       text: "#1b1b1b"
       background: "#FFFFFF"
       neutral: "#70768B"
       named_colors:
         CORAL: "#763c27"
         TEAL: "#277676"
         PINK: "#76274e"

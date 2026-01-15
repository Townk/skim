## ADDED Requirements

### Requirement: Multi-format Support
The application SHALL support parsing keymaps in Keybard (`.kbi`), Vial (`.vil`), and QMK c2json (`.json`) formats.

#### Scenario: Auto-detection
- **WHEN** a file is loaded
- **THEN** its format is detected and parsed accordingly.

### Requirement: Layout Normalization
The application SHALL normalize the key layout from different formats into a standard internal representation.

#### Scenario: Keybard/Vial reordering
- **WHEN** loading a Keybard or Vial keymap
- **THEN** the keys are reordered to match the official QMK physical layout (as defined by `qmk c2json` output).

### Requirement: Label Resolution
The application SHALL resolve QMK keycodes into display labels using the keycode mapping system.

#### Scenario: Keycode mapping
- **WHEN** a keycode like `KC_A` is encountered
- **THEN** it is resolved to `A` using the loaded `keycode-mapping` definitions.

#### Scenario: Modifier handling
- **WHEN** a complex keycode like `S(KC_A)` is encountered
- **THEN** it is resolved to the corresponding symbol sequence (e.g., `⇧ A`) using the loaded `keycode-mapping` definitions.

### Requirement: NerdFont Support
The application SHALL preserve NerdFont placeholders (e.g., `%%nf-class;`) in labels.

#### Scenario: NerdFont pass-through
- **WHEN** a label contains a NerdFont sequence
- **THEN** it is passed unchanged to the Typst renderer.

### Requirement: Layer Toggles
The application SHALL identify layer toggle keys and generate a `layerToggles` matrix.

#### Scenario: Layer toggle detection
- **WHEN** a keycode activates another layer (e.g., `MO(1)`)
- **THEN** the corresponding entry in `layerToggles` reflects the target layer index.

#### Scenario: Custom layer toggle definition
- **WHEN** the configuration provides a `layer_keycode` mapping (e.g., `CUSTOM_KEY: {target: 2, type: "TG"}`)
- **THEN** matching keycodes in the keymap are treated as layer toggles with the specified behavior (target layer and activation type).

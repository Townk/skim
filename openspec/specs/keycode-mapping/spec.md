# keycode-mapping Specification

## Purpose
TBD - created by archiving change setup-initial-specs. Update Purpose after archive.
## Requirements
### Requirement: Mapping File Structure
The application SHALL support a YAML-based mapping file to define how QMK keycodes are translated into display labels.

#### Scenario: Basic key mapping
- **WHEN** the mapping file defines a keycode (e.g., `KC_A: "A"`)
- **THEN** the parser uses that string literal for the key label.

#### Scenario: Modifier mapping
- **WHEN** the mapping file defines a modifier prefix (e.g., `S: "⇧"`)
- **THEN** the parser resolves the modifier to that symbol and recursively resolves the inner keycode.

#### Scenario: Nested modifier resolution
- **WHEN** a nested modifier sequence like `S(C(KC_A))` is encountered
- **THEN** it is resolved by recursively resolving the modifier keycode (e.g. `S` maps to `KC_LEFT_SHIFT` which maps to `%%nf-md-apple_keyboard_shift;`) and concatenating it with the inner keycode resolution.

#### Scenario: Recursive keycode resolution
- **WHEN** a mapped value contains a keycode reference syntax (e.g., `@@KC_ENTER;`)
- **THEN** the parser resolves the referenced keycode recursively until a terminal string or NerdFont is found.

#### Scenario: Circular resolution error
- **WHEN** a keycode reference loop is detected (e.g., `A` maps to `@@B;` and `B` maps to `@@A;`)
- **THEN** the application halts resolution and reports a circular dependency error.

#### Scenario: Reversed alias
- **WHEN** the mapping file defines a `reversed_alias` map entry (e.g., `"LSFT(KC_1)": "@@KC_EXLM;"`)
- **THEN** the parser checks if the keycode matches any key in `reversed_alias` *before* standard processing. If matched, it resolves the alias and proceed with the standard resolution.

#### Scenario: Layer symbols
- **WHEN** the parser encounters a layer activation keycode (e.g., `MO(1)`, `TG(2)`)
- **THEN** it looks up the function name (e.g., `MO`) in the `layer_symbols` map to find the display symbol (e.g., `%%nf-md-layers_outline;`) and combines it with the layer index.

#### Scenario: NerdFont support
- **WHEN** a mapping value contains a NerdFont placeholder (e.g., `%%nf-fa-home;`)
- **THEN** the parser preserves it for the renderer.

### Requirement: User Overrides
The application SHALL allow users to extend or override the default keycode mappings via configuration.

#### Scenario: Custom keycode definition
- **WHEN** the user provides a custom configuration with `keycodes` definitions
- **THEN** these definitions take precedence over the built-in default mappings.

#### Scenario: Custom reversed alias definition
- **WHEN** the user provides a custom configuration with `reversed_alias` definitions
- **THEN** these definitions are merged with or override the default reversed aliases.

### Requirement: Default Mapping
The application SHALL provide a built-in default mapping covering standard QMK keycodes.

#### Scenario: Fallback behavior
- **WHEN** a custom mapping file is not provided
- **THEN** the application loads the internal default mapping.


## MODIFIED Requirements

### Requirement: Mapping File Structure
The application SHALL support a YAML-based mapping file to define how QMK keycodes are translated into display labels.

#### Scenario: Reversed alias priority
- **WHEN** the transformer receives a keycode for resolution
- **THEN** it MUST first check if the keycode matches any key in `reversed_alias` before attempting any other resolution.
- **AND** if matched, it resolves the alias value and proceeds with standard resolution on the result.

#### Scenario: Basic key mapping
- **WHEN** the mapping file defines a keycode (e.g., `KC_A: "A"`)
- **THEN** the parser uses that string literal for the key label.

#### Scenario: Macro function resolution
- **WHEN** the mapping file defines a macro function (e.g., `S: "@@KC_LEFT_SHIFT; @0;"`)
- **AND** the parser encounters a keycode using that function (e.g., `S(KC_A)`)
- **THEN** it resolves the template by substituting `@0;` with the recursively resolved first argument label.

#### Scenario: Nested macro function resolution
- **WHEN** a nested function sequence like `S(C(KC_A))` is encountered
- **THEN** the inner function is resolved recursively before being substituted into the outer template.

#### Scenario: Layer function resolution
- **WHEN** the parser encounters a layer activation keycode (e.g., `MO(1)`, `TG(2)`)
- **AND** the mapping file defines a macro function for it (e.g., `MO: "%%nf-md-layers_outline; #0;"`)
- **THEN** it resolves the template by substituting `#0;` with the layer number.

#### Scenario: Hold-tap function resolution
- **WHEN** a hold-tap keycode is encountered (e.g., `LT(1, KC_SPC)`)
- **AND** the macro function template contains both layer and keycode placeholders (e.g., `"%%nf-md-layers_outline; #0;|;@1;"`)
- **THEN** the display shows both the hold behavior (layer) and tap behavior (keycode) separated by the separator character.

#### Scenario: Modifier-tap function resolution
- **WHEN** a modifier-tap keycode is encountered (e.g., `LSFT_T(KC_A)`)
- **AND** the macro function template is `"@@KC_LEFT_SHIFT;|;@0;"`
- **THEN** the display shows the hold behavior (modifier), separator, and tap behavior (e.g., "Shift | A").

#### Scenario: Modifier union argument resolution
- **WHEN** a macro function argument is a modifier union (e.g., `MOD_LCTL|MOD_LSFT`)
- **THEN** the argument is resolved by looking up each modifier in the `modifier_union` mapping and concatenating the results.

#### Scenario: Separator resolution
- **WHEN** a macro function template contains a separator placeholder `|;`
- **THEN** the placeholder is replaced with the Unicode box-drawing character `│` (U+2502).

#### Scenario: Recursive keycode resolution
- **WHEN** a mapped value contains a keycode reference syntax (e.g., `@@KC_ENTER;`)
- **THEN** the parser resolves the referenced keycode recursively until a terminal string or NerdFont is found.

#### Scenario: Circular resolution error
- **WHEN** a keycode reference loop is detected (e.g., `A` maps to `@@B;` and `B` maps to `@@A;`)
- **THEN** the application halts resolution and reports a circular dependency error.

#### Scenario: NerdFont support
- **WHEN** a mapping value contains a NerdFont placeholder (e.g., `%%nf-fa-home;`)
- **THEN** the parser preserves it for the renderer.

#### Scenario: Unknown macro function
- **WHEN** a keycode uses a function pattern not defined in `macro_functions`
- **THEN** the keycode is returned as-is without transformation.

# Change: Refactor Keycode Transformation to Support Macro Functions

## Why

The current keycode transformer handles modifiers and layer functions with
separate, hard-coded logic paths. QMK firmware supports hold-tap keys (like
`LT`, `MT`, modifier taps like `LSFT_T`) that behave as one key when held and
another when tapped. These are not currently supported.

The new `macro_functions` and `modifier_union` mappings in
`keycode-mappings.yaml` provide a unified, data-driven approach to resolve all
function-style keycodes through a single resolution pipeline with placeholder
substitution.

## What Changes

- Remove `layer_symbols` mapping section from the transformer (internal only;
  functionality moves to `macro_functions`)
- Remove `modifiers` mapping section from the transformer (internal only;
  functionality moves to `macro_functions`)
- Add `macro_functions` mapping support with placeholder resolution (`#N;`,
  `@N;`, `|;`)
- Add `modifier_union` mapping support for resolving modifier bit arguments
  (e.g., `MOD_LCTL|MOD_LSFT`)
- Refactor `KeycodeTransformer` to use a unified macro function parsing
  pipeline
- Update `KeycodeMappingLoader` to load and merge the new mapping sections

**Note**: This is not a breaking change for users. The `modifiers` and
`layer_symbols` sections were internal implementation details not exposed
through the user configuration schema (`SkimConfig`). Users can only override
`keycodes` and `reversed_alias` in their config files.

## Impact

- Affected specs: `keycode-mapping`
- Affected code:
  - `src/skim/application/keycode_transformer.py` - Major refactor
  - `src/skim/application/keycode_loader.py` - Add new mapping sections
  - `src/skim/application/image_generator.py` - Update transformer instantiation
  - `src/skim/assets/data/keycode-mappings.yaml` - Already updated with new mappings
  - All tests for keycode transformation

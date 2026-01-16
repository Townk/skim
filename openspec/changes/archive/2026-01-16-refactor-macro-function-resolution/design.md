# Design: Macro Function Resolution

## Context

QMK firmware uses macro functions to define keys with complex behaviors. These
include:

- **Modifier functions**: `S(KC_A)` sends Shift+A
- **Layer functions**: `MO(1)` activates layer 1 while held
- **Hold-tap functions**: `LT(1, KC_SPC)` acts as layer 1 when held, Space when
  tapped
- **Modifier-tap functions**: `LSFT_T(KC_A)` acts as Shift when held, A when tapped

The current implementation has separate code paths for modifiers and layer
functions, making it impossible to support hold-tap keys which need both
behaviors displayed.

## Goals / Non-Goals

**Goals:**

- Unified resolution pipeline for all function-style keycodes
- Data-driven configuration via YAML (no code changes needed for new functions)
- Support for hold-tap display with separator (e.g., "Layer 1 | Space")
- Support for modifier union arguments (e.g., `MOD_LCTL|MOD_LSFT`)
- Maintain backward compatibility for existing keycode resolution

**Non-Goals:**

- GUI configuration for macro functions
- Runtime modification of mappings
- Support for arbitrary QMK macros (only documented function patterns)

## Decisions

### Decision 1: Unified Macro Function Pipeline

All function-style keycodes (`FUNC(args)`) will be resolved through a single
`_parse_macro_function` method that:

1. Extracts function name and arguments
2. Looks up the function in `macro_functions` mapping
3. Resolves placeholders in the template string
4. Recursively resolves the result through standard keycode resolution

**Alternatives considered:**

- Keep separate methods for modifiers/layers: Rejected - doesn't scale, can't
  support hold-tap
- Use Python code generation: Rejected - too complex, harder to maintain

### Decision 2: Placeholder Syntax

The YAML already defines three placeholder types:

- `#N;` - Layer argument (resolves layer ID to number)
- `@N;` - Keycode argument (resolves through standard keycode resolution or modifier_union)
- `|;` - Separator character (visual divider between hold/tap behaviors)

These will be resolved in order: layer args, keycode args, separator, then
standard keycode resolution.

**Alternatives considered:**

- Use Python format strings: Rejected - less readable in YAML, mixing concerns
- Use Jinja templates: Rejected - overkill, adds dependency

### Decision 3: Argument Parsing

Function arguments are comma-separated. Arguments can be:

1. Layer IDs (numeric or symbolic like `_NAV`)
2. Standard keycodes (`KC_A`, `KC_SPACE`)
3. Modifier unions (`MOD_LCTL|MOD_LSFT`)
4. Nested macro functions (`S(KC_A)`)

Arguments will be parsed left-to-right, respecting parentheses for nested functions.

### Decision 4: Remove Legacy Mappings

The `modifiers` and `layer_symbols` sections will be removed from the
transformer interface since their functionality is subsumed by
`macro_functions`. The YAML file already has these mappings duplicated in
`macro_functions`.

## Risks / Trade-offs

| Risk | Mitigation |
| ---- | ---------- |
| Complex argument parsing for nested functions | Use recursive parsing with parentheses tracking |
| Performance regression from more complex resolution | Profile; current resolution is already recursive |

**Note on backward compatibility**: The `modifiers` and `layer_symbols` sections
are internal implementation details. Users cannot override these via
`SkimConfig` - only `keycodes` and `reversed_alias` are exposed. Therefore,
removing these from the transformer interface has no impact on existing user
configurations.

## Migration Plan

1. Update `KeycodeMappingLoader` to load new sections
2. Update `KeycodeTransformer` with new resolution logic
3. Update all tests
4. Remove deprecated mapping sections from loader merge logic
5. Update documentation

**Rollback:** Git revert; no data migration needed.

## Resolved Questions

1. **User-defined placeholder types?** No. The placeholders are fixed to the three
   types defined in the spec: `#N;` (layer), `@N;` (keycode), and `|;` (separator).

2. **Configurable separator character?** No. The separator placeholder `|;` always
   resolves to the Unicode box-drawing character `│` (U+2502).

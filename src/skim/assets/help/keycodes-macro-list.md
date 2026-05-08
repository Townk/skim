# Macros

<!-- body -->

A list of macro definitions referenced by `Mn` (or `QK_MACRO_n`, or
`MACRO_n`, where `n` is a number, usually between 1 and 50) keycodes
in the keymap. Each entry has a stable id matching the keycode
reference, an optional human-readable name surfaced by the renderer,
and a read-only preview summarising the macro's actions.

When you bootstrap the config from a keymap file (`skim config -k …`),
existing macro slots from the keymap are pre-populated here.
Manually-added entries start with the preview "Undefined" until the
next bootstrap fills them in.

## Interaction

| Key | Action |
|-----|--------|
| Enter | Edit the selected macro |
| A | Add a new macro |
| D | Delete the selected macro |

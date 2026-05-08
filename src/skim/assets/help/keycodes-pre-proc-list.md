# Pre-process Keycodes

<!-- body -->

A list of keycode pre-processing rules. Each rule maps a custom keycode to a target keycode expression that replaces it before rendering.

Use this to define custom keycodes (like `MKC_BKTAB`) that expand to QMK expressions (like `LSFT(KC_TAB)`) in the rendered keymap.

## Interaction

| Key | Action |
|-----|--------|
| Enter | Edit the selected rule |
| A | Add a new rule |
| D | Delete the selected rule |

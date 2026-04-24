# Pre-process — Target

The replacement expression. This is what SKIM will use to replace any
occurrence of the defined keycode.

This replacement happens before any label parsing, which means that
if you place a QMK keycode expression here (e.g. `LSFT(KC_TAB)`,
`LT(2,KC_SPC)`, etc.), SKIM will replace such expression with the correct key
label later.

The **Preview** field below shows how the resolved label will appear in the
rendered keymap.

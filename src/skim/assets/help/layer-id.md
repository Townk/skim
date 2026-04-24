# Layer ID

Only relevant for keymaps generated with the `c2json` QMK utility.

When rendering keymaps from a standard QMK keymap (when you edited the
`keymap.c` file in the QMK or user space repository), if you created a C macro
to represent your layer (e.g. `#define _BASE 0`), the output of the `c2json`
command will use the macro name instead of the layer index in keycodes like
`LT(_BASE)` or `TO(_BASE)`. For this reason, you need to tell SKIM how to
associate your layers with these macros.

The ID field is where you tell SKIM what is the macro name you used.

Leaving this field empty will make SKIM use only numeric indices to match layers.

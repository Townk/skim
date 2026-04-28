# Macro — ID

The id used to reference this macro from the keymap. For numeric
references like `M5` or `MACRO_5` the id is the matching string
(`"5"`). For named macros (`MACRO_MY_THING`) use the name portion
(`"MY_THING"`).

Each id must be unique within the macro list. Editing the id moves
the binding — the renderer matches macros to keycodes by id.

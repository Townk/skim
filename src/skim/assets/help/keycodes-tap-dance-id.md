# Tap Dance — ID

The id used to reference this tap dance from the keymap. For numeric
references like `TD(0)` the id is the matching string (`"0"`). Named
tap dances (`TD(MY_TD)`) use the name portion.

Each id must be unique within the tap-dance list. Editing the id
moves the binding — the renderer matches tap dances to keycodes by id.

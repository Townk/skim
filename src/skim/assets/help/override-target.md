# Override — Target

The custom label to display for this keycode. Supports three formats:

- **Plain text:** `Escape` — displays the text as-is
- **Keycode reference:** `@@KC_ESC;` — resolves to the label of another keycode
- **NerdFont glyph:** `%%nf-md-keyboard;` — inserts a NerdFont icon

You can combine formats: `%%nf-md-arrow-left; Back`

Type `@@` to trigger keycode autocomplete, or `%%` to trigger NerdFont glyph autocomplete.

# Layers

The list of keyboard layers that SKIM will generate keymap images for.
Each layer must be present in the keymap used to render the images, but not all
layers from the keymap need to be listed here.

If you don't want a layer to be rendered in the overview keymap image, remove
it from this list.

## Interaction

| Key | Action |
| --- | ------ |
| Enter | Edit the selected layer's details |
| A | Add a new layer |
| D | Delete the selected layer |
| M | Enter move mode to reorder layers |

In **move mode**, use Up/Down to reposition, Enter to confirm, Escape to cancel.

Layers are kept sorted by their QMK index. Adding or removing a layer here also
syncs with the layer colors in the Style tab.

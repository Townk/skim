# Show Transparent Fall-through

Only affects keys that use a QMK transparent keycode (`KC_TRANSPARENT`,
`KC_TRNS`, or `_______`) on a non-base layer.

When enabled, transparent keys borrow the label from the **base layer**
(layer 0) and render it in a faded "ghost" color derived from the key's
own background. This makes the fall-through behaviour visible at a glance
without obscuring the layer's own color scheme.

When disabled, transparent keys are rendered blank — the previous skim
behaviour.

The ghost color is the key's fill color with its HSL lightness shifted
by 0.12 — lighter when the key sits at or below the layer's base color
in the gradient, darker when it sits above. The shift is clamped to the
[0, 1] range, so very light or very dark keys produce a subtler ghost.

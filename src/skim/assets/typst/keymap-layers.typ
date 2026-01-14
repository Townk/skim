#import "svalboard-keys.typ": *

#let keymap = json(bytes(sys.inputs.keymap))
#let appearance = json(bytes(sys.inputs.appearance))
#let bordec_rect = none

#if appearance.border != none or appearance.colors.background != none {
  let fcolor = if appearance.colors.background == none { none } else { rgb(appearance.colors.background) }
  let bstroke = if appearance.border == none { none } else { (paint: rgb(appearance.border.color), thickness: 2pt) }
  let bradius = if appearance.border == none { 0pt } else { 1pt * appearance.border.radius }
  bordec_rect = rect(
    width: 1598pt,
    height: 558pt,
    radius: bradius,
    fill: fcolor,
    stroke: bstroke,
  )
}
#set page(
  margin: 0pt,
  width: 1600pt,
  height: 560pt,
  fill: none,
  background: bordec_rect,
)

#set text(fill: rgb(appearance.colors.text));

#let keymapWidth = 1540pt // 1540pt x 500pt
#let keymapHeight = keymapWidth * 0.3246

#block(inset: 30pt)[
  #for layer in keymap.layers {
    layerKeymap(keymap, layer, size: (keymapWidth, keymapHeight))
  }
]


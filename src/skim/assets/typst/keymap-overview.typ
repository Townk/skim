#import "svalboard-keys.typ": *

#let keymap = json(bytes(sys.inputs.keymap))
#let appearance = json(bytes(sys.inputs.appearance))
#let bordec_rect = none

#let pageWidth = 1800pt
#let pageBorderWidth = pageWidth - 2pt
#let pageHeight = ((882 * keymap.selectedLayers.len() + 1345) * pageWidth) / 7200
#let pageBorderHeight = pageHeight - 2pt

#if appearance.border != none or appearance.colors.background != none {
  let fcolor = if appearance.colors.background == none { none } else { rgb(appearance.colors.background) }
  let bstroke = if appearance.border == none { none } else { (paint: rgb(appearance.border.color), thickness: 2pt) }
  let bradius = if appearance.border == none { 0pt } else { 1pt * appearance.border.radius }
  bordec_rect = rect(
    width: pageBorderWidth,
    height: pageBorderHeight,
    radius: bradius,
    fill: fcolor,
    stroke: bstroke,
  )
}
#set page(
  margin: 0pt,
  width: pageWidth,
  height: pageHeight,
  fill: none,
  background: bordec_rect,
)

#let keymapWidth = 1350pt // 1540pt x 500pt

#context {
  let tableRows = ()

  for i in range(keymap.selectedLayers.len()-1, -1, step: -1) {
    let layerIdx = keymap.selectedLayers.at(i)
    let layer = keymap.layers.at(layerIdx)
    let layerName = if i > 0 { layer.name } else { "LETTERS" }
    let layerSubName = if i > 0 { none } else { layer.name }
    let layerColor = layerPrimaryColor(layer)
    let vertInset = if i == 7 { 21pt } else { 50pt }
    tableRows += (
      box(inset: (top: vertInset), width: 370pt)[
        #if i == 7 {
          box(inset: (left: 15pt), text(
            font: "Roboto",
            weight: "black",
            fill: text.fill.darken(30%),
            tracking: 2pt,
            size: 22pt,
            "LAYERS",
          ))
        }
        #rect(
          inset: 15pt,
          width: 270pt,
          radius: 5pt,
          fill: layerColor,
          text(
            font: "Roboto",
            weight: "black",
            fill: white,
            tracking: 2pt,
            size: 22pt,
            upper[#(layerIdx + 1) #layerName],
          ),
        )
        #if layerSubName != none {
          box(inset: (left: 15pt), text(
            font: "Roboto",
            weight: "black",
            fill: layerColor,
            tracking: 2pt,
            size: 22pt,
            upper(layerSubName),
          ))
        }
      ],
      minimalLayer(keymap, layer, keymapWidth),
    )
  }

  block(inset: 30pt)[
    #table(
      columns: 2,
      row-gutter: 20pt,
      stroke: none,
      image(width: 300pt, "svalboard-logo.svg"),
      box(inset: (top: 37pt), text(
        font: "Roboto",
        weight: "black",
        fill: text.fill.darken(70%),
        size: 32pt,
        "Colemak Layers Layout",
      )),
      ..tableRows,
      box(inset: (top: 50pt), width: 370pt)[
        #rect(
          inset: 15pt,
          width: 270pt,
          radius: 5pt,
          fill: text.fill,
          text(
            font: "Roboto",
            weight: "black",
            fill: white,
            tracking: 2pt,
            size: 22pt,
            upper[THUMBS],
          ),
        )
      ],
      align(center)[
        #thumb-cluster(
          keymap,
          keymap.layers.at(0),
          TCL,
          size: (keymapWidth * 0.2, keymapWidth * 0.13),
        )#h(55pt)#thumb-cluster(
          keymap,
          keymap.layers.at(0),
          TCR,
          size: (keymapWidth * 0.2, keymapWidth * 0.13),
        )
      ],
    )
  ]
}

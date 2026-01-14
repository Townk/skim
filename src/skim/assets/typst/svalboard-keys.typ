#import "@preview/one-liner:0.2.0": *
#import "@preview/nerd-icons:0.2.0": *

// [
//    0,  1,  2,  3,  4,  5,
//    6,  7,  8,  9, 10, 11,
//   12, 13, 14, 15, 16, 17,
//   18, 19, 20, 21, 22, 23,
//
//   24, 25, 26, 27, 28, 29,
//   30, 31, 32, 33, 34, 35,
//   36, 37, 38, 39, 40, 41,
//   42, 43, 44, 45, 46, 47,
//
//   48, 49, 50, 51, 52, 53,
//   54, 55, 56, 57, 58, 59,
// ]

#let FR1 = 0
#let FR2 = 1
#let FR3 = 2
#let FR4 = 3
#let FL1 = 4
#let FL2 = 5
#let FL3 = 6
#let FL4 = 7
#let TCR = 8
#let TCL = 9

#let CENTER = 0
#let NORTH = 1
#let EAST = 2
#let SOUTH = 3
#let WEST = 4
#let DSOUTH = 5

#let DOWN = 0
#let PAD = 1
#let UP = 2
#let NAIL = 3
#let KNUCKLE = 4
#let DDOWN = 5

#let RIGHT = 0
#let LEFT = 1

#let CCENTER = 0
#let CSOUTH = 1
#let CDSOUTH = 2
#let CEAST = 3
#let CNORTH = 4
#let CWEST = 5

#let CDOWN = 1
#let CDDOWN = 0
#let CUP = 0
#let CPAD = 6
#let CNAIL = 6
#let CKNUCKLE = 6

#let keyLabel(layer, cluster, key) = {
  return [#(
    layer
      .labels
      .at(cluster)
      .at(key)
      .replace(
        regex("%%([^[:blank:]%]+);"),
        m => nf-icon-string(m.captures.at(0)),
      )
  )]
}

#let keyColor(layer, key) = { return rgb(layer.colors.at(key)) }

#let keyColorAccent(layer, key) = {
  if key == 0 { return none }
  return keyColor(layer, key - 1)
}

#let layerPrimaryColor(layer) = {
  return rgb(layer.colors.at(layer.primaryColor))
}

#let layerSecondaryColor(layer) = {
  return rgb(layer.colors.at(layer.secondaryColor))
}

#let layerToggleIndex(layer, side, key) = {
  if key < 0 or key > 5 or side < 0 or side > 1 { return none }
  return layer.layerToggles.at(side).at(key)
}

#let layerToggleIndex2(layer, cluster, key) = {
  if key < 0 or key > 5 or cluster < 0 or cluster > 9 { return none }
  return layer.layerToggles.at(cluster).at(key)
}

#let layerToggleLabel(layer, side, key) = {
  let targetIndex = layerToggleIndex(layer, side, key)
  if targetIndex == none { return none }
  return [#(targetIndex + 1)]
}

#let layerToggleLabel2(layer, cluster, key) = {
  let targetIndex = layerToggleIndex2(layer, cluster, key)
  if targetIndex == none { return none }
  return [#(targetIndex + 1)]
}

#let layerToggleColor(keymap, layer, side, key) = {
  let targetIndex = layerToggleIndex(layer, side, key)
  if targetIndex == none or targetIndex < 0 or targetIndex >= keymap.layers.len() {
    return none
  }
  return layerPrimaryColor(keymap.layers.at(targetIndex))
}

#let layerToggleColor2(keymap, layer, cluster, key) = {
  let targetIndex = layerToggleIndex2(layer, cluster, key)
  if targetIndex == none or targetIndex < 0 or targetIndex >= keymap.layers.len() {
    return none
  }
  return layerPrimaryColor(keymap.layers.at(targetIndex))
}

#let trapezoid(
  size: array,
  slant: 0pt,
  short-base-position: top,
  short-base-alignment: center,
  bezier-control: 1.0,
  radius: 0pt,
  fill: none,
  stroke: none,
) = box(
  width: size.at(0),
  height: size.at(1),
  {
    let width = size.at(0)
    let height = size.at(1)
    let slant_tl = 0pt
    let slant_tr = 0pt
    let slant_bl = 0pt
    let slant_br = 0pt
    let path = ()

    if short-base-position == top or short-base-position == bottom {
      if short-base-position == top {
        if short-base-alignment == right {
          slant_tl = slant * 2
        } else if short-base-alignment == left {
          slant_tr = slant * 2
        } else {
          slant_tr = slant
          slant_tl = slant
        }
      } else {
        if short-base-alignment == right {
          slant_bl = slant * 2
        } else if short-base-alignment == left {
          slant_br = slant * 2
        } else {
          slant_bl = slant
          slant_br = slant
        }
      }
      path = path + (curve.move((slant_tl + radius, 0pt)),)
      if radius > 0pt {
        path = path + (curve.quad((0pt + slant_tl * bezier-control, 0pt), (0pt + slant_tl, radius)),)
      }
      path = path + (curve.line((0pt + slant_bl, height - radius)),)
      if radius > 0pt {
        path = path + (curve.quad((0pt + slant_bl * bezier-control, height), (slant_bl + radius, height)),)
      }
      path = path + (curve.line((width - slant_br - radius, height)),)
      if radius > 0pt {
        path = path + (curve.quad((width - slant_br * bezier-control, height), (width - slant_br, height - radius)),)
      }
      path = path + (curve.line((width - slant_tr, radius)),)
      if radius > 0pt {
        path = path + (curve.quad((width - slant_tr * bezier-control, 0pt), (width - slant_tr - radius, 0pt)),)
      }
    } else {
      if short-base-position == left {
        if short-base-alignment == top {
          slant_bl = slant * 2
        } else if short-base-alignment == bottom {
          slant_tl = slant * 2
        } else {
          slant_bl = slant
          slant_tl = slant
        }
      } else {
        if short-base-alignment == top {
          slant_br = slant * 2
        } else if short-base-alignment == bottom {
          slant_tr = slant * 2
        } else {
          slant_br = slant
          slant_tr = slant
        }
      }
      path = path + (curve.move((radius, 0pt + slant_tl)),)
      if radius > 0pt {
        path = path + (curve.quad((0pt, 0pt + slant_tl * bezier-control), (0pt, slant_tl + radius)),)
      }
      path = path + (curve.line((0pt, height - slant_bl - radius)),)
      if radius > 0pt {
        path = path + (curve.quad((0pt, height - slant_bl * bezier-control), (radius, height - slant_bl)),)
      }
      path = path + (curve.line((width - radius, height - slant_br)),)
      if radius > 0pt {
        path = path + (curve.quad((width, height - slant_br * bezier-control), (width, height - slant_br - radius)),)
      }
      path = path + (curve.line((width, slant_tr + radius)),)
      if radius > 0pt {
        path = path + (curve.quad((width, 0pt + slant_tr * bezier-control), (width - radius, 0pt + slant_tr)),)
      }
    }

    curve(
      ..path,
      curve.close(),
      fill: fill,
      stroke: stroke,
    )
  },
)

#let down-key(
  size: array,
  label: str,
  fill: none,
  stroke: none,
) = box({
  trapezoid(
    size: size,
    slant: size.at(0) * 0.12,
    radius: size.at(0) * 0.15,
    fill: fill,
    stroke: stroke,
  )
  place(bottom + center, dy: -size.at(1) * 0.14, label)
})

#let double-down-key(
  size: array,
  label: str,
  fill: none,
  stroke: none,
) = box({
  trapezoid(
    size: size,
    slant: size.at(0) * 0.05,
    radius: size.at(0) * 0.15,
    fill: fill,
    stroke: stroke,
  )
  place(horizon + center, label)
})

#let up-key(
  size: array,
  label: str,
  side: left,
  fill: none,
  stroke: none,
) = box({
  let hor_padding = if side == left { size.at(0) } else { -size.at(0) } * 0.1
  let other_side = if side == left { right } else { left }

  trapezoid(
    size: size,
    slant: size.at(1) * 0.11,
    radius: size.at(1) * 0.12,
    short-base-position: other_side,
    short-base-alignment: top,
    fill: fill,
    stroke: stroke,
  )

  place(horizon + other_side, dx: -hor_padding, dy: -size.at(1) * 0.12, box(width: size.at(0) * 0.5)[#label])
})

#let pad-key(
  size: array,
  label: str,
  side: left,
  fill: none,
  stroke: none,
) = box({
  let hor_padding = if side == left { size.at(0) } else { -size.at(0) } * 0.22
  let other_side = if side == left { right } else { left }

  trapezoid(
    size: size,
    slant: size.at(1) * 0.02,
    radius: size.at(1) * 0.13,
    short-base-position: bottom,
    short-base-alignment: side,
    fill: fill,
    stroke: stroke,
  )

  place(horizon + other_side, dx: -hor_padding, dy: -size.at(1) * 0.05, box(width: size.at(0) * 0.35)[#label])
})

#let nail-key(
  size: array,
  label: str,
  side: left,
  fill: none,
  stroke: none,
) = box({
  let hor_padding = if side == left { size.at(0) } else { -size.at(0) } * 0.22
  let other_side = if side == left { right } else { left }

  trapezoid(
    size: size,
    slant: size.at(1) * 0.02,
    radius: size.at(1) * 0.13,
    short-base-position: bottom,
    short-base-alignment: other_side,
    fill: fill,
    stroke: stroke,
  )

  place(horizon + side, dx: hor_padding, dy: -size.at(1) * 0.05, box(width: size.at(0) * 0.35)[#label])
})

#let knuckle-key(
  size: array,
  label: str,
  side: left,
  fill: none,
  stroke: none,
) = box({
  let hor_padding = if side == left { size.at(0) } else { -size.at(0) } * 0.24
  let other_side = if side == left { right } else { left }

  trapezoid(
    size: size,
    slant: size.at(1) * 0.02,
    radius: size.at(1) * 0.13,
    short-base-position: bottom,
    short-base-alignment: other_side,
    fill: fill,
    stroke: stroke,
  )

  place(horizon + side, dx: hor_padding, dy: -size.at(1) * 0.05, box(width: size.at(0) * 0.35)[#label])
})

#let thumb-cluster(
  keymap,
  layer,
  cluster,
  size: array,
) = box(width: size.at(0), height: size.at(1), {
  let cluster_width = size.at(0)
  let cluster_height = size.at(1)
  let side = if cluster == TCR { right } else { left }
  let other_side = if cluster == TCR { left } else { right }
  let side_aware_width = if side == left { cluster_width } else { -cluster_width }

  // Down
  place(top + center, down-key(
    size: (cluster_width * 0.23, cluster_height),
    fill: keyColor(layer, CDOWN),
    label: text(
      font: "Roboto",
      weight: "black",
      fill: white,
      fit-to-width(max-text-size: cluster_width * 0.075, keyLabel(layer, cluster, DOWN)),
    ),
  ))

  // Double-Down
  place(top + center, dy: 20pt, double-down-key(
    size: (cluster_width * 0.11, cluster_height * 0.235),
    fill: keyColor(layer, CDDOWN),
    stroke: (paint: white, thickness: cluster_height * 0.011, cap: "round"),
    label: text(fill: white, fit-to-width(max-text-size: cluster_width * 0.06, keyLabel(layer, cluster, DDOWN))),
  ))

  // Up
  place(bottom + side, dx: side_aware_width * 0.1, dy: -cluster_height * 0.39, up-key(
    size: (cluster_width * 0.38, cluster_height * 0.2),
    fill: keyColor(layer, CUP),
    side: side,
    stroke: (
      paint: white,
      thickness: cluster_height * 0.017,
      cap: "round",
    ),
    label: text(
      font: "Roboto",
      weight: "black",
      fill: white,
      fit-to-width(max-text-size: cluster_width * 0.05, keyLabel(layer, cluster, UP)),
    ),
  ))

  // Pad
  let padLayerToggleColor = layerToggleColor2(keymap, layer, if side == left { TCL } else { TCR }, PAD)
  place(top + side, dy: cluster_height * 0.05, box({
    pad-key(
      size: (cluster_width * 0.395, cluster_height * 0.32),
      side: side,
      fill: layerSecondaryColor(layer),
      stroke: none,
      label: text(
        font: "Roboto",
        weight: "black",
        fill: white,
        fit-to-width(max-text-size: cluster_width * 0.1, keyLabel(layer, cluster, PAD)),
      ),
    )
    if padLayerToggleColor != none {
      let padLayerToggleLabel = layerToggleLabel2(layer, if side == left { TCL } else { TCR }, PAD)
      place(horizon + side, dx: side_aware_width * 0.03, circle(
        radius: cluster_height * 0.07,
        fill: padLayerToggleColor,
        stroke: (paint: white, thickness: cluster_height * 0.011, cap: "round"),
      )[
        #set align(center + horizon)
        #text(
          font: "Roboto",
          weight: "black",
          tracking: 1pt,
          size: cluster_height * 0.065,
          fill: white,
          padLayerToggleLabel,
        )
      ])
    }
  }))

  // Nail
  let nailLayerToggleColor = layerToggleColor2(keymap, layer, if side == left { TCL } else { TCR }, NAIL)
  place(top + other_side, dy: cluster_height * 0.05, box({
    nail-key(
      size: (cluster_width * 0.395, cluster_height * 0.32),
      side: side,
      fill: layerSecondaryColor(layer),
      stroke: none,
      label: text(
        font: "Roboto",
        weight: "black",
        fill: white,
        fit-to-width(max-text-size: cluster_width * 0.1, keyLabel(layer, cluster, NAIL)),
      ),
    )
    if nailLayerToggleColor != none {
      let nailLayerToggleLabel = layerToggleLabel2(layer, if side == left { TCL } else { TCR }, NAIL)
      place(horizon + other_side, dx: -side_aware_width * 0.03, circle(
        radius: cluster_height * 0.07,
        fill: nailLayerToggleColor,
        stroke: (paint: white, thickness: cluster_height * 0.011, cap: "round"),
      )[
        #set align(center + horizon)
        #text(
          font: "Roboto",
          weight: "black",
          tracking: 1pt,
          size: cluster_height * 0.065,
          fill: white,
          nailLayerToggleLabel,
        )
      ])
    }
  }))

  // Knuckle
  let knuckleLayerToggleColor = layerToggleColor2(keymap, layer, if side == left { TCL } else { TCR }, KNUCKLE)
  place(top + other_side, dy: cluster_height * 0.075 + cluster_height * 0.32, box({
    knuckle-key(
      size: (cluster_width * 0.383, cluster_height * 0.32),
      side: side,
      fill: layerSecondaryColor(layer),
      stroke: none,
      label: text(
        font: "Roboto",
        weight: "black",
        fill: white,
        fit-to-width(max-text-size: cluster_width * 0.1, keyLabel(layer, cluster, KNUCKLE)),
      ),
    )
    if knuckleLayerToggleColor != none {
      let knuckleLayerToggleLabel = layerToggleLabel2(layer, if side == left { TCL } else { TCR }, KNUCKLE)
      place(horizon + other_side, dx: -side_aware_width * 0.03, circle(
        radius: cluster_height * 0.07,
        fill: knuckleLayerToggleColor,
        stroke: (paint: white, thickness: cluster_height * 0.011, cap: "round"),
      )[
        #set align(center + horizon)
        #text(font: "Roboto", weight: "black", size: cluster_height * 0.065, fill: white, knuckleLayerToggleLabel)
      ])
    }
  }))
})

#let finger-cluster(
  layer,
  cluster,
  size: array,
) = box(width: size.at(0), height: size.at(1), {
  let cluster_width = size.at(0)
  let cluster_height = size.at(1)

  // Center
  place(center + horizon, dy: -cluster_width * 0.145, circle(
    width: cluster_width * 0.31,
    height: cluster_width * 0.31,
    fill: keyColor(layer, CCENTER),
  )[
    #set align(center + horizon)
    #text(font: "Roboto", weight: "regular", fill: white, fit-to-width(max-text-size: cluster_width * 0.16, keyLabel(
      layer,
      cluster,
      CENTER,
    )))
  ])

  // South
  place(bottom + center, dy: -cluster_width * 0.29, box({
    rect(
      width: cluster_width * 0.33,
      height: cluster_width * 0.33,
      radius: cluster_width * 0.047,
      fill: keyColor(layer, CSOUTH),
      inset: (top: cluster_width * 0.04, bottom: cluster_width * 0.02),
    )[
      #set align(center + horizon)
      #text(font: "Roboto", weight: "regular", fill: white, fit-to-width(max-text-size: cluster_width * 0.16, keyLabel(
        layer,
        cluster,
        SOUTH,
      )))
    ]
    place(top, rect(
      width: cluster_width * 0.33,
      height: cluster_width * 0.058,
      radius: cluster_width * 0.029,
      fill: keyColorAccent(layer, CSOUTH),
    ))
  }))

  // Double-South
  place(bottom + center, box({
    trapezoid(
      size: (cluster_width * 0.35, cluster_width * 0.27),
      slant: cluster_width * 0.018,
      short-base-position: top,
      short-base-alignment: center,
      radius: cluster_width * 0.047,
      fill: keyColor(layer, CDSOUTH),
    )
    place(top + center, rect(
      width: cluster_width * 0.31,
      height: cluster_width * 0.058,
      radius: cluster_width * 0.029,
      fill: keyColorAccent(layer, CDSOUTH),
    ))
    place(center + horizon, box(inset: (top: cluster_width * 0.04, bottom: cluster_width * 0.02))[
      #text(font: "Roboto", weight: "regular", fill: white, fit-to-width(max-text-size: cluster_width * 0.14, keyLabel(
        layer,
        cluster,
        DSOUTH,
      )))])
  }))

  // East
  place(horizon + right, dy: -cluster_width * 0.145, box({
    rect(
      width: cluster_width * 0.33,
      height: cluster_width * 0.33,
      radius: cluster_width * 0.047,
      fill: if cluster < FL1 { keyColor(layer, CWEST) } else { keyColor(layer, CEAST) },
      inset: (left: cluster_width * 0.078, right: cluster_width * 0.02),
    )[
      #set align(center + horizon)
      #text(font: "Roboto", weight: "regular", fill: white, fit-to-width(max-text-size: cluster_width * 0.16, keyLabel(
        layer,
        cluster,
        EAST,
      )))
    ]
    place(left + top, rect(
      width: cluster_width * 0.058,
      height: cluster_width * 0.33,
      radius: cluster_width * 0.029,
      fill: if cluster < FL1 { keyColorAccent(layer, CWEST) } else { keyColorAccent(layer, CEAST) },
    ))
  }))

  // North
  place(top + center, box({
    rect(
      width: cluster_width * 0.33,
      height: cluster_width * 0.33,
      radius: cluster_width * 0.047,
      fill: keyColor(layer, CNORTH),
      inset: (bottom: cluster_width * 0.06, top: cluster_width * 0.02),
    )[
      #set align(center + horizon)
      #text(font: "Roboto", weight: "regular", fill: white, fit-to-width(max-text-size: cluster_width * 0.16, keyLabel(
        layer,
        cluster,
        NORTH,
      )))
    ]
    place(bottom, rect(
      width: cluster_width * 0.33,
      height: cluster_width * 0.058,
      radius: cluster_width * 0.029,
      fill: keyColorAccent(layer, CNORTH),
    ))
  }))

  // West
  place(horizon + left, dy: -cluster_width * 0.145, box({
    rect(
      width: cluster_width * 0.33,
      height: cluster_width * 0.33,
      radius: cluster_width * 0.047,
      fill: if cluster < FL1 { keyColor(layer, CEAST) } else { keyColor(layer, CWEST) },
      inset: (right: cluster_width * 0.078, left: cluster_width * 0.02),
    )[
      #set align(center + horizon)
      #text(font: "Roboto", weight: "regular", fill: white, fit-to-width(max-text-size: cluster_width * 0.16, keyLabel(
        layer,
        cluster,
        WEST,
      )))
    ]
    place(right + top, rect(
      width: cluster_width * 0.058,
      height: cluster_width * 0.33,
      radius: cluster_width * 0.029,
      fill: if cluster < FL1 { keyColorAccent(layer, CEAST) } else { keyColorAccent(layer, CWEST) },
    ))
  }))
})

#let color-to-hex(c) = {
  if c == none or c == auto {
    none
  } else {
    let r = int(c.r * 255)
    let g = int(c.g * 255)
    let b = int(c.b * 255)
    "#" + format("{:02x}", r) + format("{:02x}", g) + format("{:02x}", b)
  }
}

#let boardSide(keymap, layer, side, size: array) = box(width: size.at(0), height: size.at(1), {
  let side_width = size.at(0)
  let side_height = size.at(1)
  let fingerClusterSize = (side_width * 0.226, side_height * 0.44) // 348.04 x 220
  let thumbClusterSize = (side_width * 0.36, side_height * 0.34)

  let other_side = if side == left { right } else { left }
  let cluster1 = if side == left { FL4 } else { FR1 }
  let cluster2 = if side == left { FL3 } else { FR2 }
  let cluster3 = if side == left { FL2 } else { FR3 }
  let cluster4 = if side == left { FL1 } else { FR4 }
  let cluster5 = if side == left { TCL } else { TCR }

  let cluster1Pad = if side == left { 0pt } else { -side_width * 0.706 }
  let cluster2Pad = if side == left { side_width * 0.226 } else { -side_width * 0.48 }
  let cluster3Pad = if side == left { side_width * 0.48 } else { -side_width * 0.226 }
  let cluster4Pad = if side == left { side_width * 0.706 } else { 0pt }

  place(top + side, dy: side_height * 0.14, dx: cluster1Pad, {
    finger-cluster(layer, cluster1, size: fingerClusterSize)
  })
  place(top + side, dy: 0pt, dx: cluster2Pad, {
    finger-cluster(layer, cluster2, size: fingerClusterSize)
  })
  place(top + side, dy: 0pt, dx: cluster3Pad, {
    finger-cluster(layer, cluster3, size: fingerClusterSize)
  })
  place(top + side, dy: side_height * 0.14, dx: cluster4Pad, {
    finger-cluster(layer, cluster4, size: fingerClusterSize)
  })
  place(bottom + other_side, {
    thumb-cluster(keymap, layer, cluster5, size: thumbClusterSize)
  })
  if side == right {
    let logo-img = read("svalboard-logo.svg")
    context {
      let current-fill = text.fill.to-hex()
      let new-svg = logo-img.replace("currentColor", current-fill)
      place(bottom + right, image.decode(new-svg, width: 20%))
    }
  } else {
    place(bottom + left, dy: -30pt, text(font: "Roboto", weight: "thin", size: 45pt)[#layer.name Layer])
  }
})

#let layerKeymap(keymap, layer, size: array) = box({
  let layer_width = size.at(0) // 750 * 2 + 40 -> 1540 // 0.487
  let layer_height = size.at(1)
  let boardSideSize = (layer_width * 0.487, layer_height)
  let sidesSpacing = layer_width * 0.0259
  return [#boardSide(keymap, layer, left, size: boardSideSize)#h(sidesSpacing)#boardSide(
      keymap,
      layer,
      right,
      size: boardSideSize,
    )]
})

#let minimalLayer(keymap, layer, width) = box(
  width: width,
  height: (width / 8 - 22pt) / 0.7704,
  {
    let fingerClusterWidth = width / 8 - 22pt //0.7704
    let fingerClusterSize = (fingerClusterWidth, fingerClusterWidth / 0.7704)

    place(top + left, dx: 0pt, {
      finger-cluster(layer, FL4, size: fingerClusterSize)
    })

    place(top + left, dx: 0pt + fingerClusterWidth + 20pt, {
      finger-cluster(layer, FL3, size: fingerClusterSize)
    })

    place(top + left, dx: 0pt + (fingerClusterWidth + 20pt) * 2, {
      finger-cluster(layer, FL2, size: fingerClusterSize)
    })

    place(top + left, dx: 0pt + (fingerClusterWidth + 20pt) * 3, {
      finger-cluster(layer, FL1, size: fingerClusterSize)
    })

    place(top + right, dx: 0pt, {
      finger-cluster(layer, FR4, size: fingerClusterSize)
    })

    place(top + right, dx: 0pt - (fingerClusterWidth + 20pt), {
      finger-cluster(layer, FR3, size: fingerClusterSize)
    })

    place(top + right, dx: 0pt - (fingerClusterWidth + 20pt) * 2, {
      finger-cluster(layer, FR2, size: fingerClusterSize)
    })

    place(top + right, dx: 0pt - (fingerClusterWidth + 20pt) * 3, {
      finger-cluster(layer, FR1, size: fingerClusterSize)
    })
  },
)


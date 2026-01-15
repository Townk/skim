## ADDED Requirements

### Requirement: Typst Integration
The application SHALL use the Typst Python bindings to render images.

#### Scenario: Compile document
- **WHEN** a render request is made
- **THEN** `typst.compile` is called with the correct input template and system inputs.

### Requirement: Layer Gradient Generation
The application SHALL generate a 7-color gradient for each layer based on its base color.

#### Scenario: Gradient colors
- **WHEN** preparing layer data for Typst
- **THEN** a list of 7 hex color strings is generated, where the 3rd is the primary and 7th is secondary (neutral).

### Requirement: Data Serialization
The application SHALL serialize keymap and appearance data as JSON strings for Typst consumption.

#### Scenario: sys_inputs preparation
- **WHEN** calling Typst
- **THEN** `sys_inputs` contains `keymap` and `appearance` as JSON-encoded strings.

### Requirement: Output Formats
The application SHALL support generating images in SVG and PNG formats.

#### Scenario: SVG output
- **WHEN** format is set to `svg`
- **THEN** the output file extension and Typst format are set to SVG.

### Requirement: Layer Selection
The application SHALL support generating images for specific layers, ranges of layers, or all layers.

#### Scenario: Specific layer
- **WHEN** user requests layer 1
- **THEN** only the image for layer 1 is generated.

#### Scenario: Overview
- **WHEN** user requests `overview`
- **THEN** the overview image is generated using `keymap-overview.typ`.

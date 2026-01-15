# configuration Specification

## Purpose
TBD - created by archiving change setup-initial-specs. Update Purpose after archive.
## Requirements
### Requirement: Configuration Structure
The application SHALL use a YAML configuration file to define output appearance and behavior.

#### Scenario: Valid config structure
- **WHEN** the application loads a config file
- **THEN** it validates that it matches the expected schema (appearance, colors, etc.).

### Requirement: QMK Color Import
The application SHALL be able to parse a QMK `color.h` file to populate named colors.

#### Scenario: Parse color.h
- **WHEN** a valid `color.h` path is provided to the configuration generator
- **THEN** it extracts color definitions and converts them to the config format.

### Requirement: Keybard Metadata Import
The application SHALL be able to extract layer colors, names, and keycode overrides from a Keybard `.kbi` file.

#### Scenario: Parse .kbi metadata
- **WHEN** a valid `.kbi` file is provided to the configuration generator
- **THEN** it extracts `layer_colors` (HSV), layer names from `cosmetic.layer`, and `custom_keycodes`.

### Requirement: Color Adjustment
The application SHALL allow adjusting lightness and saturation of imported colors.

#### Scenario: Apply HSL adjustment
- **WHEN** lightness and saturation adjustments are specified
- **THEN** all imported colors are transformed to the new HSL values before being saved.

### Requirement: Config Generation
The application SHALL generate a `skim-config.yaml` file with the gathered settings.

#### Scenario: Generate to directory
- **WHEN** the output path is an existing directory
- **THEN** the configuration file is generated in that directory with the name `skim-config.yaml`

#### Scenario: Generate new file
- **WHEN** the output path does not exist
- **THEN** the tool assumes it is a file path and generates the configuration with the given file name

#### Scenario: Overwrite prompt
- **WHEN** the output path is an existing file AND `--force` is NOT provided
- **THEN** the user is asked for confirmation to overwrite the file

#### Scenario: Force overwrite
- **WHEN** the output path is an existing file AND `--force` IS provided
- **THEN** the file is overwritten without confirmation


## MODIFIED Requirements

### Requirement: Generate Command
The CLI SHALL provide a `generate` command to create keymap images.

#### Scenario: Generate help
- **WHEN** user runs `skim generate --help`
- **THEN** it displays arguments: `--config`, `--keymap`, `--output-dir`, `--format`, `--layer`, `--force`.

#### Scenario: Stdin input
- **WHEN** user runs `skim generate` without `--keymap` or `skim generate -`
- **THEN** the keymap data is read from standard input.

#### Scenario: Output directory validation
- **WHEN** user specifies an existing file as `--output-dir`
- **THEN** the command fails with an error explaining it must be a directory.

#### Scenario: Force overwrite
- **WHEN** user runs `skim generate --force` and one or more generated files already exist
- **THEN** the generated file or files are overwritten without confirmation.

#### Scenario: Interactive overwrite
- **WHEN** user runs `skim generate` and one or more generated files already exist
- **THEN** the user is asked for confirmation before overwriting.

#### Scenario: Multiple layer arguments
- **WHEN** user runs `skim generate` with multiple `--layer` arguments
- **THEN** each layer argument is resolved and aggregated to be generated

#### Scenario: Single layer
- **WHEN** user runs `skim generate --layer 1`
- **THEN** only the keymap image of the first layer will be generated

#### Scenario: Range of layer
- **WHEN** user runs `skim generate --layer 1-3`
- **THEN** the keymap image of the first, second, and third layers will be generated

#### Scenario: List of layer
- **WHEN** user runs `skim generate --layer "1,2-4, 6, 8"`
- **THEN** the layers to generate are resolved as a comma-separated list

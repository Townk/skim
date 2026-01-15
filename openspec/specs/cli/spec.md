# cli Specification

## Purpose
TBD - created by archiving change setup-initial-specs. Update Purpose after archive.
## Requirements
### Requirement: CLI Entry Point
The application SHALL be invokable via the `skim` command.

#### Scenario: Basic invocation
- **WHEN** user runs `skim --help`
- **THEN** it displays help information listing available commands.

### Requirement: Command Aliasing
The CLI SHALL support discovering commands by unique prefixes or abbreviations.

#### Scenario: Abbreviated command
- **WHEN** user runs `skim conf` or `skim c`
- **THEN** the `configure` command is executed.

### Requirement: Configure Command
The CLI SHALL provide a `configure` command to help users generate the configuration file.

#### Scenario: Configure help
- **WHEN** user runs `skim configure --help`
- **THEN** it displays arguments: `--qmk-color-header`, `--keybard-keymap`, `--adjust-lightness`, `--adjust-saturation`, `--output`, `--force`.

#### Scenario: Force overwrite
- **WHEN** user runs `skim configure --output existing_file.yaml --force`
- **THEN** the file is overwritten without confirmation.

#### Scenario: Interactive overwrite
- **WHEN** user runs `skim configure --output existing_file.yaml` (without force)
- **THEN** the user is asked for confirmation before overwriting.

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

### Requirement: Logging Control
The CLI SHALL provide options to control logging verbosity.

#### Scenario: Verbosity level
- **WHEN** user runs `skim --verbosity DEBUG generate ...`
- **THEN** debug logs are printed.

#### Scenario: Quiet mode
- **WHEN** user runs `skim --quiet generate ...`
- **THEN** no logs (or only critical errors) are printed.


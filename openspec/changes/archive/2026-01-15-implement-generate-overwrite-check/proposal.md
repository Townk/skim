# Change: Implement Generate Overwrite Check

## Why
The `generate` command is missing the file overwrite protection mechanisms defined in the `cli` specification. Currently, the tool blindly overwrites output files without warning, which risks data loss for users who may have manually edited generated files or want to preserve previous runs. The spec requires both an interactive confirmation prompt and a `--force` flag to bypass it.

## What Changes
- Update `skim generate` CLI command to accept a `--force` flag (no short `-f` alias as it conflicts with `--format`).
- Implement pre-generation checks to identify existing output files in the target directory.
- Add interactive prompt logic to ask for confirmation before overwriting unless `--force` is used.
- Update `ImageGenerator` or CLI logic to support this validation step.

## Impact
- **Affected specs**: `cli` (compliance fix)
- **Affected code**: `src/skim/ui/cli.py`, `src/skim/application/image_generator.py`

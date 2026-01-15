## Context
The project `qmk-skim` (Svalboard Keymap Image Maker) is a CLI tool to generate keymap images for Svalboard keyboards. It uses Python for logic and Typst for rendering. The detailed requirements are currently in a monolithic `SPEC.md` file.

## Goals
- Formalize requirements into OpenSpec format.
- Ensure clear separation of concerns between CLI, Logic, and Rendering.
- Define data structures for configuration and keymap data explicitly.

## Decisions
- **Split into Capabilities**: The monolithic spec is broken down into `cli`, `configuration`, `image-generation`, and `keymap-parsing` to allow for modular development and testing.
- **Typst for Rendering**: As per `SPEC.md`, Typst is the chosen engine. The spec will treat Typst templates as assets and the Python-Typst bridge as the core logic.
- **Click for CLI**: As per `SPEC.md`, `click` is the library for CLI interactions.
- **PyYAML for Config**: As per `SPEC.md`, YAML is the configuration format.

## Risks / Trade-offs
- **Dependency on Typst**: The tool requires the `typst` Python package. This is a hard dependency.
- **Asset Management**: Bundling Typst files and fonts needs careful handling in the python package to ensure they are available at runtime.

## Migration Plan
- This is an initial setup, so no migration is needed. Future changes will evolve these specs.

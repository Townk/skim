# Configuration

Skim is highly configurable: layout dimensions, spacing, colors, keycode
display, and more can all be tuned to match how you want your keymap images
to look.

There are three ways to configure Skim. All three eventually flow into the
same YAML configuration file — they're just different ways of editing it.

- **Command line options.** The fastest way to make a one-off change. CLI
  arguments take the highest priority and override anything set in the
  configuration file for that run.
- **Configurator UI.** A terminal app for discovering options and previewing
  changes interactively. Every field in the UI maps to an entry in the
  configuration file.
- **Configuration file.** A plain-text YAML file that holds the full set of
  options. The CLI and Configurator UI only surface a subset; if you need
  fine-grained control, this is the source of truth.

## Next steps

The next section walks through every option in the configuration file —
what it does, how to set it, and how it changes the rendered keymap. When
the command-line or Configurator UI pages need to refer to an option, they
link back to its description here instead of repeating it.

- [Configuration File](config-file.md)
- [Command Line Options](cli-options.md)
- [Configurator UI](configurator-ui.md)

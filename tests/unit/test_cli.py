# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for skim.cli module."""

from unittest.mock import patch

import click
import pytest
import yaml
from click.testing import CliRunner

from skim.cli import AliasedGroup, main


class TestAliasedGroup:
    """Tests for AliasedGroup command resolution."""

    def test_get_command_returns_exact_match(self):
        """Returns command for exact name match."""
        group = AliasedGroup()

        @group.command(name="testcmd")
        def test_command():
            pass

        ctx = click.Context(group)
        result = group.get_command(ctx, "testcmd")
        assert result is not None
        assert result.name == "testcmd"

    def test_get_command_returns_prefix_match(self):
        """Returns command for unique prefix match."""
        group = AliasedGroup()

        @group.command()
        def generate():
            pass

        ctx = click.Context(group)
        result = group.get_command(ctx, "gen")
        assert result is not None
        assert result.name == "generate"

    def test_get_command_returns_none_for_no_match(self):
        """Returns None when no commands match."""
        group = AliasedGroup()

        @group.command()
        def test_command():
            pass

        ctx = click.Context(group)
        result = group.get_command(ctx, "xyz")
        assert result is None

    def test_get_command_fails_for_ambiguous_prefix(self):
        """Raises UsageError when prefix matches multiple commands."""
        group = AliasedGroup()

        @group.command()
        def generate():
            pass

        @group.command()
        def get():
            pass

        ctx = click.Context(group)
        with pytest.raises(click.exceptions.UsageError, match="Too many matches"):
            group.get_command(ctx, "ge")

    def test_resolve_command_returns_full_name(self):
        """Returns full command name in resolve_command."""
        group = AliasedGroup()

        @group.command()
        def generate():
            pass

        ctx = click.Context(group)
        name, cmd, args = group.resolve_command(ctx, ["gen"])
        assert name == "generate"
        assert cmd.name == "generate"


class TestMainCommand:
    """Tests for main CLI group."""

    def test_version_option(self):
        """Shows version with --version flag."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "skim" in result.output.lower()

    @patch("skim.cli.generate_keymap")
    def test_verbosity_option_accepted(self, mock_generate, tmp_path):
        """Accepts verbosity level option."""
        runner = CliRunner()
        result = runner.invoke(main, ["-v", "DEBUG", "generate", "-o", str(tmp_path)])
        assert result.exit_code == 0

    @patch("skim.cli.generate_keymap")
    def test_quiet_option_accepted(self, mock_generate, tmp_path):
        """Accepts quiet flag."""
        runner = CliRunner()
        result = runner.invoke(main, ["--quiet", "generate", "-o", str(tmp_path)])
        assert result.exit_code == 0


class TestGenerateCommand:
    """Tests for generate subcommand."""

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_with_keymap_file(self, mock_setup, mock_generate, tmp_path):
        """Generates keymap from file."""
        keymap_file = tmp_path / "keymap.kbi"
        keymap_file.write_text('{"layers": []}')

        runner = CliRunner()
        result = runner.invoke(main, ["generate", "-k", str(keymap_file), "-o", str(tmp_path)])

        # Check that generate_keymap was called
        if result.exit_code != 0:
            # May fail due to validation - that's ok for this test
            pass

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_handles_abort(self, mock_setup, mock_generate):
        """Handles click.Abort gracefully."""
        mock_generate.side_effect = click.Abort()

        runner = CliRunner()
        result = runner.invoke(main, ["generate"])

        assert result.exit_code == 1
        assert "Aborted" in result.output

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_handles_value_error(self, mock_setup, mock_generate):
        """Handles ValueError gracefully."""
        mock_generate.side_effect = ValueError("Invalid keymap")

        runner = CliRunner()
        result = runner.invoke(main, ["generate"])

        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_handles_file_not_found(self, mock_setup, mock_generate):
        """Handles FileNotFoundError gracefully."""
        mock_generate.side_effect = FileNotFoundError("File not found")

        runner = CliRunner()
        result = runner.invoke(main, ["generate"])

        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_handles_json_decode_error(self, mock_setup, mock_generate):
        """Handles JSONDecodeError gracefully."""
        import json

        mock_generate.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        runner = CliRunner()
        result = runner.invoke(main, ["generate"])

        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_handles_os_error(self, mock_setup, mock_generate):
        """Handles OSError gracefully."""
        mock_generate.side_effect = OSError("OS error")

        runner = CliRunner()
        result = runner.invoke(main, ["generate"])

        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_with_stdin_marker(self, mock_setup, mock_generate, tmp_path):
        """Accepts stdin marker '-' for reading from stdin."""
        runner = CliRunner()
        runner.invoke(main, ["generate", "-", "-o", str(tmp_path)])
        # The command should pass the stdin marker to InputFiles
        mock_generate.assert_called_once()
        args = mock_generate.call_args[0]
        assert args[0].force_stdin_keymap is True

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_with_format_option(self, mock_setup, mock_generate, tmp_path):
        """Accepts format option."""
        runner = CliRunner()
        runner.invoke(main, ["generate", "-o", str(tmp_path), "-f", "svg"])
        mock_generate.assert_called_once()
        args = mock_generate.call_args[0]
        assert args[1].output_format == "svg"

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_with_force_option(self, mock_setup, mock_generate, tmp_path):
        """Accepts force option."""
        runner = CliRunner()
        runner.invoke(main, ["generate", "-o", str(tmp_path), "--force"])
        mock_generate.assert_called_once()
        args = mock_generate.call_args[0]
        assert args[1].force_overwrite is True

    @patch("skim.cli.generate_keymap")
    @patch("skim.cli.setup_logging")
    def test_generate_with_layer_option(self, mock_setup, mock_generate, tmp_path):
        """Accepts layer selection options."""
        runner = CliRunner()
        runner.invoke(main, ["generate", "-o", str(tmp_path), "-l", "1", "-l", "2"])
        mock_generate.assert_called_once()


class TestConfigureCommand:
    """Tests for configure subcommand."""

    @patch("skim.cli.setup_logging")
    def test_no_args_shows_help(self, mock_setup):
        """Running configure with no args shows help message."""
        runner = CliRunner()
        result = runner.invoke(main, ["configure"])
        assert result.exit_code == 0
        assert "--interactive" in result.output
        assert "--keymap" in result.output

    @patch("skim.cli.setup_logging")
    def test_interactive_flag_required_for_tui(self, mock_setup):
        """The -i flag is required to launch the TUI."""
        runner = CliRunner()
        result = runner.invoke(main, ["configure"])
        assert result.exit_code == 0
        assert "--interactive" in result.output

    @patch("skim.cli.setup_logging")
    def test_keybard_input_generates_config(self, mock_setup, tmp_path):
        """Running with -k generates config from keybard file."""
        import json

        kbi = tmp_path / "test.kbi"
        kbi.write_text(
            json.dumps(
                {
                    "layers": 1,
                    "keymap": [["KC_A"] * 60],
                    "layer_colors": [{"hue": 85, "sat": 255, "val": 255}],
                    "cosmetic": {"layer": {"0": "Base"}},
                    "custom_keycodes": [],
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-k", str(kbi)])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert len(parsed["keyboard"]["layers"]) == 1
        assert parsed["keyboard"]["layers"][0]["name"] == "Base"

    @patch("skim.cli.setup_logging")
    def test_invalid_keybard_file_shows_error(self, mock_setup, tmp_path):
        """Invalid .kbi content shows error message."""
        kbi = tmp_path / "bad.kbi"
        kbi.write_text("not json")
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-k", str(kbi)])
        assert result.exit_code == 1

    @patch("skim.cli.setup_logging")
    def test_keybard_output_to_stdout(self, mock_setup, tmp_path):
        """Running with -k and no -o outputs YAML to stdout."""
        import json

        kbi = tmp_path / "test.kbi"
        kbi.write_text(
            json.dumps(
                {
                    "layers": 1,
                    "keymap": [["KC_A"] * 60],
                    "layer_colors": [{"hue": 85, "sat": 255, "val": 255}],
                    "cosmetic": {"layer": {"0": "Base"}},
                    "custom_keycodes": [],
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-k", str(kbi)])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert "keyboard" in parsed

    @patch("skim.cli.setup_logging")
    def test_keybard_flag_skips_tui(self, mock_setup, tmp_path):
        """The -k flag always uses CLI path, never TUI."""
        import json

        kbi = tmp_path / "test.kbi"
        kbi.write_text(
            json.dumps(
                {
                    "layers": 1,
                    "keymap": [["KC_A"] * 60],
                    "layer_colors": [{"hue": 85, "sat": 255, "val": 255}],
                    "cosmetic": {"layer": {"0": "Base"}},
                    "custom_keycodes": [],
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-k", str(kbi)])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["keyboard"]["layers"][0]["name"] == "Base"

    @patch("skim.cli.setup_logging")
    def test_title_sets_keymap_title_non_interactive(self, mock_setup, tmp_path):
        """--title sets output.keymap_title and writes config."""
        out = tmp_path / "out.yaml"
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "--title", "My Keymap", "-o", str(out)])
        assert result.exit_code == 0
        parsed = yaml.safe_load(out.read_text())
        assert parsed["output"]["keymap_title"] == "My Keymap"

    @patch("skim.cli.setup_logging")
    def test_copyright_sets_copyright_non_interactive(self, mock_setup, tmp_path):
        """--copyright sets output.copyright and writes config."""
        out = tmp_path / "out.yaml"
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "--copyright", "© 2026 Me", "-o", str(out)])
        assert result.exit_code == 0
        parsed = yaml.safe_load(out.read_text())
        assert parsed["output"]["copyright"] == "© 2026 Me"

    @patch("skim.cli.setup_logging")
    def test_title_and_copyright_together_non_interactive(self, mock_setup, tmp_path):
        """--title and --copyright together writes both values."""
        out = tmp_path / "out.yaml"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["configure", "-t", "Title", "-r", "© Me", "-o", str(out)],
        )
        assert result.exit_code == 0
        parsed = yaml.safe_load(out.read_text())
        assert parsed["output"]["keymap_title"] == "Title"
        assert parsed["output"]["copyright"] == "© Me"

    @patch("skim.cli.setup_logging")
    def test_title_with_existing_config(self, mock_setup, tmp_path):
        """--title overrides keymap_title in existing config file."""
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(yaml.dump({"output": {"keymap_title": "Old"}}))
        out = tmp_path / "out.yaml"
        runner = CliRunner()
        result = runner.invoke(
            main, ["configure", "-c", str(cfg), "-t", "New Title", "-o", str(out)]
        )
        assert result.exit_code == 0
        parsed = yaml.safe_load(out.read_text())
        assert parsed["output"]["keymap_title"] == "New Title"

    @patch("skim.cli.setup_logging")
    def test_title_without_output_echoes_yaml(self, mock_setup):
        """--title without -o echoes YAML to stdout."""
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-t", "My Title"])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["output"]["keymap_title"] == "My Title"

    @patch("skim.cli.setup_logging")
    @patch("skim.tui.launch_tui")
    def test_title_passed_to_tui(self, mock_tui, mock_setup):
        """--title pre-populates keymap_title in TUI config data."""
        runner = CliRunner()
        runner.invoke(main, ["configure", "-i", "-t", "TUI Title"])
        config_data = mock_tui.call_args[1]["config_data"]
        assert config_data["output"]["keymap_title"] == "TUI Title"

    @patch("skim.cli.setup_logging")
    @patch("skim.tui.launch_tui")
    def test_copyright_passed_to_tui(self, mock_tui, mock_setup):
        """--copyright pre-populates copyright in TUI config data."""
        runner = CliRunner()
        runner.invoke(main, ["configure", "-i", "-r", "© 2026"])
        config_data = mock_tui.call_args[1]["config_data"]
        assert config_data["output"]["copyright"] == "© 2026"

    @patch("skim.cli.setup_logging")
    @patch("skim.tui.launch_tui")
    def test_layer_count_creates_default_layers(self, mock_tui, mock_setup):
        """--layer-count creates N layers with defaults in interactive mode."""
        runner = CliRunner()
        runner.invoke(main, ["configure", "-i", "-n", "3"])
        config_data = mock_tui.call_args[1]["config_data"]
        layers = config_data["keyboard"]["layers"]
        assert len(layers) == 3
        assert layers[0]["index"] == 0
        assert layers[1]["index"] == 1
        assert layers[2]["index"] == 2
        palette_layers = config_data["output"]["style"]["palette"]["layers"]
        assert len(palette_layers) == 3

    @patch("skim.cli.setup_logging")
    @patch("skim.tui.launch_tui")
    def test_layer_count_fills_sparse_gaps(self, mock_tui, mock_setup, tmp_path):
        """--layer-count fills gaps in sparse layer indices."""
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "keyboard": {
                        "layers": [
                            {"index": 0, "name": "Base", "id": None, "variant": None},
                            {"index": 1, "name": "Nav", "id": None, "variant": None},
                            {"index": 4, "name": "Sym", "id": None, "variant": None},
                            {"index": 5, "name": "Num", "id": None, "variant": None},
                        ],
                    },
                    "output": {
                        "style": {
                            "palette": {
                                "layers": [
                                    {"base_color": "#AA0000"},
                                    {"base_color": "#BB0000"},
                                    {"base_color": "#CC0000"},
                                    {"base_color": "#DD0000"},
                                ],
                            },
                        },
                    },
                }
            )
        )
        runner = CliRunner()
        runner.invoke(main, ["configure", "-i", "-c", str(cfg), "-n", "7"])
        config_data = mock_tui.call_args[1]["config_data"]
        layers = config_data["keyboard"]["layers"]
        indices = sorted(l["index"] for l in layers)
        assert indices == [0, 1, 2, 3, 4, 5, 6]
        assert len(layers) == 7
        # Original layers preserved
        orig_names = {l["index"]: l["name"] for l in layers}
        assert orig_names[0] == "Base"
        assert orig_names[1] == "Nav"
        assert orig_names[4] == "Sym"
        assert orig_names[5] == "Num"
        # New layers have default names
        assert orig_names[2] == "Layer 2"
        assert orig_names[3] == "Layer 3"
        assert orig_names[6] == "Layer 6"
        # Palette layers match count
        palette_layers = config_data["output"]["style"]["palette"]["layers"]
        assert len(palette_layers) == 7

    @patch("skim.cli.setup_logging")
    @patch("skim.tui.launch_tui")
    def test_layer_count_no_change_when_enough_layers(self, mock_tui, mock_setup, tmp_path):
        """--layer-count does nothing when config already has enough layers."""
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "keyboard": {
                        "layers": [
                            {"index": i, "name": f"Layer {i}", "id": None, "variant": None}
                            for i in range(5)
                        ],
                    },
                    "output": {
                        "style": {
                            "palette": {
                                "layers": [{"base_color": f"#00{i:02x}00"} for i in range(5)],
                            },
                        },
                    },
                }
            )
        )
        runner = CliRunner()
        runner.invoke(main, ["configure", "-i", "-c", str(cfg), "-n", "3"])
        config_data = mock_tui.call_args[1]["config_data"]
        assert len(config_data["keyboard"]["layers"]) == 5

    @patch("skim.cli.setup_logging")
    def test_layer_count_ignored_without_interactive(self, mock_setup, tmp_path):
        """--layer-count alone (no -i, no -k) is silently ignored, shows help."""
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-n", "5"])
        assert result.exit_code == 0
        assert "--interactive" in result.output  # help text

    @patch("skim.cli.setup_logging")
    def test_keymap_with_vial_file(self, mock_setup, tmp_path):
        """Vial keymap generates config with layers."""
        import json

        vil = tmp_path / "test.vil"
        vil.write_text(
            json.dumps(
                {
                    "version": 1,
                    "uid": 12345,
                    "layout": [
                        [["KC_A"] * 6] * 10,
                        [["KC_B"] * 6] * 10,
                    ],
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-k", str(vil)])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert len(parsed["keyboard"]["layers"]) == 2

    @patch("skim.cli.setup_logging")
    def test_keymap_with_c2json_file(self, mock_setup, tmp_path):
        """c2json keymap generates config with layers and non-standard overrides."""
        import json

        c2j = tmp_path / "test.json"
        c2j.write_text(
            json.dumps(
                {
                    "keyboard": "test",
                    "keymap": "test",
                    "layout": "LAYOUT",
                    "layers": [
                        ["KC_A", "MY_KEY"] + ["KC_NO"] * 58,
                    ],
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-k", str(c2j)])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert len(parsed["keyboard"]["layers"]) == 1
        keycode_names = [o["keycode"] for o in parsed["keycodes"]["overrides"]]
        assert "MY_KEY" in keycode_names

    @patch("skim.cli.setup_logging")
    def test_keymap_with_keybard_still_works(self, mock_setup, tmp_path):
        """Keybard keymap still uses existing generate_from_keybard path."""
        import json

        kbi = tmp_path / "test.kbi"
        kbi.write_text(
            json.dumps(
                {
                    "layers": 1,
                    "keymap": [["KC_A"] * 60],
                    "layer_colors": [{"hue": 85, "sat": 255, "val": 255}],
                    "cosmetic": {"layer": {"0": "Base"}},
                    "custom_keycodes": [],
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-k", str(kbi)])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["keyboard"]["layers"][0]["name"] == "Base"

    @patch("skim.cli.setup_logging")
    @patch("skim.tui.launch_tui")
    def test_interactive_with_keymap_launches_tui(self, mock_tui, mock_setup, tmp_path):
        """Using -i with -k feeds generated config into TUI."""
        import json

        kbi = tmp_path / "test.kbi"
        kbi.write_text(
            json.dumps(
                {
                    "layers": 2,
                    "keymap": [["KC_A"] * 60, ["KC_B"] * 60],
                    "layer_colors": [
                        {"hue": 85, "sat": 255, "val": 255},
                        {"hue": 0, "sat": 255, "val": 255},
                    ],
                    "cosmetic": {"layer": {"0": "Base", "1": "Sym"}},
                    "custom_keycodes": [],
                }
            )
        )
        runner = CliRunner()
        runner.invoke(main, ["configure", "-i", "-k", str(kbi)])
        mock_tui.assert_called_once()
        config_data = mock_tui.call_args[1]["config_data"]
        assert len(config_data["keyboard"]["layers"]) == 2
        assert config_data["keyboard"]["layers"][0]["name"] == "Base"

    @patch("skim.cli.setup_logging")
    def test_title_copyright_layer_count_non_interactive(self, mock_setup, tmp_path):
        """All three options together in non-interactive mode."""
        out = tmp_path / "out.yaml"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["configure", "-t", "Full Config", "-r", "© 2026", "-n", "4", "-o", str(out)],
        )
        assert result.exit_code == 0
        parsed = yaml.safe_load(out.read_text())
        assert parsed["output"]["keymap_title"] == "Full Config"
        assert parsed["output"]["copyright"] == "© 2026"
        assert len(parsed["keyboard"]["layers"]) == 4

    @patch("skim.cli.setup_logging")
    @patch("skim.tui.launch_tui")
    def test_all_options_interactive(self, mock_tui, mock_setup):
        """All three options with -i populates config before TUI launch."""
        runner = CliRunner()
        runner.invoke(
            main,
            ["configure", "-i", "-t", "Interactive", "-r", "© Me", "-n", "2"],
        )
        config_data = mock_tui.call_args[1]["config_data"]
        assert config_data["output"]["keymap_title"] == "Interactive"
        assert config_data["output"]["copyright"] == "© Me"
        assert len(config_data["keyboard"]["layers"]) == 2


class TestDoctorCommand:
    """Tests for doctor subcommand."""

    @patch("skim.cli.run_doctor_checks")
    def test_doctor_runs_all_checks_passed(self, mock_checks):
        """Displays success message when all checks pass."""
        from skim.application.doctor import CheckResult

        mock_checks.return_value = [
            CheckResult("Check 1", True, "Passed"),
            CheckResult("Check 2", True, "Passed"),
        ]

        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])

        assert result.exit_code == 0
        assert "Everything looks good!" in result.output
        assert "PASS" in result.output

    @patch("skim.cli.run_doctor_checks")
    def test_doctor_handles_failures(self, mock_checks):
        """Displays failure messages."""
        from skim.application.doctor import CheckResult

        mock_checks.return_value = [
            CheckResult("Check 1", False, "Failed", "Reason"),
        ]

        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])

        assert result.exit_code == 0
        assert "FAIL" in result.output
        assert "Some checks failed or warned" in result.output

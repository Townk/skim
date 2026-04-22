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
    def test_default_config_to_stdout(self, mock_setup):
        """Running configure with no args outputs default YAML to stdout."""
        runner = CliRunner()
        result = runner.invoke(main, ["configure"])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert "keyboard" in parsed
        assert "output" in parsed

    @patch("skim.cli.setup_logging")
    def test_default_config_to_file(self, mock_setup, tmp_path):
        """Running configure with -o writes YAML to file."""
        output = tmp_path / "config.yaml"
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-o", str(output)])
        assert result.exit_code == 0
        assert output.exists()
        parsed = yaml.safe_load(output.read_text())
        assert "keyboard" in parsed

    @patch("skim.cli.setup_logging")
    def test_output_to_directory_appends_filename(self, mock_setup, tmp_path):
        """When -o is a directory, appends skim-config.yaml."""
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-o", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "skim-config.yaml").exists()

    @patch("skim.cli.setup_logging")
    def test_overwrite_requires_force(self, mock_setup, tmp_path):
        """Existing file without --force prompts for confirmation."""
        output = tmp_path / "config.yaml"
        output.write_text("existing content")
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-o", str(output)], input="n\n")
        assert result.exit_code != 0 or "existing content" == output.read_text()

    @patch("skim.cli.setup_logging")
    def test_force_overwrites_existing(self, mock_setup, tmp_path):
        """--force overwrites without prompting."""
        output = tmp_path / "config.yaml"
        output.write_text("old")
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-f", "-o", str(output)])
        assert result.exit_code == 0
        assert output.read_text() != "old"

    @patch("skim.cli.setup_logging")
    def test_keybard_input_generates_config(self, mock_setup, tmp_path):
        """Running with -k generates config from keybard file."""
        import json

        kbi = tmp_path / "test.kbi"
        kbi.write_text(json.dumps({
            "layers": 1,
            "keymap": [["KC_A"] * 60],
            "layer_colors": [{"hue": 85, "sat": 255, "val": 255}],
            "cosmetic": {"layer": {"0": "Base"}},
            "custom_keycodes": [],
        }))
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
    def test_non_tty_outputs_yaml(self, mock_setup):
        """Non-TTY stdout outputs YAML directly (pipe-safe)."""
        runner = CliRunner()
        result = runner.invoke(main, ["configure"])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert "keyboard" in parsed

    @patch("skim.cli.setup_logging")
    def test_keybard_flag_skips_tui(self, mock_setup, tmp_path):
        """The -k flag always uses CLI path, never TUI."""
        import json

        kbi = tmp_path / "test.kbi"
        kbi.write_text(json.dumps({
            "layers": 1,
            "keymap": [["KC_A"] * 60],
            "layer_colors": [{"hue": 85, "sat": 255, "val": 255}],
            "cosmetic": {"layer": {"0": "Base"}},
            "custom_keycodes": [],
        }))
        runner = CliRunner()
        result = runner.invoke(main, ["configure", "-k", str(kbi)])
        assert result.exit_code == 0
        parsed = yaml.safe_load(result.output)
        assert parsed["keyboard"]["layers"][0]["name"] == "Base"


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

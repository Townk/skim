"""Unit tests for CLI."""

from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from skim.ui.cli import AliasedGroup, main


class TestCli:
    """Test CLI commands."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_generator(self):
        with patch("skim.ui.cli.ImageGenerator") as mock:
            yield mock

    def test_generate_command_defaults(self, runner, mock_generator):
        """Test generate command with minimal arguments."""
        with runner.isolated_filesystem():
            with open("map.json", "w") as f:
                f.write("{}")

            result = runner.invoke(main, ["generate", "--keymap", "map.json"])

            # Debugging info if it fails
            if result.exit_code != 0:
                print(result.output)

            assert result.exit_code == 0
            mock_generator.assert_called_once()
            instance = mock_generator.return_value
            instance.generate.assert_called_once()

            # Verify default args
            call_args = instance.generate.call_args[1]
            assert call_args["layers"] is None  # Default None (all)

    def test_generate_command_stdin(self, runner, mock_generator):
        """Test generate command reading from stdin."""
        # Using '-' argument doesn't check file existence
        result = runner.invoke(main, ["generate", "-"], input='{"layers":[]}')

        if result.exit_code != 0:
            print(result.output)

        assert result.exit_code == 0
        instance = mock_generator.return_value
        call_args = instance.generate.call_args[1]
        assert call_args["keymap_content"] == '{"layers":[]}'
        assert call_args["keymap_path"] is None

    def test_generate_command_layers(self, runner, mock_generator):
        """Test generate command with layer options."""
        with runner.isolated_filesystem():
            with open("map.json", "w") as f:
                f.write("{}")

            result = runner.invoke(
                main, ["generate", "-k", "map.json", "-l", "1", "-l", "overview"]
            )

            if result.exit_code != 0:
                print(result.output)

            assert result.exit_code == 0
            instance = mock_generator.return_value
            call_args = instance.generate.call_args[1]
            # Should be list of strings
            assert "1" in call_args["layers"]
            assert "overview" in call_args["layers"]

    def test_generate_command_abbreviation(self, runner, mock_generator):
        """Test command abbreviation (gen, g)."""
        with runner.isolated_filesystem():
            with open("map.json", "w") as f:
                f.write("{}")

            result = runner.invoke(main, ["gen", "-k", "map.json"])
            if result.exit_code != 0:
                print(result.output)
            assert result.exit_code == 0

            result = runner.invoke(main, ["g", "-k", "map.json"])
            assert result.exit_code == 0

    @pytest.fixture
    def mock_config_gen(self):
        with patch("skim.ui.cli.ConfigGenerator") as mock:
            yield mock

    def test_configure_command_default(self, runner):
        """Test configure command without args (default template)."""
        # Mock reading default config asset
        with patch("pathlib.Path.read_text", return_value="default_content"):
            result = runner.invoke(main, ["configure"])

        assert result.exit_code == 0
        assert "default_content" in result.output

    def test_configure_command_with_keymap(self, runner, mock_config_gen):
        """Test configure command with input keymap."""
        with runner.isolated_filesystem():
            with open("input.kbi", "w") as f:
                f.write("{}")

            mock_gen_instance = mock_config_gen.return_value
            mock_gen_instance.generate.return_value = "generated_config"

            result = runner.invoke(main, ["configure", "-k", "input.kbi"])

            assert result.exit_code == 0
            assert "generated_config" in result.output
            mock_gen_instance.generate.assert_called_once_with("{}", None, None, None)

    def test_configure_command_with_qmk_header(self, runner, mock_config_gen):
        """Test configure command with QMK header."""
        with runner.isolated_filesystem():
            with open("input.kbi", "w") as f:
                f.write("{}")
            with open("color.h", "w") as f:
                f.write("#define HSV_RED 0,255,255")

            mock_gen_instance = mock_config_gen.return_value
            mock_gen_instance.generate.return_value = "generated_config"

            result = runner.invoke(
                main, ["configure", "-k", "input.kbi", "-C", "color.h"]
            )

            assert result.exit_code == 0
            mock_gen_instance.generate.assert_called_once_with(
                "{}", "#define HSV_RED 0,255,255", None, None
            )

    def test_configure_command_output_file(self, runner, mock_config_gen):
        """Test configure command writing to file."""
        with runner.isolated_filesystem():
            with open("input.kbi", "w") as f:
                f.write("{}")

            mock_gen_instance = mock_config_gen.return_value
            mock_gen_instance.generate.return_value = "generated_config"

            result = runner.invoke(
                main, ["configure", "-k", "input.kbi", "-o", "out.yaml"]
            )

            assert result.exit_code == 0
            assert "Configuration written to out.yaml" in result.output

            with open("out.yaml") as f:
                assert f.read() == "generated_config"

    def test_generate_stdin_overrides_keymap(self, runner, mock_generator):
        """Test that stdin marker '-' overrides --keymap argument."""
        # This hits line 101: if keymap: keymap = None
        with runner.isolated_filesystem():
            # Create dummy file to satisfy Click's exists=True check
            with open("ignored.json", "w") as f:
                f.write("{}")

            result = runner.invoke(
                main, ["generate", "-", "-k", "ignored.json"], input='{"layers":[]}'
            )

            assert result.exit_code == 0
            instance = mock_generator.return_value
            call_args = instance.generate.call_args[1]
            assert call_args["keymap_path"] is None
            assert call_args["keymap_content"] == '{"layers":[]}'

    def test_configure_exception_handling(self, runner, mock_config_gen):
        """Test configure command handles exceptions gracefully."""
        mock_config_gen.return_value.generate.side_effect = RuntimeError("Boom")

        # Must provide input to trigger generate
        with runner.isolated_filesystem():
            with open("input.kbi", "w") as f:
                f.write("{}")
            result = runner.invoke(main, ["configure", "-k", "input.kbi"])

        assert result.exit_code == 1
        assert "Error: Boom" in result.output

    def test_aliased_group_ambiguity(self, runner):
        """Test ambiguous command abbreviation."""

        @click.group(cls=AliasedGroup)
        def dummy_group():
            pass

        @dummy_group.command()
        def command_one():
            pass

        @dummy_group.command()
        def command_two():
            pass

        # 'command' matches both -> fail
        result = runner.invoke(dummy_group, ["command"])
        assert result.exit_code != 0
        assert "Too many matches" in result.output

    def test_generate_no_stdin_tty(self, runner):
        """Test generate fails when no input provided and TTY is active."""
        # Mock sys.stdin.isatty to True
        with patch("sys.stdin.isatty", return_value=True):
            result = runner.invoke(main, ["generate"])

            assert result.exit_code == 1
            assert "Error: No keymap provided" in result.output

    def test_configure_file_exists_error(self, runner, mock_config_gen):
        """Test error when output file exists and no force flag."""
        with runner.isolated_filesystem():
            with open("existing.yaml", "w") as f:
                f.write("old")

            mock_gen_instance = mock_config_gen.return_value
            mock_gen_instance.generate.return_value = "new"

            result = runner.invoke(main, ["configure", "-o", "existing.yaml"])

            assert result.exit_code == 1
            assert "already exists" in result.output
            assert "Use --force" in result.output

    def test_configure_command_flags(self, runner, mock_config_gen):
        """Test configure command with adjustment flags."""
        with runner.isolated_filesystem():
            with open("input.kbi", "w") as f:
                f.write("{}")

            mock_gen_instance = mock_config_gen.return_value
            mock_gen_instance.generate.return_value = "config"

            result = runner.invoke(
                main, ["configure", "-k", "input.kbi", "-l", "0.5", "-s", "0.8"]
            )

            assert result.exit_code == 0
            mock_gen_instance.generate.assert_called_once_with("{}", None, 0.5, 0.8)

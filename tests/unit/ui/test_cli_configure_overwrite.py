from pathlib import Path

from click.testing import CliRunner

from skim.ui.cli import configure


class TestCliConfigureOverwrite:
    def test_configure_overwrite_prompt_confirm(self):
        """Test that configure prompts for overwrite when file exists and user confirms."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            output_file = Path("config.yaml")
            output_file.write_text("existing content")

            # Setup input: "y" for confirmation
            result = runner.invoke(configure, ["-o", "config.yaml"], input="y\n")

            assert result.exit_code == 0
            assert (
                "File config.yaml already exists. Do you want to overwrite?"
                in result.output
            )
            assert "Configuration written to config.yaml" in result.output

            # Verify file was overwritten (default config content should replace "existing content")
            content = output_file.read_text()
            assert "existing content" not in content
            assert "layers:" in content

    def test_configure_overwrite_prompt_abort(self):
        """Test that configure prompts for overwrite when file exists and user aborts."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            output_file = Path("config.yaml")
            output_file.write_text("existing content")

            # Setup input: "n" for abort
            result = runner.invoke(configure, ["-o", "config.yaml"], input="n\n")

            assert result.exit_code == 1
            assert (
                "File config.yaml already exists. Do you want to overwrite?"
                in result.output
            )
            assert "Aborted." in result.output

            # Verify file was NOT overwritten
            assert output_file.read_text() == "existing content"

    def test_configure_force_overwrite(self):
        """Test that --force bypasses overwrite prompt."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            output_file = Path("config.yaml")
            output_file.write_text("existing content")

            result = runner.invoke(configure, ["-o", "config.yaml", "--force"])

            assert result.exit_code == 0
            assert "overwrite?" not in result.output
            assert "Configuration written to config.yaml" in result.output

            # Verify file was overwritten
            content = output_file.read_text()
            assert "existing content" not in content

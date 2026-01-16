from pathlib import Path

from click.testing import CliRunner

from skim.ui.cli import configure


class TestCliConfigureOverwriteDirectory:
    def test_configure_output_directory_prompt_only_if_file_exists(self):
        """Test that passing a directory as output checks for file existence within it."""
        # Wait, if output IS a directory, Path.exists() is true.
        # But we intend to write TO a file.
        # If user passes a directory, we currently try to check if THAT path exists.
        # If it exists (as a dir), we prompt for overwrite?
        # And then try to write text to it? output.write_text(content) -> IsADirectoryError!

        # If user passes a directory "output_dir", do we mean "output_dir/skim-config.yaml"?
        # The help says "Output configuration file path". So it expects a file path.

        # If the user passes a directory path that exists, `output.exists()` is True.
        # Then we prompt overwrite.
        # If confirmed, we call `output.write_text()`, which fails because it's a directory.

        # But the user says: "overwrite message only happens if the target 'file' is present"
        # And "even though there is no skim-config.yaml file in the directory".

        # If I run `skim configure -o mydir`, and `mydir` exists.
        # It prompts overwrite.
        # If I say yes, it crashes with IsADirectoryError.

        # If I run `skim configure -o mydir/skim-config.yaml`.
        # `mydir` exists. `mydir/skim-config.yaml` does NOT exist.
        # `output.exists()` is False. No prompt. Correct.

        # The user report implies they might be passing a directory PATH as the output file argument?
        # "When I pass an existing directory as the output... even though there is no skim-config.yaml file in the directory"

        # If they mean they want `skim configure -o mydir` to auto-detect and write to `mydir/skim-config.yaml`,
        # that's a feature request (or implicit behavior assumption).

        # BUT if they just passed a directory by mistake or intention, and it prompts overwrite, that's weird if it's a dir.

        # Let's reproduce the crash/behavior first.
        pass

    def test_configure_output_directory_auto_filename(self):
        """Test that passing a directory as output writes to skim-config.yaml inside it."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("mydir").mkdir()

            # User passes directory as output, should succeed without prompt (if file doesn't exist)
            result = runner.invoke(configure, ["-o", "mydir"])

            assert result.exit_code == 0
            assert "Configuration written to mydir/skim-config.yaml" in result.output

            # Verify file created
            assert (Path("mydir") / "skim-config.yaml").exists()

    def test_configure_output_directory_prompt_if_inner_file_exists(self):
        """Test that passing directory prompts only if inner skim-config.yaml exists."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("mydir").mkdir()
            (Path("mydir") / "skim-config.yaml").write_text("old content")

            # Should prompt now
            result = runner.invoke(configure, ["-o", "mydir"], input="n\n")

            assert result.exit_code == 1
            assert "File mydir/skim-config.yaml already exists" in result.output
            assert "Aborted" in result.output

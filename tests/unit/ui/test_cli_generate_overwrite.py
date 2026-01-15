"""Tests for the CLI generate command overwrite protection."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from skim.ui.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_generator():
    with patch("skim.ui.cli.ImageGenerator") as mock:
        yield mock


def test_generate_check_overwrite_prompt_confirm(runner, mock_generator):
    """Test that user is prompted and can confirm overwrite."""
    instance = mock_generator.return_value
    # First call raises FileExistsError (check), second returns None (actual gen)
    instance.generate.side_effect = [FileExistsError("Files exist"), None]

    with runner.isolated_filesystem():
        with open("dummy.kbi", "w") as f:
            f.write("{}")

        result = runner.invoke(
            main,
            ["generate", "--keymap", "dummy.kbi", "--output-dir", "out"],
            input="y\n",
        )

    if result.exit_code != 0:
        print(result.output)

    assert result.exit_code == 0
    assert "Do you want to overwrite?" in result.output
    # Should call generate twice: once for check, once for real
    assert instance.generate.call_count == 2

    # Verify calls
    # Call 1: Check overwrite
    instance.generate.assert_any_call(
        keymap_path=Path("dummy.kbi"),
        keymap_content=None,
        layers=None,
        check_overwrite=True,
    )
    # Call 2: Actual generation
    instance.generate.assert_any_call(
        keymap_path=Path("dummy.kbi"),
        keymap_content=None,
        layers=None,
    )


def test_generate_check_overwrite_prompt_abort(runner, mock_generator):
    """Test that user is prompted and can abort overwrite."""
    instance = mock_generator.return_value
    instance.generate.side_effect = [FileExistsError("Files exist"), None]

    with runner.isolated_filesystem():
        with open("dummy.kbi", "w") as f:
            f.write("{}")

        result = runner.invoke(
            main,
            ["generate", "--keymap", "dummy.kbi", "--output-dir", "out"],
            input="n\n",
        )

    assert result.exit_code == 1
    assert "Do you want to overwrite?" in result.output
    assert "Aborted." in result.output
    # Should call generate only once (the check)
    assert instance.generate.call_count == 1
    instance.generate.assert_called_with(
        keymap_path=Path("dummy.kbi"),
        keymap_content=None,
        layers=None,
        check_overwrite=True,
    )


def test_generate_force_flag(runner, mock_generator):
    """Test that --force skips the check."""
    instance = mock_generator.return_value

    with runner.isolated_filesystem():
        with open("dummy.kbi", "w") as f:
            f.write("{}")

        result = runner.invoke(
            main,
            ["generate", "--keymap", "dummy.kbi", "--output-dir", "out", "--force"],
        )

    if result.exit_code != 0:
        print(result.output)

    assert result.exit_code == 0
    # Should call generate only once (the real generation, no check)
    assert instance.generate.call_count == 1
    instance.generate.assert_called_with(
        keymap_path=Path("dummy.kbi"),
        keymap_content=None,
        layers=None,
    )

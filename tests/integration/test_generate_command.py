"""Integration tests for skim generate command."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from skim.ui.cli import main


class TestIntegrationGenerate:
    """End-to-end tests for generation flow using sample files."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def samples_dir(self):
        # Locate samples directory relative to project root (parent of skim dir)
        # We are in skim/tests/integration
        # __file__ is skim/tests/integration/test_generate_command.py
        # root is ../../..
        return (
            Path(__file__).parent.parent.parent.parent / "docs/spec/samples/keymaps"
        ).resolve()

    @pytest.fixture
    def mock_typst_compile(self):
        """Mock the actual typst compilation to avoid binary dependency."""
        with patch("typst.compile") as mock:
            yield mock

    def test_generate_c2json(self, runner, samples_dir, mock_typst_compile):
        """Test generation from c2json sample."""
        sample_path = samples_dir / "c2json-sample.json"
        if not sample_path.exists():
            pytest.skip(f"Sample file not found: {sample_path}")

        with runner.isolated_filesystem():
            # Copy sample to isolated env or reference absolute path
            # Reference absolute path is easier
            result = runner.invoke(main, ["generate", "-k", str(sample_path)])

            if result.exit_code != 0:
                print(result.output)
            assert result.exit_code == 0

            # Verify typst.compile was called
            assert mock_typst_compile.called

            # Check inputs passed to typst
            # sys_inputs should contain "keymap" JSON string
            call_kwargs = mock_typst_compile.call_args[1]
            sys_inputs = call_kwargs["sys_inputs"]
            keymap_data = json.loads(sys_inputs["keymap"])

            # c2json-sample.json has 8 layers
            # Verify structure
            assert "layers" in keymap_data
            assert len(keymap_data["layers"]) == 8
            # Verify a known key from sample (Layer 0, Key 0 is KC_N)
            # Note: KeycodeTransformer transforms "KC_N" -> "N"
            assert keymap_data["layers"][0]["labels"][0][0] == "N"

    def test_generate_vial(self, runner, samples_dir, mock_typst_compile):
        """Test generation from vial sample."""
        sample_path = samples_dir / "vial-sample.vil"
        if not sample_path.exists():
            pytest.skip(f"Sample file not found: {sample_path}")

        with runner.isolated_filesystem():
            result = runner.invoke(main, ["generate", "-k", str(sample_path)])

            if result.exit_code != 0:
                print(result.output)
            assert result.exit_code == 0

            assert mock_typst_compile.called
            keymap_data = json.loads(
                mock_typst_compile.call_args[1]["sys_inputs"]["keymap"]
            )

            # vial-sample.vil has 16 layers (from layout array length)
            assert len(keymap_data["layers"]) == 16

            # Vial sample Layer 0, first cluster first key: "MO(5)"
            # KeycodeTransformer: "MO(5)" -> "5 " (icon depends on mapping)
            # Just check it's not empty
            assert keymap_data["layers"][0]["labels"][0][0] != ""

    def test_generate_keybard(self, runner, samples_dir, mock_typst_compile):
        """Test generation from keybard sample."""
        sample_path = samples_dir / "keybard-sample.kbi"
        if not sample_path.exists():
            pytest.skip(f"Sample file not found: {sample_path}")

        with runner.isolated_filesystem():
            result = runner.invoke(main, ["generate", "-k", str(sample_path)])

            if result.exit_code != 0:
                print(result.output)
            assert result.exit_code == 0

            assert mock_typst_compile.called
            keymap_data = json.loads(
                mock_typst_compile.call_args[1]["sys_inputs"]["keymap"]
            )

            # keybard-sample.kbi "layers": 16
            # But "keymap" array has 16 entries.
            assert len(keymap_data["layers"]) == 16

            # Layer 0 key 0 is "MO(5)" in the file too
            assert keymap_data["layers"][0]["labels"][0][0] != ""

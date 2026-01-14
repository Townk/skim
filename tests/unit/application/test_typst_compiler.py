"""Unit tests for TypstCompiler."""

from pathlib import Path
from unittest.mock import patch

import pytest

from skim.application.typst_compiler import TypstCompiler


class TestTypstCompiler:
    """Test Typst compiler wrapper."""

    @pytest.fixture
    def mock_compile(self):
        """Mock typst.compile function."""
        with patch("typst.compile") as mock:
            yield mock

    def test_compile_calls_typst_correctly(self, mock_compile):
        """Verify typst.compile is called with correct arguments."""
        compiler = TypstCompiler()

        input_path = Path("template.typ")
        output_path = Path("output.svg")
        sys_inputs = {"key": "value"}
        font_path = Path("fonts")

        compiler.compile(
            input_path=input_path,
            output_path=output_path,
            sys_inputs=sys_inputs,
            font_paths=[font_path],
        )

        mock_compile.assert_called_once_with(
            input=input_path,
            output=output_path,
            ppi=120,
            font_paths=[font_path],
            ignore_system_fonts=True,
            sys_inputs=sys_inputs,
        )

    def test_compile_handles_string_paths(self, mock_compile):
        """Verify string paths are converted or handled."""
        compiler = TypstCompiler()

        compiler.compile(
            input_path="template.typ",
            output_path="output.svg",
            sys_inputs={},
            font_paths=["fonts"],
        )

        # Check if called (args might be Path objects or strings depending on implementation)
        mock_compile.assert_called_once()
        args = mock_compile.call_args[1]
        assert str(args["input"]) == "template.typ"
        assert str(args["output"]) == "output.svg"

    def test_compile_error_propagation(self, mock_compile):
        """Verify errors from typst are propagated."""
        mock_compile.side_effect = RuntimeError("Typst error")

        compiler = TypstCompiler()

        with pytest.raises(RuntimeError, match="Typst error"):
            compiler.compile(Path("in.typ"), Path("out.svg"), {})

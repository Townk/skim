"""Wrapper for the Typst document compiler.

This module provides the :class:`TypstCompiler` which wraps the typst-py library
to compile Typst documents into output formats (SVG, PNG, PDF). The compiler
is used to render keymap visualization templates with layer data.

Example:
    Compiling a Typst template::

        from skim.application.typst_compiler import TypstCompiler
        from pathlib import Path
        import json

        compiler = TypstCompiler()
        compiler.compile(
            input_path=Path("template.typ"),
            output_path=Path("output.svg"),
            sys_inputs={"keymap": json.dumps(keymap_data)},
            font_paths=[Path("fonts/")],
        )
"""

from pathlib import Path

import typst


class TypstCompiler:
    """Wrapper around the typst-py compiler for document rendering.

    Provides a simplified interface to the Typst compilation engine with
    support for custom fonts and system inputs. The compiler handles
    the conversion of Typst markup documents to various output formats.

    The wrapper configures Typst with settings optimized for skim's use case:
        - Fixed PPI (120) for consistent image sizing
        - System fonts ignored for reproducible output
        - Custom font paths for NerdFont icon support

    Example:
        >>> compiler = TypstCompiler()
        >>> compiler.compile(
        ...     input_path="keymap.typ",
        ...     output_path="keymap.svg",
        ...     sys_inputs={"data": '{"layers": [...]}'},
        ... )
    """

    def compile(
        self,
        input_path: str | Path,
        output_path: str | Path,
        sys_inputs: dict[str, str],
        font_paths: list[str | Path] | None = None,
    ) -> None:
        """Compile a Typst document to an output file.

        Renders the input Typst template with the provided system inputs
        and writes the result to the output path. The output format is
        determined by the output file extension (.svg, .png, or .pdf).

        Args:
            input_path: Path to the .typ input file containing the template.
            output_path: Path for the generated output file. May include
                ``{p}`` placeholder for page numbers when generating
                multi-page output (e.g., "layer-{p}.svg").
            sys_inputs: Dictionary of string key-value pairs passed to the
                Typst template as system inputs. The template accesses these
                via ``sys.inputs``. Values should be JSON-serialized strings.
            font_paths: Optional list of directories to search for font files.
                Fonts in these directories are available to the Typst template.

        Raises:
            FileNotFoundError: If the input file doesn't exist.
            typst.TypstError: If compilation fails due to template errors.

        Example:
            >>> compiler.compile(
            ...     input_path="keymap-layers.typ",
            ...     output_path="output/layer-{p}.svg",
            ...     sys_inputs={
            ...         "keymap": '{"layers": [...]}',
            ...         "appearance": '{"colors": {...}}',
            ...     },
            ...     font_paths=["assets/fonts"],
            ... )
        """
        if font_paths is None:
            font_paths = []

        typst.compile(
            input=Path(input_path),
            output=Path(output_path),
            ppi=120,
            font_paths=[Path(p) for p in font_paths],
            ignore_system_fonts=True,
            sys_inputs=sys_inputs,
        )

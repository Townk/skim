# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Ambient render-time context for the composable framework.

A :class:`RenderContext` carries the inputs every composable in an
image needs but few want to accept as explicit kwargs: the user's
:class:`SkimConfig`, the parsed :class:`SvalboardKeymap`, a resolved
:class:`Theme`, and a :class:`DocumentMetrics` bundle of cross-cutting
sizes (margins, paddings, base scale).

The context is set once at the entry point of a render via
:func:`using_render_context` and read inside composables via the
``ctx`` parameter the :func:`CtxComposable` decorator injects from a
``ContextVar``. Composables never *create* a context themselves;
they're handed one by their decorator at call time.

Why a context-var instead of an explicit param?
-----------------------------------------------

Threading ``ctx`` through every composable's kwargs would force every
parent to forward it to every child. Using a ``ContextVar`` keeps the
data flow implicit but well-scoped: pyright sees ``ctx: RenderContext``
on each composable's signature (the decorator strips it from the
public-facing call shape), and the context is always the active one
for the dynamic call stack. Tests can construct an undecorated
composable's underlying builder and pass a mock ``ctx`` directly.

Scaling
-------

The standalone special-keys images render at a 1.5× scale relative
to per-layer images. :meth:`RenderContext.build` accepts a ``scale``
factor and produces a config copy whose ``layout.width`` is already
multiplied so every downstream metric (computed from ``doc_width``)
scales uniformly. Composables don't need to know about scaling — they
read ``ctx.config.output.layout.width`` and get the right value for
the current image.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from skim.data import Palette, SkimConfig, SvalboardKeymap
from skim.domain import SvalboardTargetKey

from .text import Font

# ---------------------------------------------------------------------------
# Theme & typography
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class TextStyle:
    """A reusable text-style preset (the unit a :class:`Typography` registry
    collects).

    The decoupled flat fields mirror what an SVG ``<text>`` element
    needs at paint time. Composables that emit text should accept a
    :class:`TextStyle` (or read one off ``ctx.theme.typography``)
    instead of re-spelling these fields per call site.

    Letter spacing is intentionally NOT a :class:`TextStyle` field —
    it's a per-glyph-run treatment used in only a handful of places
    (section titles, the ``N ENTRIES`` count, action key labels) and
    pinning it to the preset would bake one site's tracking into every
    preset that shared the font.
    """

    font: Font
    size: float
    weight: int = 400
    color: str = "black"


@dataclass(frozen=True, slots=True, kw_only=True)
class Typography:
    """The registry of every :class:`TextStyle` an image render uses.

    One :class:`Typography` instance lives on the :class:`Theme` so
    composables can grab named presets via
    ``ctx.theme.typography.<preset>``. New presets are added as
    composables migrate; the rule is "only add a preset when at least
    two composables would reference it" (keeps the registry from
    becoming a junk drawer).
    """

    title: TextStyle
    """Keymap title — large, thin, top-left of the image."""

    copyright: TextStyle
    """Footer copyright text — small, faded, right-aligned."""

    # Future presets:
    #   section_title: TextStyle
    #   chip_label: TextStyle


@dataclass(frozen=True, slots=True, kw_only=True)
class Theme:
    """Resolved colour palette + typography registry for a single render."""

    palette: Palette
    typography: Typography

    @classmethod
    def resolve(
        cls,
        config: SkimConfig,
        *,
        title_font_size: float,
        copyright_font_size: float,
    ) -> "Theme":
        """Resolve the theme from a config + per-image font sizes.

        ``title_font_size`` and ``copyright_font_size`` both come from
        the overview's badge math (``HeaderDims``) so the same sizes
        flow through every image variant — title and footer stay
        visually consistent across per-layer, overview, macros,
        tap-dances and special-keys renders.
        """
        palette = config.output.style.palette
        return cls(
            palette=palette,
            typography=Typography(
                title=TextStyle(
                    font=Font.TITLE,
                    size=title_font_size,
                    color=palette.text_color,
                ),
                copyright=TextStyle(
                    font=Font.FINGER_KEY,
                    size=copyright_font_size,
                    color=palette.text_color,
                ),
            ),
        )


# ---------------------------------------------------------------------------
# Document-wide metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentMetrics:
    """Cross-cutting sizes shared by every composable in one image.

    These are the metrics that aren't owned by any single component —
    page margins, content padding, the base scale factor, the rounded
    border's radius. Composables that need them read
    ``ctx.document_metrics.x`` instead of re-deriving from config each
    time.

    Component-specific metrics (cell width, chip width, font sizes
    used by particular composables) do NOT live here — those belong on
    the component itself, exposed via ``MetricsComponent[M].metrics``.
    """

    doc_width: float
    """The document width the image lays out against."""

    margin: float
    """Outer canvas → border gap (matches ``KeymapLayoutMetrics.margin``)."""

    padding: float
    """Outer canvas → content gap (matches ``_outer_padding``)."""

    bottom_inset: float
    """Bottom canvas → content gap (= ``inset + margin``)."""

    border_radius: float | None
    """Rounded-rectangle radius for the outer border, or ``None`` when off."""

    column_gap: float
    """Horizontal gap between side-by-side sections (e.g. macros + tap-dance)."""

    @classmethod
    def from_config(cls, config: SkimConfig) -> "DocumentMetrics":
        """Compute document-wide metrics from a config."""
        from .layout import KeymapLayoutMetrics
        from .legend import _LegendGeometry
        from .overview_layout import _outer_padding

        metrics = KeymapLayoutMetrics.from_config(config)
        legend_geom = _LegendGeometry.for_doc_width(config.output.layout.width)
        border = config.output.style.border
        return cls(
            doc_width=config.output.layout.width,
            margin=metrics.margin,
            padding=_outer_padding(metrics),
            bottom_inset=metrics.inset + metrics.margin,
            border_radius=border.radius if border else None,
            column_gap=legend_geom.column_gap,
        )


# ---------------------------------------------------------------------------
# RenderContext + ContextVar plumbing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderContext:
    """Ambient render-time inputs for one image.

    Holds the canonical inputs (``config``, ``keymap``) plus the
    derived bundles (``theme``, ``document_metrics``) that get
    computed once at context construction and read by every
    composable in the image.

    Construct via :meth:`build` — the constructor stays ``__init__``
    so tests can build mock contexts without going through the
    config-derivation path.
    """

    config: SkimConfig
    keymap: SvalboardKeymap[SvalboardTargetKey]
    theme: Theme
    document_metrics: DocumentMetrics

    @classmethod
    def build(
        cls,
        config: SkimConfig,
        keymap: SvalboardKeymap[SvalboardTargetKey],
    ) -> "RenderContext":
        """Resolve a context from raw inputs.

        Composables that want to render parts of themselves at a
        non-default scale (e.g. the ``MACROS`` and ``TAP-DANCE``
        bodies in the standalone special-keys images) accept a
        per-component ``scale`` kwarg and apply it locally — the
        :class:`RenderContext` itself stays at the user's actual
        ``config.output.layout.width`` so the title and footer don't
        get pulled along by the body's zoom.
        """
        # Local import — :mod:`overview` imports from this module
        # transitively at startup; importing it eagerly would create a
        # circular import cycle.
        from .overview import compute_header_dims

        header_dims = compute_header_dims(config, keymap)
        return cls(
            config=config,
            keymap=keymap,
            theme=Theme.resolve(
                config,
                title_font_size=header_dims.title_font_size,
                copyright_font_size=header_dims.copyright_font_size,
            ),
            document_metrics=DocumentMetrics.from_config(config),
        )


# Active render context — set via :func:`using_render_context`.
# Composables decorated with ``@CtxComposable`` read from this var
# and receive the context as the first positional argument.
_render_ctx: ContextVar[RenderContext] = ContextVar("skim_render_ctx")


@contextmanager
def using_render_context(ctx: RenderContext) -> Iterator[RenderContext]:
    """Push ``ctx`` as the active render context for the duration of the block.

    Composables decorated with ``@CtxComposable`` read the context
    from a :class:`ContextVar` set by this manager. Calling a
    ``@CtxComposable`` outside of a ``using_render_context`` block
    raises :class:`LookupError` at the entry — the failure is loud and
    obvious, not silent or subtle.

    Nested contexts are supported (each ``using_render_context`` pushes
    a new value and restores the previous one on exit) so a child
    render can shadow the parent's context if needed.
    """
    token = _render_ctx.set(ctx)
    try:
        yield ctx
    finally:
        _render_ctx.reset(token)


def current_render_context() -> RenderContext:
    """Return the active render context, or raise ``LookupError`` if none.

    Composables decorated with ``@CtxComposable`` go through this
    helper indirectly — the decorator pulls the context and passes it
    as the first positional argument so composable bodies declare
    ``def MyComposable(ctx, ...)`` and never call this helper directly.
    """
    return _render_ctx.get()


__all__ = [
    "DocumentMetrics",
    "RenderContext",
    "TextStyle",
    "Theme",
    "Typography",
    "current_render_context",
    "using_render_context",
]

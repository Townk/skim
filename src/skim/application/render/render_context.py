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

from skim.data import LayerColor, SkimConfig, SvalboardKeymap
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
class RenderPalette:
    """Render-time palette — chrome colours + per-layer colours keyed
    by QMK firmware index.

    The data-layer :class:`Palette` stores per-layer colours as a
    position-keyed tuple (``palette.layers[0]`` etc.). The render
    stack doesn't care about array positions; it always identifies
    a layer by its **QMK firmware index** (the int that ends up on
    a key's ``layer_switch`` field after the keymap is parsed).
    Symbolic layer ids (``"_NAV"``, ``"_SYS"``) are a *config-time*
    concept — the user spells them in their YAML, the parser
    translates them to firmware ints, and by the time anything
    reaches the render stack we only ever see ints.

    Re-keying by QMK firmware index makes every render-stack lookup
    a single dict access: ``palette.layers[key.layer_switch]`` for
    indicator badges or tinted layer-switch keys; same for the
    cluster's own layer (``palette.layers[layer_qmk_index]``).

    Document-chrome colours (background, text, neutral, etc.) live
    on this class verbatim from the data :class:`Palette` — saves
    the render stack from having to thread two palette references
    through every call site.
    """

    background_color: str
    text_color: str
    key_label_color: str
    neutral_color: str
    border_color: str
    macro_color: str
    tap_dance_color: str
    layers: dict[int, LayerColor]
    """Per-layer colours keyed by QMK firmware index. Direct lookup
    for any int the render stack handles — both the cluster's own
    ``layer_qmk_index`` argument and the ``key.layer_switch`` int on
    layer-switch keys."""

    @classmethod
    def from_config(cls, config: SkimConfig) -> "RenderPalette":
        """Build the render palette by zipping the data palette's
        position-indexed layers with the keyboard config's layer list.

        ``config.output.style.palette.layers[i]`` and
        ``config.keyboard.layers[i]`` are aligned by position — the
        i-th palette colour belongs to the i-th configured layer. We
        re-key by ``KeyboardLayer.index`` (the QMK firmware index)
        so the render stack never touches array positions again.
        """
        data_palette = config.output.style.palette
        keyboard_layers = config.keyboard.layers
        layers: dict[int, LayerColor] = {
            kb_layer.index: layer_color
            for kb_layer, layer_color in zip(keyboard_layers, data_palette.layers, strict=False)
        }
        return cls(
            background_color=data_palette.background_color,
            text_color=data_palette.text_color,
            key_label_color=data_palette.key_label_color,
            neutral_color=data_palette.neutral_color,
            border_color=data_palette.border_color,
            macro_color=data_palette.macro_color,
            tap_dance_color=data_palette.tap_dance_color,
            layers=layers,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Theme:
    """Resolved colour palette + typography registry for a single render."""

    palette: RenderPalette
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
        palette = RenderPalette.from_config(config)
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


# Width-proportional fallback for ``Spacing.inset`` when the user
# hasn't set it explicitly. Matches the canonical 40-unit gap at the
# canonical 1600-unit document width — the value the legacy
# ``_outer_padding`` floor was tuned against.
_INSET_DEFAULT_RATIO = 40.0 / 1600.0

# Per-doc-width ratios for the four cross-cutting spacings populated
# on :class:`DocumentMetrics`. Owned here so :meth:`from_config` no
# longer reaches into the legacy ``_LegendGeometry``. The values mirror
# the same ratios in ``legend.py`` (which still uses them for the
# overview's imperative path); when the overview migrates the legend
# copies retire and these stay.
_COLUMN_GAP_RATIO = 40.0 / 1600.0
_SECTION_SPACING_RATIO = 24.0 / 1600.0
_TABLE_HEADER_SPACING_RATIO = 12.0 / 1600.0
_TABLE_COL_SPACING_RATIO = 6.0 / 1600.0
_TABLE_ROW_SPACING_RATIO = 9.0 / 1600.0


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentMetrics:
    """Cross-cutting sizes shared by every composable in one image.

    The canonical source for the document's outer-chrome metrics —
    margin, border stroke thickness and inset. Composables (and
    ``KeymapLayoutMetrics``) read these from a built
    :class:`DocumentMetrics` instead of resolving them from config
    independently, so a single resolution rule applies everywhere.

    Component-specific metrics (cell width, chip width, font sizes
    used by particular composables) do NOT live here — those belong on
    the component itself, exposed via ``MetricsComponent[M].metrics``.
    """

    doc_width: float
    """The document width the image lays out against."""

    margin: float
    """Canvas edge → border-line gap.

    Resolves to ``output.layout.spacing.margin`` when set, ``0``
    otherwise. When a border is configured the resolved margin is
    floored at ``border.width / 2`` so the centred stroke isn't
    clipped by the canvas edge.
    """

    border_width: float
    """Border stroke thickness, or ``0`` when no border is configured."""

    inset: float
    """Border line → content gap, applied uniformly on all four sides.

    Also doubles as the inter-element gap inside the document's main
    Column (and as the basis for header / footer breathing room).
    Resolves to ``output.layout.spacing.inset`` when set, otherwise
    falls back to ``doc_width * 40/1600`` — the historical 40-unit
    gap at the canonical 1600-unit document width.
    """

    border_radius: float | None
    """Rounded-rectangle radius for the outer border, or ``None`` when off."""

    column_gap: float
    """Horizontal gap between side-by-side sections (e.g. macros + tap-dance)."""

    section_spacing: float
    """Vertical gap between a section title strip and the section's body
    (e.g. between the ``MACROS`` rule and its first row)."""

    table_header_spacing: float
    """Gap between a table header and the content it labels.

    Used universally:

    * Column header text → first data row.
    * Row header (e.g. the TD chip with name+id) → row's content.
    * Named-macro name strip → the macro's pill row.
    * Macro ID chip → its action pills.
    """

    table_col_spacing: float
    """Horizontal gap between adjacent table columns (TD cells, macro pills)."""

    table_row_spacing: float
    """Vertical gap between adjacent table rows (TD rows, macro rows)."""

    @classmethod
    def from_config(cls, config: SkimConfig) -> "DocumentMetrics":
        """Compute document-wide metrics from a config.

        Resolves margin / border_width / inset directly — this is the
        canonical source for those values. ``KeymapLayoutMetrics``
        reads them off the resulting :class:`DocumentMetrics``.
        """
        doc_width = config.output.layout.width
        spacing = config.output.layout.spacing
        border = config.output.style.border

        border_width = border.width if border is not None else 0.0
        configured_margin = spacing.margin if spacing.margin is not None else 0.0
        # Floor the margin at ``border_width / 2`` so a centred stroke
        # never extends past the canvas edge.
        margin = (
            max(border_width / 2.0, configured_margin) if border is not None else configured_margin
        )
        inset = spacing.inset if spacing.inset is not None else doc_width * _INSET_DEFAULT_RATIO

        return cls(
            doc_width=doc_width,
            margin=margin,
            border_width=border_width,
            inset=inset,
            border_radius=border.radius if border is not None else None,
            column_gap=doc_width * _COLUMN_GAP_RATIO,
            # Universal table spacings — unscaled (per document); the
            # body-scaled standalone images multiply by ``BODY_SCALE``
            # locally via the per-component ``MacroMetrics`` /
            # ``TapDanceMetrics`` ``from_ctx`` factories.
            section_spacing=doc_width * _SECTION_SPACING_RATIO,
            table_header_spacing=doc_width * _TABLE_HEADER_SPACING_RATIO,
            table_col_spacing=doc_width * _TABLE_COL_SPACING_RATIO,
            table_row_spacing=doc_width * _TABLE_ROW_SPACING_RATIO,
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
        # Local import — :mod:`keymap_overview` imports from this
        # module transitively at startup; importing it eagerly would
        # create a circular import cycle.
        from .keymap_overview import compute_header_dims

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
    "RenderPalette",
    "TextStyle",
    "Theme",
    "Typography",
    "current_render_context",
    "using_render_context",
]

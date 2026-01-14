"""Test suite for configuration models."""

from skim.domain.config import (
    AppearanceConfig,
    BorderConfig,
    ColorConfig,
    LayerConfig,
    LayerConfigList,
    SkimConfig,
)


class TestLayerConfigList:
    """Test LayerConfigList functionality."""

    def test_lookup_by_id(self):
        layers = LayerConfigList(
            [
                LayerConfig(base_color="#000000", id="L1"),
                LayerConfig(base_color="#FFFFFF", id="L2"),
            ]
        )
        assert layers["L1"].base_color == "#000000"
        assert layers["L2"].base_color == "#FFFFFF"
        assert layers["L1"].index == 0
        assert layers["L2"].index == 1

    def test_lookup_by_index_str(self):
        layers = LayerConfigList([LayerConfig(base_color="#000000", id="L1")])
        assert layers["0"].base_color == "#000000"

    def test_lookup_invalid(self):
        layers = LayerConfigList([])
        assert layers["invalid"].index == -1


class TestBorderConfig:
    """Test border configuration model."""

    def test_border_config_creation(self):
        border = BorderConfig(color="#000000", radius=20)
        assert border.color == "#000000"
        assert border.radius == 20

    def test_border_config_defaults(self):
        border = BorderConfig()
        assert border.color == "#000000"
        assert border.radius == 20


class TestColorConfig:
    """Test color configuration model."""

    def test_color_config_creation(self):
        colors = ColorConfig(text="#000000", background="#FFFFFF", neutral="#70768B")
        assert colors.text == "#000000"
        assert colors.background == "#FFFFFF"
        assert colors.neutral == "#70768B"

    def test_color_config_with_named_colors(self):
        named_colors = {"RED": "#FF0000", "BLUE": "#0000FF"}
        colors = ColorConfig(
            text="#000000",
            background="#FFFFFF",
            neutral="#70768B",
            named_colors=named_colors,
        )
        assert colors.named_colors == named_colors


class TestAppearanceConfig:
    """Test appearance configuration model."""

    def test_appearance_config_creation(self):
        appearance = AppearanceConfig(
            border=BorderConfig(color="#000000", radius=20),
            colors=ColorConfig(text="#000000", background="#FFFFFF", neutral="#70768B"),
        )
        assert appearance.border.color == "#000000"
        assert appearance.colors.text == "#000000"

    def test_appearance_config_to_dict(self):
        appearance = AppearanceConfig(
            border=BorderConfig(color="#FF0000", radius=10),
            colors=ColorConfig(text="#111111", background="#EEEEEE", neutral="#888888"),
        )
        result = appearance.to_dict()
        assert result["border"]["color"] == "#FF0000"
        assert result["border"]["radius"] == 10
        assert result["colors"]["text"] == "#111111"


class TestLayerConfig:
    """Test layer configuration model."""

    def test_layer_config_with_base_color(self):
        layer = LayerConfig(base_color="#347156")
        assert layer.base_color == "#347156"

    def test_layer_config_with_all_fields(self):
        layer = LayerConfig(
            id="_BASE", name="COLEMAK", label="BASE", base_color="#347156"
        )
        assert layer.id == "_BASE"
        assert layer.name == "COLEMAK"
        assert layer.label == "BASE"
        assert layer.base_color == "#347156"


class TestSkimConfig:
    """Test main skim configuration model."""

    def test_skim_config_creation(self):
        config = SkimConfig(
            layers=LayerConfigList(
                [
                    LayerConfig(base_color="#347156"),
                    LayerConfig(base_color="#89511C"),
                ]
            ),
            appearance=AppearanceConfig(
                border=BorderConfig(),
                colors=ColorConfig(
                    text="#000000", background="#FFFFFF", neutral="#70768B"
                ),
            ),
        )
        assert len(config.layers) == 2
        assert config.layers[0].base_color == "#347156"

    def test_skim_config_with_keycodes(self):
        keycodes = {"KC_A": "A", "KC_B": "B"}
        config = SkimConfig(
            layers=LayerConfigList([LayerConfig(base_color="#347156")]),
            keycodes=keycodes,
        )
        assert config.keycodes == keycodes

    def test_skim_config_from_yaml_dict(self):
        yaml_data = {
            "layers": [{"base_color": "#347156"}],
            "appearance": {
                "border": {"color": "#000000", "radius": 20},
                "colors": {
                    "text": "#000000",
                    "background": "#FFFFFF",
                    "neutral": "#70768B",
                },
            },
        }
        config = SkimConfig.from_dict(yaml_data)
        assert len(config.layers) == 1
        assert config.layers[0].base_color == "#347156"
        assert config.appearance is not None
        assert config.appearance.border.color == "#000000"

    def test_skim_config_load_default(self):
        config = SkimConfig.load_default()
        assert config is not None
        assert len(config.layers) > 0
        assert config.appearance is not None

    def test_skim_config_merge_with_defaults(self):
        partial = SkimConfig(
            layers=LayerConfigList([LayerConfig(base_color="#FF0000")])
        )
        merged = partial.merge_with_defaults()
        assert merged.appearance is not None
        assert len(merged.layers) == 1
        assert merged.layers[0].base_color == "#FF0000"

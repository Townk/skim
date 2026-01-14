"""Unit tests for ImageGenerator."""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from skim.application.image_generator import ImageGenerator
from skim.domain.config import LayerConfig


class TestImageGenerator:
    """Test image generation orchestration."""

    @pytest.fixture
    def mock_deps(self):
        """Mock all external dependencies."""
        with (
            patch("skim.application.image_generator.SkimConfig") as mock_config_cls,
            patch(
                "skim.application.image_generator.KeycodeMappingLoader"
            ) as mock_loader_cls,
            patch(
                "skim.application.image_generator.KeycodeTransformer"
            ) as mock_transformer_cls,
            patch(
                "skim.application.image_generator.TypstCompiler"
            ) as mock_compiler_cls,
            patch("skim.application.image_generator.C2JsonParser") as mock_c2json_cls,
            patch("skim.application.image_generator.VialParser") as mock_vial_cls,
            patch("skim.application.image_generator.KeybardParser") as mock_keybard_cls,
        ):
            # Setup mocks
            mock_config = MagicMock()
            mock_config_cls.return_value = mock_config

            # Setup appearance mock
            mock_appearance = MagicMock()
            mock_appearance.colors.neutral = "#cccccc"
            mock_appearance.to_dict.return_value = {
                "colors": {
                    "neutral": "#cccccc",
                    "text": "#000000",
                    "background": "#ffffff",
                },
                "border": {"color": "#000000", "radius": 20},
            }
            mock_config.appearance = mock_appearance

            # Setup default layer config mock
            layer_mock = MagicMock(spec=LayerConfig)
            # We must set 'name' separately because it's a reserved argument in MagicMock constructor
            layer_mock.base_color = "#ff0000"
            layer_mock.id = "0"
            layer_mock.name = "Base"
            layer_mock.label = "BASE"

            mock_config.layers = [layer_mock]

            # Important: Mock class method load_default to return our mock instance
            mock_config_cls.load_default.return_value = mock_config
            mock_config_cls.from_dict.return_value = mock_config
            mock_config.merge_with_defaults.return_value = mock_config

            mock_loader = MagicMock()
            mock_loader_cls.return_value = mock_loader
            mock_loader.load_bundled.return_value = {
                "keycodes": {},
                "reversed_alias": {},
                "modifiers": {},
                "layer_symbols": {},
            }

            mock_transformer = MagicMock()
            mock_transformer_cls.return_value = mock_transformer
            mock_transformer.transform_list.side_effect = (
                lambda x: x
            )  # Identity transform
            mock_transformer.extract_layer_number.return_value = None

            mock_compiler = MagicMock()
            mock_compiler_cls.return_value = mock_compiler

            mock_c2json = MagicMock()
            mock_c2json_cls.return_value = mock_c2json

            mock_vial = MagicMock()
            mock_vial_cls.return_value = mock_vial

            mock_keybard = MagicMock()
            mock_keybard_cls.return_value = mock_keybard

            yield {
                "config_cls": mock_config_cls,
                "config": mock_config,
                "loader": mock_loader,
                "transformer": mock_transformer,
                "compiler": mock_compiler,
                "c2json": mock_c2json,
                "vial": mock_vial,
                "keybard": mock_keybard,
            }

    def test_detect_format_c2json(self, mock_deps):
        """Detect c2json format from content."""
        content = json.dumps({"layers": [["KC_A"]]})
        generator = ImageGenerator(None, Path("out"), "svg")

        # Should call C2JsonParser
        with patch(
            "skim.application.image_generator.Path.read_text", return_value=content
        ):
            # We bypass file reading logic for this specific detection test if checking private method
            # But let's test public method
            fmt = generator._detect_format(content)
            assert fmt == "c2json"

    def test_detect_format_vial(self, mock_deps):
        """Detect vial format from content."""
        content = json.dumps({"layout": [], "version": 1})
        generator = ImageGenerator(None, Path("out"), "svg")

        fmt = generator._detect_format(content)
        assert fmt == "vial"

    def test_detect_format_keybard(self, mock_deps):
        """Detect keybard format from content."""
        content = json.dumps({"keymap": [], "layers": 1})
        generator = ImageGenerator(None, Path("out"), "svg")

        fmt = generator._detect_format(content)
        assert fmt == "keybard"

    def test_generate_flow_c2json(self, mock_deps):
        """Test full generation flow with c2json input."""
        generator = ImageGenerator(None, Path("out"), "svg")

        # Mock parsing result
        mock_deps["c2json"].parse.return_value = [["KC_A"] * 60]  # 1 layer, 60 keys

        # Mock file reading
        content = json.dumps({"layers": []})

        # We need to mock Path.read_text specifically
        with patch("pathlib.Path.read_text", return_value=content):
            # Also need to mock Path.suffix for detection logic if used
            # But Path("map.json") has .json suffix, so it calls read_text()
            generator.generate(keymap_path=Path("map.json"))

        # Verify parsers called
        mock_deps["c2json"].parse.assert_called_once()
        mock_deps["vial"].parse.assert_not_called()

        # Verify compilation called
        # Should call compile twice: once for layer 0, once for overview
        assert mock_deps["compiler"].compile.call_count >= 1

    def test_generate_layer_selection_single(self, mock_deps):
        """Test generating specific layer only."""
        # Use Mocks for paths to avoid filesystem and verify calls
        mock_output_dir = MagicMock()
        generator = ImageGenerator(None, mock_output_dir, "svg")

        # Mock 3 layers
        mock_deps["c2json"].parse.return_value = [["KC_A"] * 60] * 3

        content = json.dumps({"layers": []})
        mock_keymap_path = MagicMock()
        mock_keymap_path.read_text.return_value = content
        # Mock suffix for detection
        mock_keymap_path.suffix = ".json"

        # Setup output_dir / "filename" behavior
        # When generator does output_dir / string, it calls __truediv__
        # We want to verify unlink is called on the specific file mocks

        # We need distinct mocks for each file to verify specific unlinks
        # mock_output_dir / "keymap-1.svg" -> mock_file_1
        # mock_output_dir / "keymap-2.svg" -> mock_file_2
        # etc.

        file_mocks = {}

        def get_file_mock(name):
            if name not in file_mocks:
                m = MagicMock()
                m.exists.return_value = True  # Simulate file exists
                file_mocks[name] = m
            return file_mocks[name]

        mock_output_dir.__truediv__.side_effect = get_file_mock

        generator.generate(
            keymap_path=mock_keymap_path, layers=["1"]
        )  # 1-based index = layer 0 (so we want page 1)

        # 1. Verify compiler called with {p} pattern
        assert mock_deps["compiler"].compile.call_args_list

        # Verify get_file_mock called with pattern string
        # The pattern string is f"keymap-{{p}}.svg"
        pattern = "keymap-{p}.svg"
        assert pattern in file_mocks

        # 2. Verify cleanup
        # We expect unlink to be called on keymap-2.svg and keymap-3.svg
        # And NOT on keymap-1.svg

        assert "keymap-1.svg" in file_mocks  # It was accessed/created loop
        assert "keymap-2.svg" in file_mocks
        assert "keymap-3.svg" in file_mocks

        file_mocks["keymap-1.svg"].unlink.assert_not_called()
        file_mocks["keymap-2.svg"].unlink.assert_called_once()
        file_mocks["keymap-3.svg"].unlink.assert_called_once()

    def test_generate_resolves_named_colors(self, mock_deps):
        """Ensure named colors are resolved using config."""
        generator = ImageGenerator(None, Path("out"), "svg")

        # Setup config with a named color
        mock_deps["config"].layers[0].base_color = "PINK"
        # Add PINK to named_colors
        mock_deps["config"].appearance.colors.named_colors = {"PINK": "#FF00FF"}

        # Mock c2json result (1 layer)
        mock_deps["c2json"].parse.return_value = [["KC_A"] * 60]

        content = json.dumps({"layers": []})
        with patch("pathlib.Path.read_text", return_value=content):
            # If resolution fails, this will raise ValueError (invalid literal for int() with base 16: 'PI')
            generator.generate(keymap_path=Path("map.json"))

    def test_generate_selected_layers_sys_input(self, mock_deps):
        """Ensure selectedLayers is passed to sys_inputs."""
        generator = ImageGenerator(None, Path("out"), "svg")

        # Mock 5 layers
        mock_deps["c2json"].parse.return_value = [["KC_A"] * 60] * 5

        content = json.dumps({"layers": []})
        with patch("pathlib.Path.read_text", return_value=content):
            # Select layer 1 (index 0) and 3-4 (indices 2, 3)
            # -l "1,3-4"
            generator.generate(keymap_path=Path("map.json"), layers=["1,3-4"])

        call_args = mock_deps["compiler"].compile.call_args[1]
        keymap_dict = json.loads(call_args["sys_inputs"]["keymap"])

        assert "selectedLayers" in keymap_dict
        assert keymap_dict["selectedLayers"] == [0, 2, 3]

    def test_unknown_format_raises(self, mock_deps):
        """Raise error if format cannot be detected."""
        generator = ImageGenerator(None, Path("out"), "svg")
        content = "{}"

        with pytest.raises(ValueError, match="Unknown keymap format"):
            generator._detect_format(content)

    def test_generate_supports_custom_layer_keycode(self, mock_deps):
        """Ensure config.layer_keycode is used for toggles."""
        generator = ImageGenerator(None, Path("out"), "svg")

        # Setup config
        mock_deps["config"].layer_keycode = {"CUSTOM_KEY": {"target": 1, "type": "MO"}}

        # Mock parsing: keymap has CUSTOM_KEY
        mock_deps["c2json"].parse.return_value = [["CUSTOM_KEY"] * 60]

        content = json.dumps({"layers": []})
        with patch("pathlib.Path.read_text", return_value=content):
            generator.generate(keymap_path=Path("map.json"))

        # Verify layerToggles in sys_inputs
        call_args = mock_deps["compiler"].compile.call_args[1]
        keymap_dict = json.loads(call_args["sys_inputs"]["keymap"])
        toggles = keymap_dict["layers"][0]["layerToggles"]

        # Should be all 1s (since we filled layer with CUSTOM_KEY)
        assert toggles[0][0] == 1

    def test_generate_loads_config_from_file(self, mock_deps):
        """Test configuration loading from file."""
        generator = ImageGenerator(Path("config.yaml"), Path("out"), "svg")

        with (
            patch("builtins.open", mock_open(read_data="layers: []")),
            patch("yaml.safe_load", return_value={"layers": []}),
            patch("pathlib.Path.read_text", return_value='{"layers":[]}'),
        ):
            generator.generate(keymap_path=Path("map.json"))

        assert mock_deps["config_cls"].from_dict.called
        assert mock_deps["config"].merge_with_defaults.called

    def test_detect_format_from_path_extensions(self, mock_deps):
        """Test format detection based on file extensions."""
        generator = ImageGenerator(None, Path("out"), "svg")

        # .vil -> vial
        p = MagicMock()
        p.suffix = ".vil"
        assert generator._detect_format_from_path(p) == "vial"

        # .kbi -> keybard
        p.suffix = ".kbi"
        assert generator._detect_format_from_path(p) == "keybard"

        # .json -> read content
        p.suffix = ".json"
        p.read_text.return_value = '{"layers":[]}'
        assert generator._detect_format_from_path(p) == "c2json"

        # .txt -> read content
        p.suffix = ".txt"
        p.read_text.return_value = '{"layout":[], "version":1}'
        assert generator._detect_format_from_path(p) == "vial"

    def test_cleanup_skip_nonexistent(self, mock_deps):
        """Test cleanup logic skips if file doesn't exist."""
        mock_output_dir = MagicMock()
        # Mock file existence to False
        mock_output_dir.__truediv__.return_value.exists.return_value = False

        generator = ImageGenerator(None, mock_output_dir, "svg")
        mock_deps["c2json"].parse.return_value = [["KC_A"] * 60] * 2

        # Select layer 1 (index 0). Layer 2 (index 1) should be skipped for cleanup.
        with patch("pathlib.Path.read_text", return_value='{"layers":[]}'):
            generator.generate(keymap_path=Path("map.json"), layers=["1"])

        # Verify unlink NOT called
        mock_output_dir.__truediv__.return_value.unlink.assert_not_called()

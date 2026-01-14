"""Unit tests for LayerAdaptor."""

import pytest

from skim.application.layer_transformer import LayerAdaptor


class TestLayerAdaptor:
    """Test reordering of layer keys for Keybard and Vial formats."""

    @pytest.fixture
    def sequential_layer(self):
        """Create a layer with sequential strings '00' to '59'."""
        return [f"{i:02d}" for i in range(60)]

    def test_single_layer_adaptor_completeness(self, sequential_layer):
        """Test that all keys are preserved (no data loss)."""
        # We access private method for direct testing
        result = LayerAdaptor._single_layer_adaptor(sequential_layer)

        assert len(result) == 60
        assert sorted(result) == sorted(sequential_layer)
        assert "" not in result  # Ensure no empty slots left

    def test_from_keybard(self, sequential_layer):
        """Test processing multiple layers from Keybard."""
        layers = [sequential_layer, sequential_layer]
        result = LayerAdaptor.from_keybard(layers)

        assert len(result) == 2
        # Verify transformation happened (output should not match input)
        assert result[0] != sequential_layer
        assert result[0] == LayerAdaptor._single_layer_adaptor(sequential_layer)

    def test_from_vial(self):
        """Test processing Vial format (nested lists)."""
        # Vial format: List[List[List[str]]] -> Layers -> Clusters -> Keys
        # Let's mock a single layer with 10 clusters of 6 keys
        layer_clusters = []
        counter = 0
        for _ in range(10):
            cluster = []
            for _ in range(6):
                cluster.append(f"{counter:02d}")
                counter += 1
            layer_clusters.append(cluster)

        # Input is list of layers (which are lists of clusters)
        vial_input = [layer_clusters]

        result = LayerAdaptor.from_vial(vial_input)

        assert len(result) == 1
        assert len(result[0]) == 60

        # Verify it flattened and transformed correctly
        # The flattened input would match sequential_layer
        flattened = [k for cluster in layer_clusters for k in cluster]
        expected = LayerAdaptor._single_layer_adaptor(flattened)
        assert result[0] == expected

    def test_specific_mapping_logic(self, sequential_layer):
        """Verify specific mapping positions based on algorithm."""
        result = LayerAdaptor._single_layer_adaptor(sequential_layer)

        # Let's trace a few keys based on the algorithm:
        # thumb_mapping = [4, 2, -2, -2, -2, 0]
        # finger_mapping = [3, 1, -2, -2, 0, 0]

        # 1. Right finger clusters (Input 36-60) -> Output 0-24
        # Input index 36 (first of right fingers) -> idx=0
        # mapped_list[0 + finger_mapping[0%6]] = input[36]
        # mapped_list[0 + 3] = '36' -> result[3] should be '36'
        assert result[3] == "36"

        # Input index 37 -> idx=1
        # mapped_list[1 + finger_mapping[1%6]] = input[37]
        # mapped_list[1 + 1] = '37' -> result[2] should be '37'
        assert result[2] == "37"

        # 2. Left finger clusters (Input 6-30) -> Output 24-48
        # Input index 6 (first of left fingers) -> idx=0
        # oIdx starts at 24
        # mapped_list[24 + finger_mapping[0%6]] = input[6]
        # mapped_list[24 + 3] = '06' -> result[27] should be '06'
        assert result[27] == "06"

        # 3. Left thumb cluster (Input 0-6) -> Output 54-60 (Last block)
        # Input index 0 -> idx=0
        # oIdx starts at 54
        # mapped_list[54 + thumb_mapping[0%6]] = input[0]
        # mapped_list[54 + 4] = '00' -> result[58] should be '00'
        assert result[58] == "00"

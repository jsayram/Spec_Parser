"""
Tests for ExtractionConfig and related configuration classes.
"""

import pytest
from dataclasses import asdict

from spec_parser.config import (
    ExtractionConfig,
    LLMConfig,
    ParallelConfig,
    ConfidenceConfig,
    SearchConfig,
    VisualizationConfig,
    GroundingConfig,
    SMALL_LLM_CONFIG,
    LARGE_LLM_CONFIG,
    DEFAULT_CONFIG,
    default_config,
    small_llm_config,
    large_llm_config,
)


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""
    
    def test_default_values(self):
        """Test default LLMConfig values."""
        config = LLMConfig()
        
        assert config.model == "qwen2.5-coder:7b"
        assert config.temperature == 0.0
        assert config.max_tokens == 4000
        assert config.context_window == 8192
        assert config.chunk_size == 3000
        assert config.overlap_size == 200
        assert config.timeout == 180
        assert config.max_retries == 5
        assert config.retry_min_wait == 2.0
        assert config.retry_max_wait == 60.0
        assert config.retry_multiplier == 2.0
        assert config.retry_jitter == 5.0
    
    def test_custom_values(self):
        """Test LLMConfig with custom values."""
        config = LLMConfig(
            model="llama3:70b",
            chunk_size=5000,
            max_retries=10,
        )
        
        assert config.model == "llama3:70b"
        assert config.chunk_size == 5000
        assert config.max_retries == 10
        # Defaults still apply
        assert config.temperature == 0.0


class TestParallelConfig:
    """Tests for ParallelConfig dataclass."""
    
    def test_default_values(self):
        """Test default ParallelConfig values."""
        config = ParallelConfig()
        
        assert config.max_page_workers == 4
        assert config.max_message_workers == 2
        assert config.batch_size == 10
        assert config.queue_timeout == 300.0
    
    def test_custom_workers(self):
        """Test custom worker counts."""
        config = ParallelConfig(
            max_page_workers=8,
            max_message_workers=4,
        )
        
        assert config.max_page_workers == 8
        assert config.max_message_workers == 4


class TestConfidenceConfig:
    """Tests for ConfidenceConfig dataclass."""
    
    def test_default_thresholds(self):
        """Test default confidence thresholds."""
        config = ConfidenceConfig()
        
        assert config.discovery_threshold == 0.7
        assert config.field_extraction_threshold == 0.6
        assert config.refinement_threshold == 0.8
        assert config.max_refinement_iterations == 3
    
    def test_custom_thresholds(self):
        """Test custom confidence thresholds."""
        config = ConfidenceConfig(
            discovery_threshold=0.5,
            refinement_threshold=0.9,
        )
        
        assert config.discovery_threshold == 0.5
        assert config.refinement_threshold == 0.9


class TestSearchConfig:
    """Tests for SearchConfig dataclass."""
    
    def test_default_values(self):
        """Test default search configuration."""
        config = SearchConfig()
        
        assert config.faiss_weight == 0.6
        assert config.bm25_weight == 0.4
        assert config.top_k == 10
        assert config.max_context_chunks == 20
        assert config.dedup_threshold == 0.95
    
    def test_weights_sum(self):
        """Test that weights can be customized."""
        config = SearchConfig(faiss_weight=0.5, bm25_weight=0.5)
        
        assert config.faiss_weight + config.bm25_weight == 1.0


class TestVisualizationConfig:
    """Tests for VisualizationConfig dataclass."""
    
    def test_default_colors(self):
        """Test default visualization colors."""
        config = VisualizationConfig()
        
        assert "text" in config.colors
        assert "picture" in config.colors
        assert "table" in config.colors
        assert "graphics" in config.colors
        assert "marginalia" in config.colors
    
    def test_color_format(self):
        """Test color format is RGB tuple (0-255 BGR for OpenCV)."""
        config = VisualizationConfig()
        
        for color_name, color_value in config.colors.items():
            assert isinstance(color_value, tuple)
            assert len(color_value) == 3
            assert all(0 <= v <= 255 for v in color_value)


class TestGroundingConfig:
    """Tests for GroundingConfig dataclass."""
    
    def test_default_values(self):
        """Test default grounding configuration."""
        config = GroundingConfig()
        
        assert config.export_enabled is True
        assert config.padding == 5
        assert config.dpi == 200
        assert config.output_format == "png"
    
    def test_custom_config(self):
        """Test custom grounding config."""
        config = GroundingConfig(export_enabled=False, dpi=300)
        
        assert config.export_enabled is False
        assert config.dpi == 300


class TestExtractionConfig:
    """Tests for main ExtractionConfig class."""
    
    def test_default_config(self):
        """Test default ExtractionConfig."""
        config = ExtractionConfig()
        
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.parallel, ParallelConfig)
        assert isinstance(config.confidence, ConfidenceConfig)
        assert isinstance(config.search, SearchConfig)
        assert isinstance(config.visualization, VisualizationConfig)
        assert isinstance(config.grounding, GroundingConfig)
    
    def test_for_small_llm_preset(self):
        """Test small LLM preset configuration."""
        config = ExtractionConfig.for_small_llm()
        
        # Smaller chunks for limited context
        assert config.llm.chunk_size == 2000
        # More retries for less reliable models
        assert config.llm.max_retries == 7
        # Lower thresholds for less accurate extraction
        assert config.confidence.discovery_threshold == 0.6
        assert config.confidence.field_extraction_threshold == 0.5
        # Fewer parallel workers
        assert config.parallel.max_page_workers == 2
    
    def test_for_large_llm_preset(self):
        """Test large LLM preset configuration."""
        config = ExtractionConfig.for_large_llm()
        
        # Larger chunks for bigger context windows
        assert config.llm.chunk_size == 6000
        # Fewer retries for more reliable models
        assert config.llm.max_retries == 3
        # Higher thresholds for better accuracy
        assert config.confidence.discovery_threshold == 0.8
        assert config.confidence.field_extraction_threshold == 0.7
        # More parallel workers
        assert config.parallel.max_page_workers == 6
    
    def test_from_model_size(self):
        """Test config factory based on model size."""
        small_config = ExtractionConfig.from_model_size(7.0)
        large_config = ExtractionConfig.from_model_size(70.0)
        medium_config = ExtractionConfig.from_model_size(20.0)
        
        assert small_config.llm.chunk_size == 2000
        assert large_config.llm.chunk_size == 6000
        assert medium_config.llm.chunk_size == 3000  # Default
    
    def test_to_dict(self):
        """Test serialization to dict."""
        config = ExtractionConfig()
        config_dict = config.to_dict()
        
        assert "llm" in config_dict
        assert "parallel" in config_dict
        assert "confidence" in config_dict
        assert "search" in config_dict
        assert config_dict["llm"]["model"] == "qwen2.5-coder:7b"
    
    def test_from_dict(self):
        """Test deserialization from dict."""
        config_dict = {
            "llm": {"chunk_size": 4000, "max_retries": 10},
            "parallel": {"max_page_workers": 8},
        }
        
        config = ExtractionConfig.from_dict(config_dict)
        
        assert config.llm.chunk_size == 4000
        assert config.llm.max_retries == 10
        assert config.parallel.max_page_workers == 8
        # Defaults for unspecified
        assert config.confidence.discovery_threshold == 0.7


class TestPresetInstances:
    """Tests for preset config instances."""
    
    def test_preset_aliases(self):
        """Test preset alias names."""
        assert SMALL_LLM_CONFIG is small_llm_config
        assert LARGE_LLM_CONFIG is large_llm_config
        assert DEFAULT_CONFIG is default_config
    
    def test_presets_are_different(self):
        """Test that presets have different values."""
        assert SMALL_LLM_CONFIG.llm.chunk_size != LARGE_LLM_CONFIG.llm.chunk_size
        assert SMALL_LLM_CONFIG.llm.max_retries != LARGE_LLM_CONFIG.llm.max_retries
    
    def test_presets_are_valid(self):
        """Test that all presets are valid ExtractionConfig instances."""
        assert isinstance(SMALL_LLM_CONFIG, ExtractionConfig)
        assert isinstance(LARGE_LLM_CONFIG, ExtractionConfig)
        assert isinstance(DEFAULT_CONFIG, ExtractionConfig)

"""
Unified extraction configuration for POCT1-A spec parsing.

Centralizes all settings for LLM, parallel processing, retry logic,
confidence thresholds, and chunk sizing for optimal extraction.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class LLMConfig:
    """LLM-specific configuration for optimal extraction with smaller models."""
    
    # Model settings
    provider: str = "ollama"
    model: str = "qwen2.5-coder:7b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0  # Deterministic for reproducibility
    
    # Context window management (CRITICAL for smaller LLMs)
    max_tokens: int = 4000  # Response limit
    context_window: int = 8192  # Model's context window
    chunk_size: int = 3000  # Safe chunk size (leaves room for prompt + response)
    overlap_size: int = 200  # Overlap between chunks for continuity
    
    # Timeout settings
    timeout: int = 180  # Extended for complex extractions
    connect_timeout: int = 10  # Connection timeout
    
    # Retry settings (CRITICAL for self-healing)
    max_retries: int = 5  # Retry attempts
    retry_min_wait: float = 2.0  # Initial wait (seconds)
    retry_max_wait: float = 60.0  # Maximum wait (seconds)
    retry_multiplier: float = 2.0  # Exponential multiplier
    retry_jitter: float = 5.0  # Random jitter (seconds)
    
    # Response validation
    require_json: bool = True  # Expect JSON responses
    json_repair_attempts: int = 3  # Attempts to repair malformed JSON


@dataclass
class ParallelConfig:
    """Parallel processing configuration."""
    
    # Page extraction parallelism
    max_page_workers: int = 4  # Concurrent page extractions
    
    # Message extraction parallelism  
    max_message_workers: int = 2  # Concurrent message field extractions
    
    # Batch settings
    batch_size: int = 10  # Pages per batch
    
    # Queue settings
    queue_timeout: float = 300.0  # Max wait for queue item


@dataclass
class ConfidenceConfig:
    """Confidence threshold configuration."""
    
    # Extraction confidence thresholds
    discovery_threshold: float = 0.7  # Minimum for message discovery
    field_extraction_threshold: float = 0.6  # Minimum for field extraction
    refinement_threshold: float = 0.8  # Trigger refinement below this
    
    # Validation thresholds
    schema_validation_weight: float = 0.3
    search_confidence_weight: float = 0.3
    llm_confidence_weight: float = 0.4
    
    # Maximum refinement iterations
    max_refinement_iterations: int = 3


@dataclass
class SearchConfig:
    """Search and retrieval configuration."""
    
    # Hybrid search weights
    faiss_weight: float = 0.6
    bm25_weight: float = 0.4
    
    # Retrieval settings
    top_k: int = 10  # Results per query
    dedup_threshold: float = 0.95  # Similarity threshold for deduplication
    
    # Context building
    max_context_chunks: int = 20  # Max chunks to include in LLM context
    context_char_limit: int = 6000  # Character limit for context


@dataclass
class VisualizationConfig:
    """Visualization and debugging configuration."""
    
    # Bounding box visualization
    box_thickness: int = 2
    font_scale: float = 0.5
    text_bg_opacity: float = 0.7
    
    # Colors (BGR format for OpenCV)
    colors: Dict[str, tuple] = field(default_factory=lambda: {
        "text": (255, 0, 0),       # Blue
        "table": (139, 69, 19),    # Brown
        "picture": (50, 205, 50),  # Green
        "graphics": (128, 0, 255), # Purple
        "marginalia": (128, 128, 128),  # Gray
    })
    
    # Output settings
    dpi: int = 150
    output_format: str = "png"


@dataclass
class GroundingConfig:
    """Grounding export configuration."""
    
    # Export settings
    export_enabled: bool = True
    min_block_size: int = 20  # Minimum block dimension to export
    
    # Cropping settings
    padding: int = 5  # Padding around crops
    dpi: int = 200  # Rendering DPI for crops
    
    # Output settings
    output_format: str = "png"
    organize_by_page: bool = True  # Organize by page subdirectory


@dataclass
class ExtractionConfig:
    """
    Master extraction configuration.
    
    Combines all sub-configurations for complete pipeline control.
    Optimized for reliable extraction with smaller LLMs.
    """
    
    # Sub-configurations
    llm: LLMConfig = field(default_factory=LLMConfig)
    parallel: ParallelConfig = field(default_factory=ParallelConfig)
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    grounding: GroundingConfig = field(default_factory=GroundingConfig)
    
    # Global settings
    include_marginalia: bool = True
    enable_layout_detection: bool = True
    enable_validation_agent: bool = True
    
    # Output settings
    save_intermediates: bool = True  # Save intermediate extraction results
    debug_mode: bool = False  # Enable verbose debug logging
    
    @classmethod
    def for_small_llm(cls) -> "ExtractionConfig":
        """
        Create config optimized for smaller LLMs (7B parameters).
        
        Smaller context chunks, more retries, lower confidence thresholds.
        """
        config = cls()
        
        # Smaller chunks for limited context
        config.llm.chunk_size = 2000
        config.llm.overlap_size = 150
        config.llm.max_tokens = 2000
        
        # More retries for reliability
        config.llm.max_retries = 7
        config.llm.timeout = 240
        
        # Lower thresholds for smaller model capabilities
        config.confidence.discovery_threshold = 0.6
        config.confidence.field_extraction_threshold = 0.5
        config.confidence.refinement_threshold = 0.7
        
        # Fewer parallel workers to reduce memory
        config.parallel.max_page_workers = 2
        config.parallel.max_message_workers = 1
        
        # Smaller context
        config.search.max_context_chunks = 10
        config.search.context_char_limit = 4000
        
        return config
    
    @classmethod
    def for_large_llm(cls) -> "ExtractionConfig":
        """
        Create config for larger LLMs (32B+ parameters).
        
        Larger context, higher quality thresholds, faster processing.
        """
        config = cls()
        
        # Larger chunks for extended context
        config.llm.chunk_size = 6000
        config.llm.overlap_size = 300
        config.llm.max_tokens = 4000
        config.llm.context_window = 32768
        
        # Fewer retries needed
        config.llm.max_retries = 3
        
        # Higher quality thresholds
        config.confidence.discovery_threshold = 0.8
        config.confidence.field_extraction_threshold = 0.7
        config.confidence.refinement_threshold = 0.85
        
        # More parallel workers
        config.parallel.max_page_workers = 6
        config.parallel.max_message_workers = 4
        
        # Larger context
        config.search.max_context_chunks = 30
        config.search.context_char_limit = 12000
        
        return config
    
    @classmethod
    def from_model_size(cls, model_params_b: float) -> "ExtractionConfig":
        """
        Auto-configure based on model size in billions of parameters.
        
        Args:
            model_params_b: Model size in billions (e.g., 7.0, 32.0)
            
        Returns:
            Appropriately configured ExtractionConfig
        """
        if model_params_b < 10:
            return cls.for_small_llm()
        elif model_params_b < 30:
            return cls()  # Default/medium config
        else:
            return cls.for_large_llm()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionConfig":
        """Create from dictionary."""
        config = cls()
        
        if "llm" in data:
            config.llm = LLMConfig(**data["llm"])
        if "parallel" in data:
            config.parallel = ParallelConfig(**data["parallel"])
        if "confidence" in data:
            config.confidence = ConfidenceConfig(**data["confidence"])
        if "search" in data:
            config.search = SearchConfig(**data["search"])
        if "visualization" in data:
            config.visualization = VisualizationConfig(**data["visualization"])
        if "grounding" in data:
            config.grounding = GroundingConfig(**data["grounding"])
        
        # Global settings
        for key in ["include_marginalia", "enable_layout_detection", 
                    "enable_validation_agent", "save_intermediates", "debug_mode"]:
            if key in data:
                setattr(config, key, data[key])
        
        return config


# Default configuration instance
default_config = ExtractionConfig()

# Pre-configured instances for common use cases
small_llm_config = ExtractionConfig.for_small_llm()
large_llm_config = ExtractionConfig.for_large_llm()

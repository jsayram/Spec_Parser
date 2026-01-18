"""
Configuration module using pydantic-settings.

All configuration loaded from environment variables with sensible defaults.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    Load from .env file or environment variables.
    """
    
    # Project paths
    project_root: Path = Path(__file__).parent.parent.parent
    output_dir: Path = project_root / "output"
    image_dir: Path = output_dir / "images"
    markdown_dir: Path = output_dir / "markdown"
    json_dir: Path = output_dir / "json"
    index_dir: Path = output_dir / "indices"
    
    # OCR settings
    ocr_language: str = "eng"
    ocr_dpi: int = 300
    ocr_confidence_threshold: float = 0.7
    
    # Embedding settings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    
    # Search settings
    search_top_k: int = 5
    hybrid_search_alpha: float = 0.5  # Weight for semantic vs keyword
    
    # RLM settings
    rlm_context_window: int = 2000  # Characters before/after target
    rlm_max_span_length: int = 5000  # Max characters per span
    rlm_neighbors_count: int = 3  # Number of neighbor spans to retrieve
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None
    
    # Performance
    max_workers: int = 4  # Parallel processing workers
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    def ensure_directories(self):
        """Create all required directories"""
        for directory in [
            self.output_dir,
            self.image_dir,
            self.markdown_dir,
            self.json_dir,
            self.index_dir
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

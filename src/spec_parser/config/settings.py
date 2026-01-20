"""
Application settings using pydantic-settings.

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
    project_root: Path = Path(__file__).parent.parent.parent.parent
    data_dir: Path = project_root / "data"
    specs_dir: Path = data_dir / "specs"
    spec_output_dir: Path = data_dir / "spec_output"
    extraction_output_dir: Path = data_dir / "output"  # Debug/temp extraction outputs
    models_dir: Path = project_root / "models"
    
    # Output directories (set dynamically per parsing run)
    output_dir: Optional[Path] = None
    image_dir: Optional[Path] = None
    markdown_dir: Optional[Path] = None
    json_dir: Optional[Path] = None
    index_dir: Optional[Path] = None
    
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
    hybrid_search_alpha: float = 0.5
    
    # RLM settings
    rlm_context_window: int = 2000
    rlm_max_span_length: int = 5000
    rlm_neighbors_count: int = 3
    
    # LLM settings
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5-coder:7b"
    llm_base_url: str = "http://localhost:11434"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4000
    llm_rate_limit: float = 1.0
    llm_timeout: int = 120
    
    # LLM cache settings
    llm_cache_dir: Path = project_root / "config"
    llm_global_cache: str = "llm_corrections.db"
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None
    
    # Performance
    max_workers: int = 4
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    def ensure_directories(self):
        """Create all required directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        self.spec_output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.output_dir:
            for directory in [
                self.output_dir,
                self.image_dir,
                self.markdown_dir,
                self.json_dir,
                self.index_dir
            ]:
                if directory:
                    directory.mkdir(parents=True, exist_ok=True)
    
    def create_output_session(self, pdf_path: Path) -> Path:
        """
        Create timestamped output directory for parsing session.
        
        Format: YYYYMMDD_HHMMSS_{identifier}
        
        Args:
            pdf_path: Path to PDF being parsed
            
        Returns:
            Path to created output directory
        """
        from datetime import datetime
        import re
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        pdf_stem = pdf_path.stem
        identifier = re.sub(r'[_\-](v\d+|version\d+|\d{4,8})', '', pdf_stem, flags=re.IGNORECASE)
        identifier = re.sub(r'[^a-zA-Z0-9]', '', identifier)[:20]
        
        session_name = f"{timestamp}_{identifier}"
        self.output_dir = self.spec_output_dir / session_name
        self.image_dir = self.output_dir / "images"
        self.markdown_dir = self.output_dir / "markdown"
        self.json_dir = self.output_dir / "json"
        self.index_dir = self.output_dir / "index"
        
        self.ensure_directories()
        
        return self.output_dir


# Global settings instance
settings = Settings()

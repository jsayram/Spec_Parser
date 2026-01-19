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
    data_dir: Path = project_root / "data"
    specs_dir: Path = data_dir / "specs"
    spec_output_dir: Path = data_dir / "spec_output"
    models_dir: Path = project_root / "models"  # For LLM/embedding model binaries
    
    # Output directories (set dynamically per parsing run)
    # Use create_output_session() to generate timestamped directory
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
    hybrid_search_alpha: float = 0.5  # Weight for semantic vs keyword
    
    # RLM settings
    rlm_context_window: int = 2000  # Characters before/after target
    rlm_max_span_length: int = 5000  # Max characters per span
    rlm_neighbors_count: int = 3  # Number of neighbor spans to retrieve
    
    # LLM settings
    llm_provider: str = "ollama"  # "huggingface", "ollama", "anthropic", or "openai"
    llm_model: str = "qwen2.5-coder:7b"  # Model identifier
    llm_base_url: str = "http://localhost:11434"  # Ollama base URL (ignored for huggingface)
    llm_temperature: float = 0.0  # Deterministic generation
    llm_max_tokens: int = 4000  # Maximum response tokens
    llm_rate_limit: float = 1.0  # Requests per second for external APIs
    llm_timeout: int = 120  # Request timeout in seconds
    
    # LLM cache settings
    llm_cache_dir: Path = project_root / "config"
    llm_global_cache: str = "llm_corrections.db"  # Global corrections
    
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
        # Ensure base directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        self.spec_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create output session directories if set
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
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Extract identifier from PDF name
        pdf_stem = pdf_path.stem
        # Remove version numbers, dates, and common suffixes
        identifier = re.sub(r'[_\-](v\d+|version\d+|\d{4,8})', '', pdf_stem, flags=re.IGNORECASE)
        identifier = re.sub(r'[^a-zA-Z0-9]', '', identifier)[:20]  # Max 20 chars, alphanumeric only
        
        # Create session directory
        session_name = f"{timestamp}_{identifier}"
        self.output_dir = self.spec_output_dir / session_name
        self.image_dir = self.output_dir / "images"
        self.markdown_dir = self.output_dir / "markdown"
        self.json_dir = self.output_dir / "json"
        self.index_dir = self.output_dir / "index"
        
        # Create directories
        self.ensure_directories()
        
        return self.output_dir


# Global settings instance
settings = Settings()

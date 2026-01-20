"""
Tests for Settings configuration class.
"""

import pytest
from pathlib import Path

from spec_parser.config import Settings, settings


class TestSettings:
    """Tests for Settings class."""
    
    def test_settings_instance_exists(self):
        """Test that global settings instance exists."""
        assert settings is not None
        assert isinstance(settings, Settings)
    
    def test_project_paths(self):
        """Test project path defaults."""
        assert settings.project_root.exists()
        assert settings.data_dir.name == "data"
        assert settings.specs_dir.name == "specs"
        assert settings.spec_output_dir.name == "spec_output"
    
    def test_llm_settings(self):
        """Test LLM configuration defaults."""
        assert settings.llm_provider in ["ollama", "huggingface", "anthropic", "openai"]
        assert isinstance(settings.llm_model, str)
        assert settings.llm_temperature >= 0.0
        assert settings.llm_max_tokens > 0
        assert settings.llm_timeout > 0
    
    def test_ocr_settings(self):
        """Test OCR configuration defaults."""
        assert settings.ocr_language == "eng"
        assert settings.ocr_dpi >= 72
        assert 0 <= settings.ocr_confidence_threshold <= 1
    
    def test_embedding_settings(self):
        """Test embedding configuration defaults."""
        assert "MiniLM" in settings.embedding_model or "sentence-transformers" in settings.embedding_model
        assert settings.embedding_device in ["cpu", "cuda", "mps"]
        assert settings.embedding_batch_size > 0
    
    def test_search_settings(self):
        """Test search configuration defaults."""
        assert settings.search_top_k > 0
        assert 0 <= settings.hybrid_search_alpha <= 1
    
    def test_max_workers(self):
        """Test max workers setting."""
        assert settings.max_workers > 0
        assert settings.max_workers <= 32  # Reasonable upper limit
    
    def test_ensure_directories(self):
        """Test directory creation method."""
        # Should not raise
        settings.ensure_directories()
        
        assert settings.data_dir.exists()
        assert settings.specs_dir.exists()
        assert settings.spec_output_dir.exists()
    
    def test_create_output_session(self, tmp_path):
        """Test output session creation."""
        # Create a test settings instance with temp directory
        test_settings = Settings()
        test_settings.spec_output_dir = tmp_path
        
        # Create a fake PDF path
        fake_pdf = tmp_path / "test_spec_v1.pdf"
        fake_pdf.touch()
        
        # Create output session
        output_dir = test_settings.create_output_session(fake_pdf)
        
        assert output_dir.exists()
        assert output_dir.parent == tmp_path
        assert "testspec" in output_dir.name.lower() or "test" in output_dir.name.lower()
        
        # Check subdirectories created
        assert test_settings.image_dir.exists()
        assert test_settings.markdown_dir.exists()
        assert test_settings.json_dir.exists()
        assert test_settings.index_dir.exists()
    
    def test_output_session_timestamp_format(self, tmp_path):
        """Test output session uses correct timestamp format."""
        test_settings = Settings()
        test_settings.spec_output_dir = tmp_path
        
        fake_pdf = tmp_path / "device_manual.pdf"
        fake_pdf.touch()
        
        output_dir = test_settings.create_output_session(fake_pdf)
        
        # Directory name should start with timestamp YYYYMMDD_HHMMSS
        dir_name = output_dir.name
        parts = dir_name.split("_")
        
        # First part should be date (8 digits)
        assert len(parts[0]) == 8
        assert parts[0].isdigit()
        
        # Second part should be time (6 digits)
        assert len(parts[1]) == 6
        assert parts[1].isdigit()


class TestSettingsEnvironment:
    """Tests for environment variable loading."""
    
    def test_settings_from_env(self, monkeypatch):
        """Test settings can be overridden via environment."""
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("LLM_MODEL", "claude-3-opus")
        monkeypatch.setenv("MAX_WORKERS", "8")
        
        # Create new settings instance to pick up env vars
        new_settings = Settings()
        
        assert new_settings.llm_provider == "anthropic"
        assert new_settings.llm_model == "claude-3-opus"
        assert new_settings.max_workers == 8
    
    def test_settings_defaults_when_no_env(self):
        """Test settings use defaults when env vars not set."""
        # The global settings instance should have defaults
        assert settings.llm_provider is not None
        assert settings.llm_model is not None

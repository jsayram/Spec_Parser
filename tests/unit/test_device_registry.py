"""
Unit tests for device registry.

Tests device type registration and version management.
"""

import pytest
import json
from pathlib import Path
from src.spec_parser.schemas.device_registry import (
    DeviceRegistry,
    DeviceType,
    DeviceVersion,
    MessageSummary,
    create_device_version,
    load_registry
)


@pytest.fixture
def temp_registry(tmp_path):
    """Create temporary registry."""
    registry_path = tmp_path / "test_registry.json"
    return DeviceRegistry(registry_path)


@pytest.fixture
def sample_version():
    """Create sample device version."""
    return create_device_version(
        version="1.0",
        pdf_hash="abc123",
        index_path="data/index/v1",
        report_path="data/reports/baseline_v1.md",
        is_baseline=True,
        message_summary=MessageSummary(
            observation_count=5,
            config_count=3,
            field_count=50
        )
    )


class TestDeviceRegistration:
    """Test device registration operations."""
    
    def test_register_new_device(self, temp_registry, sample_version):
        device_id = temp_registry.register_device(
            vendor="Abbott",
            model="InfoHQ",
            device_name="Abbott InfoHQ Analyzer",
            version=sample_version
        )
        
        assert device_id == "Abbott_InfoHQ"
        assert temp_registry.device_exists(device_id)
    
    def test_cannot_register_duplicate(self, temp_registry, sample_version):
        temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        with pytest.raises(ValueError, match="already registered"):
            temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
    
    def test_registry_persists_to_disk(self, temp_registry, sample_version):
        temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        # Registry file should exist
        assert temp_registry.registry_path.exists()
        
        # Should be valid JSON
        with open(temp_registry.registry_path, 'r') as f:
            data = json.load(f)
        
        assert "Abbott_InfoHQ" in data


class TestVersionManagement:
    """Test version addition and tracking."""
    
    def test_add_version_to_device(self, temp_registry, sample_version):
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        new_version = create_device_version(
            version="2.0",
            pdf_hash="def456",
            index_path="data/index/v2",
            report_path="data/reports/changes_v1_to_v2.md"
        )
        
        temp_registry.update_device_version(device_id, new_version)
        
        device = temp_registry.get_device(device_id)
        assert len(device.spec_history) == 2
        assert device.current_version == "2.0"
    
    def test_cannot_add_duplicate_version(self, temp_registry, sample_version):
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        with pytest.raises(ValueError, match="already exists"):
            temp_registry.update_device_version(device_id, sample_version)
    
    def test_get_specific_version(self, temp_registry, sample_version):
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        device = temp_registry.get_device(device_id)
        version = device.get_version("1.0")
        
        assert version is not None
        assert version.version == "1.0"
        assert version.pdf_hash == "abc123"
    
    def test_get_current_version(self, temp_registry, sample_version):
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        device = temp_registry.get_device(device_id)
        current = device.get_current_version_obj()
        
        assert current is not None
        assert current.version == "1.0"


class TestVersionHistory:
    """Test version history tracking."""
    
    def test_maintains_version_order(self, temp_registry, sample_version):
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        v2 = create_device_version("2.0", "hash2", "path2", "report2")
        v3 = create_device_version("3.0", "hash3", "path3", "report3")
        
        temp_registry.update_device_version(device_id, v2)
        temp_registry.update_device_version(device_id, v3)
        
        history = temp_registry.get_version_history(device_id)
        assert len(history) == 3
        assert [v.version for v in history] == ["1.0", "2.0", "3.0"]
    
    def test_tracks_baseline_flag(self, temp_registry):
        baseline = create_device_version("1.0", "hash1", "path1", "report1", is_baseline=True)
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", baseline)
        
        device = temp_registry.get_device(device_id)
        first_version = device.spec_history[0]
        
        assert first_version.is_baseline
    
    def test_tracks_rebuild_status(self, temp_registry, sample_version):
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        # Add version with rebuild
        v2 = create_device_version(
            "2.0", "hash2", "path2", "report2",
            rebuild_performed=True,
            approval_reason="Breaking changes detected"
        )
        temp_registry.update_device_version(device_id, v2)
        
        device = temp_registry.get_device(device_id)
        v2_obj = device.get_version("2.0")
        
        assert v2_obj.rebuild_performed
        assert v2_obj.approval_reason == "Breaking changes detected"


class TestMessageSummary:
    """Test message summary tracking."""
    
    def test_tracks_message_counts(self, temp_registry):
        summary = MessageSummary(
            observation_count=10,
            config_count=5,
            vendor_count=2,
            unrecognized_count=3,
            field_count=75
        )
        
        version = create_device_version(
            "1.0", "hash", "path", "report",
            message_summary=summary
        )
        
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", version)
        device = temp_registry.get_device(device_id)
        
        v = device.get_current_version_obj()
        assert v.message_summary.observation_count == 10
        assert v.message_summary.field_count == 75


class TestRegistryQuery:
    """Test registry query operations."""
    
    def test_list_all_devices(self, temp_registry, sample_version):
        temp_registry.register_device("Abbott", "InfoHQ", "Test1", sample_version)
        
        v2 = create_device_version("1.0", "hash2", "path2", "report2")
        temp_registry.register_device("Roche", "Cobas", "Test2", v2)
        
        devices = temp_registry.list_devices()
        assert len(devices) == 2
        assert "Abbott_InfoHQ" in devices
        assert "Roche_Cobas" in devices
    
    def test_get_by_vendor_model(self, temp_registry, sample_version):
        temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        device = temp_registry.get_device_by_name("Abbott", "InfoHQ")
        assert device is not None
        assert device.vendor == "Abbott"
        assert device.model == "InfoHQ"
    
    def test_get_latest_version(self, temp_registry, sample_version):
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        v2 = create_device_version("2.0", "hash2", "path2", "report2")
        temp_registry.update_device_version(device_id, v2)
        
        latest = temp_registry.get_latest_version(device_id)
        assert latest.version == "2.0"


class TestRegistryPersistence:
    """Test registry save/load operations."""
    
    def test_auto_saves_on_register(self, temp_registry, sample_version):
        temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        # Should auto-save
        assert temp_registry.registry_path.exists()
    
    def test_auto_saves_on_update(self, temp_registry, sample_version):
        device_id = temp_registry.register_device("Abbott", "InfoHQ", "Test", sample_version)
        
        v2 = create_device_version("2.0", "hash2", "path2", "report2")
        temp_registry.update_device_version(device_id, v2)
        
        # Reload from disk
        new_registry = DeviceRegistry(temp_registry.registry_path)
        device = new_registry.get_device(device_id)
        
        assert len(device.spec_history) == 2
    
    def test_load_empty_registry(self, tmp_path):
        registry_path = tmp_path / "nonexistent.json"
        registry = DeviceRegistry(registry_path)
        
        assert len(registry.devices) == 0
    
    def test_handles_corrupted_registry(self, tmp_path):
        registry_path = tmp_path / "corrupt.json"
        registry_path.write_text("{ invalid json")
        
        # Should handle gracefully
        registry = DeviceRegistry(registry_path)
        assert len(registry.devices) == 0


class TestConvenienceFunctions:
    """Test convenience helper functions."""
    
    def test_create_device_version_with_defaults(self):
        version = create_device_version(
            version="1.0",
            pdf_hash="hash",
            index_path="path",
            report_path="report"
        )
        
        assert version.version == "1.0"
        assert version.rebuild_performed  # Default True
        assert version.impact_counts == {}
        assert isinstance(version.message_summary, MessageSummary)
    
    def test_load_registry_convenience(self, tmp_path):
        registry_path = tmp_path / "test.json"
        registry = load_registry(registry_path)
        
        assert isinstance(registry, DeviceRegistry)
        assert registry.registry_path == registry_path

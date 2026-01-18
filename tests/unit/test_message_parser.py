"""
Unit tests for message parser.

Tests POCT1 message type and field extraction from JSON sidecars.
"""

import pytest
import json
from pathlib import Path
from src.spec_parser.extractors.message_parser import (
    MessageParser,
    MessageInventory,
    MessageType,
    FieldSpec
)


@pytest.fixture
def sample_json_sidecar(tmp_path):
    """Create sample JSON sidecar for testing."""
    doc_data = [
        {
            "page": 1,
            "blocks": [
                {
                    "type": "text",
                    "block_id": 1,
                    "markdown": "The OBS.R01 message is used to send observations from device to host.",
                    "bbox": [100, 200, 500, 250],
                    "source": "text"
                },
                {
                    "type": "text",
                    "block_id": 2,
                    "markdown": "Query message QCN.R01 is sent from host to device.",
                    "bbox": [100, 300, 500, 350],
                    "source": "text"
                },
                {
                    "type": "text",
                    "block_id": 3,
                    "markdown": "Vendor-specific message Mes.custom.data.v2 for special operations.",
                    "bbox": [100, 400, 500, 450],
                    "source": "text"
                }
            ]
        },
        {
            "page": 2,
            "blocks": [
                {
                    "type": "table",
                    "block_id": 4,
                    "markdown": "| Field | Type | Opt |\n| MSH-9 | ST | R |\n| OBX-3 | CE | R |",
                    "bbox": [100, 100, 500, 200],
                    "source": "text"
                },
                {
                    "type": "text",
                    "block_id": 5,
                    "markdown": "Unrecognized segment XYZ.R99 for testing.",
                    "bbox": [100, 250, 500, 300],
                    "source": "text"
                }
            ]
        }
    ]
    
    json_path = tmp_path / "document.json"
    with open(json_path, 'w') as f:
        json.dump(doc_data, f)
    
    return json_path


class TestMessageExtraction:
    """Test message type extraction."""
    
    def test_extracts_standard_messages(self, sample_json_sidecar):
        parser = MessageParser()
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        recognized_ids = [m.message_id for m in inventory.recognized_messages]
        assert "OBS.R01" in recognized_ids
        assert "QCN.R01" in recognized_ids
    
    def test_extracts_vendor_multi_segment(self, sample_json_sidecar):
        parser = MessageParser()
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        vendor_msgs = [m for m in inventory.recognized_messages if m.category == "vendor_specific"]
        vendor_ids = [m.message_id for m in vendor_msgs]
        assert "Mes.custom.data.v2" in vendor_ids
    
    def test_flags_unrecognized_messages(self, sample_json_sidecar):
        parser = MessageParser()
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        unrecognized_ids = [m.message_id for m in inventory.unrecognized_messages]
        assert "XYZ.R99" in unrecognized_ids
    
    def test_infers_directionality(self, sample_json_sidecar):
        parser = MessageParser()
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        obs_msg = next(m for m in inventory.recognized_messages if m.message_id == "OBS.R01")
        assert obs_msg.direction == "→Host"
        
        qcn_msg = next(m for m in inventory.recognized_messages if m.message_id == "QCN.R01")
        assert qcn_msg.direction == "←Device"


class TestFieldExtraction:
    """Test field specification extraction."""
    
    def test_extracts_fields_from_tables(self, sample_json_sidecar):
        parser = MessageParser()
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        field_ids = [f.field_id for f in inventory.field_specs]
        assert "MSH-9" in field_ids
        assert "OBX-3" in field_ids
    
    def test_field_has_citation(self, sample_json_sidecar):
        parser = MessageParser()
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        field = next(f for f in inventory.field_specs if f.field_id == "MSH-9")
        assert field.citation is not None
        assert field.citation.page == 2
        assert field.citation.block_id == "4"


class TestCategorization:
    """Test message categorization."""
    
    def test_categorizes_observation_messages(self, sample_json_sidecar):
        parser = MessageParser()
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        obs_msg = next(m for m in inventory.recognized_messages if m.message_id == "OBS.R01")
        assert obs_msg.category == "observation"
    
    def test_categorizes_config_messages(self, sample_json_sidecar):
        parser = MessageParser()
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        qcn_msg = next(m for m in inventory.recognized_messages if m.message_id == "QCN.R01")
        assert qcn_msg.category in ["config", "qc"]  # QCN is in both
    
    def test_builds_category_summary(self, sample_json_sidecar):
        parser = MessageParser()
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        assert "observation" in inventory.categories
        assert "vendor_specific" in inventory.categories
        assert "unrecognized" in inventory.categories


class TestAutoAccept:
    """Test auto-accept of unrecognized messages."""
    
    def test_saves_unrecognized_to_custom_messages(self, sample_json_sidecar, tmp_path, monkeypatch):
        # Point custom_messages to temp location
        custom_path = tmp_path / "custom_messages.json"
        
        parser = MessageParser()
        monkeypatch.setattr(parser, 'custom_messages_path', custom_path)
        
        inventory = parser.parse_spec(sample_json_sidecar, "TestDevice")
        
        assert custom_path.exists()
        with open(custom_path, 'r') as f:
            custom_msgs = json.load(f)
        
        assert "TestDevice" in custom_msgs
        assert "XYZ.R99" in custom_msgs["TestDevice"]
        assert custom_msgs["TestDevice"]["XYZ.R99"]["review_status"] == "pending"


class TestAlternativePatterns:
    """Test handling of alternative message/field formats."""
    
    def test_handles_caret_format(self, tmp_path):
        """Test OBS^OBS_R01 format."""
        doc_data = [{
            "page": 1,
            "blocks": [{
                "type": "text",
                "block_id": 1,
                "markdown": "Message OBS^OBS_R01 structure",
                "bbox": [0, 0, 100, 100],
                "source": "text"
            }]
        }]
        
        json_path = tmp_path / "test.json"
        with open(json_path, 'w') as f:
            json.dump(doc_data, f)
        
        parser = MessageParser()
        inventory = parser.parse_spec(json_path, "Test")
        
        # Should normalize to OBS.R01
        msg_ids = [m.message_id for m in inventory.recognized_messages + inventory.unrecognized_messages]
        assert "OBS.R01" in msg_ids
    
    def test_handles_dot_field_separator(self, tmp_path):
        """Test MSH.9 format (dot instead of dash)."""
        doc_data = [{
            "page": 1,
            "blocks": [{
                "type": "text",
                "block_id": 1,
                "markdown": "Field MSH.9 contains message type",
                "bbox": [0, 0, 100, 100],
                "source": "text"
            }]
        }]
        
        json_path = tmp_path / "test.json"
        with open(json_path, 'w') as f:
            json.dump(doc_data, f)
        
        parser = MessageParser()
        inventory = parser.parse_spec(json_path, "Test")
        
        # Should normalize to MSH-9
        field_ids = [f.field_id for f in inventory.field_specs]
        assert "MSH-9" in field_ids


class TestVendorPatterns:
    """Test vendor extension pattern matching."""
    
    def test_z_segment_patterns(self, tmp_path):
        """Test various Z** vendor formats."""
        doc_data = [{
            "page": 1,
            "blocks": [
                {"type": "text", "block_id": 1, "markdown": "ZXX segment", "bbox": [0, 0, 100, 100], "source": "text"},
                {"type": "text", "block_id": 2, "markdown": "ZABC segment", "bbox": [0, 0, 100, 100], "source": "text"},
                {"type": "text", "block_id": 3, "markdown": "Z12 segment", "bbox": [0, 0, 100, 100], "source": "text"}
            ]
        }]
        
        json_path = tmp_path / "test.json"
        with open(json_path, 'w') as f:
            json.dump(doc_data, f)
        
        parser = MessageParser()
        inventory = parser.parse_spec(json_path, "Test")
        
        # All should be categorized as vendor
        vendor_msgs = [m for m in inventory.recognized_messages if m.category == "vendor_specific"]
        assert len(vendor_msgs) >= 1  # At least one vendor message detected

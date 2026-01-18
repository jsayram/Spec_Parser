"""
Unit tests for impact classifier.

Tests change classification logic for HIGH, MEDIUM, and LOW impact.
"""

import pytest
from src.spec_parser.validation.impact_classifier import (
    classify_change,
    ImpactLevel,
    ChangeType,
    _contains_message_type,
    _contains_field_definition,
    _extract_message_types,
    _extract_field_info,
    _extract_optionality,
    _is_required_field,
    _contains_vendor_extension
)


class TestMessageTypeDetection:
    """Test message type pattern detection."""
    
    def test_detects_standard_message_type(self):
        content = "The OBS.R01 message is used for observations"
        assert _contains_message_type(content)
    
    def test_extracts_message_types(self):
        content = "Supports OBS.R01, QCN.R01, and ORU.R01 messages"
        result = _extract_message_types(content)
        assert "OBS" in result
        assert "QCN" in result
        assert "ORU" in result
    
    def test_no_message_type(self):
        content = "This is just documentation text"
        assert not _contains_message_type(content)


class TestFieldDetection:
    """Test field pattern detection."""
    
    def test_detects_field_definition(self):
        content = "MSH-9 contains the message type"
        assert _contains_field_definition(content)
    
    def test_extracts_field_info(self):
        content = "Fields: MSH-9, OBX-3, PID-5"
        result = _extract_field_info(content)
        assert "MSH-9" in result
        assert "OBX-3" in result
    
    def test_detects_required_field(self):
        content = "Field: MSH-9, Type: ST, Optionality: R"
        assert _is_required_field(content)
    
    def test_detects_optional_field(self):
        content = "Field: OBX-17, Type: CE, Optionality: O"
        assert not _is_required_field(content)


class TestVendorExtensions:
    """Test vendor extension detection."""
    
    def test_detects_z_segment(self):
        content = "Vendor segment ZAB is supported"
        assert _contains_vendor_extension(content)
    
    def test_no_vendor_extension(self):
        content = "Standard MSH segment only"
        assert not _contains_vendor_extension(content)


class TestHighImpactChanges:
    """Test HIGH impact change classification."""
    
    def test_message_added(self):
        result = classify_change(
            old_content=None,
            new_content="New message type OBS.R02 added",
            block_type="text"
        )
        assert result.level == ImpactLevel.HIGH
        assert result.change_type == ChangeType.MESSAGE_ADDED
    
    def test_message_removed(self):
        result = classify_change(
            old_content="Message type QCN.R01 definition",
            new_content=None,
            block_type="text"
        )
        assert result.level == ImpactLevel.HIGH
        assert result.change_type == ChangeType.MESSAGE_REMOVED
    
    def test_field_type_changed(self):
        old = "Field: PatientID, Type: ST, Opt: R"
        new = "Field: PatientID, Type: CX, Opt: R"
        result = classify_change(old, new, "table")
        assert result.level == ImpactLevel.HIGH
        assert result.change_type == ChangeType.FIELD_TYPE_CHANGED
    
    def test_cardinality_changed(self):
        old = "Field: SampleID, Type: ST, Opt: R"
        new = "Field: SampleID, Type: ST, Opt: O"
        result = classify_change(old, new, "table")
        assert result.level == ImpactLevel.HIGH
        assert result.change_type == ChangeType.CARDINALITY_CHANGED


class TestMediumImpactChanges:
    """Test MEDIUM impact change classification."""
    
    def test_optional_field_added(self):
        result = classify_change(
            old_content=None,
            new_content="New optional field: Comment, Type: TX, Opt: O",
            block_type="table"
        )
        assert result.level == ImpactLevel.MEDIUM
        assert result.change_type == ChangeType.FIELD_ADDED
    
    def test_vendor_extension_added(self):
        result = classify_change(
            old_content=None,
            new_content="Vendor extension ZXX added for custom data",
            block_type="text"
        )
        assert result.level == ImpactLevel.MEDIUM
        assert result.change_type == ChangeType.VENDOR_EXTENSION_MODIFIED
    
    def test_table_structure_changed(self):
        old = "| Field | Type | Opt |\n| MSH-9 | ST | R |"
        new = "| Field | Type | Opt | Length |\n| MSH-9 | ST | R | 20 |"
        result = classify_change(old, new, "table")
        assert result.level == ImpactLevel.MEDIUM
        assert result.change_type == ChangeType.TABLE_STRUCTURE_CHANGED


class TestLowImpactChanges:
    """Test LOW impact change classification."""
    
    def test_whitespace_only(self):
        old = "Field: MSH-9"
        new = "Field:  MSH-9  "
        result = classify_change(old, new, "text")
        assert result.level == ImpactLevel.LOW
        assert result.change_type == ChangeType.WHITESPACE_CHANGED
    
    def test_typo_correction(self):
        old = "This mesage is used for observations"
        new = "This message is used for observations"
        result = classify_change(old, new, "text")
        assert result.level == ImpactLevel.LOW
        assert result.change_type == ChangeType.TYPO_FIXED
    
    def test_documentation_update(self):
        old = "This field contains patient data"
        new = "This field contains patient demographic information"
        result = classify_change(old, new, "text")
        assert result.level == ImpactLevel.LOW
        assert result.change_type == ChangeType.DOCUMENTATION_UPDATED


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_no_change(self):
        content = "Same content"
        result = classify_change(content, content, "text")
        assert result.level == ImpactLevel.LOW
    
    def test_empty_content(self):
        result = classify_change("", "", "text")
        assert result.level == ImpactLevel.LOW
    
    def test_case_change_only(self):
        result = classify_change("PATIENT ID", "Patient ID", "text")
        assert result.level == ImpactLevel.LOW
        assert result.change_type == ChangeType.TYPO_FIXED


class TestContextualClassification:
    """Test classification with context."""
    
    def test_with_context_metadata(self):
        context = {"field_name": "PatientID", "is_critical": True}
        result = classify_change(
            old_content="Type: ST",
            new_content="Type: CX",
            block_type="table",
            context=context
        )
        assert result.level == ImpactLevel.HIGH
    
    def test_block_type_affects_classification(self):
        # Same change in different block types
        change = "Some content modification"
        
        text_result = classify_change("old", change, "text")
        table_result = classify_change("old", change, "table")
        
        # Table changes often have higher impact
        assert table_result.level in [ImpactLevel.MEDIUM, ImpactLevel.HIGH]

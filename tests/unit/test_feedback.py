"""
Unit tests for feedback storage and retrieval.

Tests FeedbackStore for human review data and retraining examples.
"""

import json
from pathlib import Path

import pytest

from spec_parser.schemas.audit import FeedbackType
from spec_parser.search.feedback import FeedbackStore


class TestFeedbackStore:
    """Tests for FeedbackStore class."""

    def test_init_creates_empty_store(self, tmp_path: Path):
        """Test initializing a new feedback store."""
        store = FeedbackStore(tmp_path)
        
        assert store.record_count == 0
        assert not store.feedback_file.exists()

    def test_add_correction_feedback(self, tmp_path: Path):
        """Test adding a correction feedback record."""
        store = FeedbackStore(tmp_path)
        
        record = store.add_feedback(
            extraction_id="ext_123",
            block_hash="hash_456",
            page=5,
            bbox=[10.0, 20.0, 100.0, 200.0],
            original_content="Incorect text",
            original_confidence=0.65,
            source_type="ocr",
            feedback_type=FeedbackType.CORRECTION,
            corrected_content="Incorrect text",
            reviewer_id="user_abc",
        )
        
        assert record.feedback_id.startswith("fb_")
        assert record.feedback_type == FeedbackType.CORRECTION
        assert record.corrected_content == "Incorrect text"
        assert store.record_count == 1

    def test_add_confirmation_feedback(self, tmp_path: Path):
        """Test adding a confirmation feedback record."""
        store = FeedbackStore(tmp_path)
        
        record = store.add_feedback(
            extraction_id="ext_123",
            block_hash="hash_789",
            page=3,
            bbox=[0, 0, 50, 50],
            original_content="Correct text",
            original_confidence=0.9,
            source_type="ocr",
            feedback_type=FeedbackType.CONFIRMATION,
        )
        
        assert record.feedback_type == FeedbackType.CONFIRMATION
        assert store.record_count == 1

    def test_feedback_persisted_to_disk(self, tmp_path: Path):
        """Test that feedback is saved to disk."""
        store = FeedbackStore(tmp_path)
        
        store.add_feedback(
            extraction_id="ext_123",
            block_hash="hash_456",
            page=1,
            bbox=[0, 0, 100, 100],
            original_content="Test",
            original_confidence=0.7,
            source_type="ocr",
            feedback_type=FeedbackType.CORRECTION,
            corrected_content="Fixed",
        )
        
        # Check file exists and contains data
        assert store.feedback_file.exists()
        
        with open(store.feedback_file) as f:
            data = json.load(f)
        
        assert data["total_records"] == 1
        assert len(data["feedback"]) == 1
        assert data["feedback"][0]["corrected_content"] == "Fixed"

    def test_load_existing_feedback(self, tmp_path: Path):
        """Test loading feedback from existing file."""
        # Create and populate a store
        store1 = FeedbackStore(tmp_path)
        store1.add_feedback(
            extraction_id="ext_1",
            block_hash="hash_1",
            page=1,
            bbox=[0, 0, 100, 100],
            original_content="Original",
            original_confidence=0.6,
            source_type="ocr",
            feedback_type=FeedbackType.CORRECTION,
            corrected_content="Corrected",
        )
        
        # Create new store from same directory
        store2 = FeedbackStore(tmp_path)
        
        assert store2.record_count == 1

    def test_get_training_data_corrections(self, tmp_path: Path):
        """Test getting training data from corrections."""
        store = FeedbackStore(tmp_path)
        
        store.add_feedback(
            extraction_id="ext_1",
            block_hash="hash_1",
            page=1,
            bbox=[0, 0, 100, 100],
            original_content="Wrng",
            original_confidence=0.5,
            source_type="ocr",
            feedback_type=FeedbackType.CORRECTION,
            corrected_content="Wrong",
        )
        
        training_data = store.get_training_data()
        
        assert len(training_data) == 1
        assert training_data[0]["original"] == "Wrng"
        assert training_data[0]["corrected"] == "Wrong"

    def test_get_training_data_confirmations(self, tmp_path: Path):
        """Test getting training data from confirmations."""
        store = FeedbackStore(tmp_path)
        
        store.add_feedback(
            extraction_id="ext_1",
            block_hash="hash_1",
            page=1,
            bbox=[0, 0, 100, 100],
            original_content="Correct",
            original_confidence=0.7,
            source_type="ocr",
            feedback_type=FeedbackType.CONFIRMATION,
        )
        
        training_data = store.get_training_data()
        
        assert len(training_data) == 1
        assert training_data[0]["original"] == "Correct"
        assert training_data[0]["corrected"] == "Correct"  # Same for confirmation
        assert training_data[0]["confidence"] == 1.0  # Bumped to 1.0

    def test_exclude_from_training(self, tmp_path: Path):
        """Test excluding feedback from training data."""
        store = FeedbackStore(tmp_path)
        
        store.add_feedback(
            extraction_id="ext_1",
            block_hash="hash_1",
            page=1,
            bbox=[0, 0, 100, 100],
            original_content="Test",
            original_confidence=0.6,
            source_type="ocr",
            feedback_type=FeedbackType.CORRECTION,
            corrected_content="Fixed",
            include_in_training=False,  # Excluded
        )
        
        training_data = store.get_training_data()
        
        assert len(training_data) == 0

    def test_get_records_by_type(self, tmp_path: Path):
        """Test filtering records by feedback type."""
        store = FeedbackStore(tmp_path)
        
        # Add multiple records of different types
        store.add_feedback(
            extraction_id="ext_1", block_hash="h1", page=1, bbox=[0, 0, 100, 100],
            original_content="A", original_confidence=0.5, source_type="ocr",
            feedback_type=FeedbackType.CORRECTION, corrected_content="B",
        )
        store.add_feedback(
            extraction_id="ext_2", block_hash="h2", page=2, bbox=[0, 0, 100, 100],
            original_content="C", original_confidence=0.8, source_type="ocr",
            feedback_type=FeedbackType.CONFIRMATION,
        )
        store.add_feedback(
            extraction_id="ext_3", block_hash="h3", page=3, bbox=[0, 0, 100, 100],
            original_content="D", original_confidence=0.3, source_type="ocr",
            feedback_type=FeedbackType.REJECTION,
        )
        
        corrections = store.get_records_by_type(FeedbackType.CORRECTION)
        confirmations = store.get_records_by_type(FeedbackType.CONFIRMATION)
        rejections = store.get_records_by_type(FeedbackType.REJECTION)
        
        assert len(corrections) == 1
        assert len(confirmations) == 1
        assert len(rejections) == 1

    def test_get_records_by_extraction(self, tmp_path: Path):
        """Test filtering records by extraction ID."""
        store = FeedbackStore(tmp_path)
        
        # Add records for different extractions
        store.add_feedback(
            extraction_id="ext_A", block_hash="h1", page=1, bbox=[0, 0, 100, 100],
            original_content="A", original_confidence=0.5, source_type="ocr",
            feedback_type=FeedbackType.CORRECTION, corrected_content="B",
        )
        store.add_feedback(
            extraction_id="ext_A", block_hash="h2", page=2, bbox=[0, 0, 100, 100],
            original_content="C", original_confidence=0.6, source_type="ocr",
            feedback_type=FeedbackType.CORRECTION, corrected_content="D",
        )
        store.add_feedback(
            extraction_id="ext_B", block_hash="h3", page=1, bbox=[0, 0, 100, 100],
            original_content="E", original_confidence=0.7, source_type="ocr",
            feedback_type=FeedbackType.CONFIRMATION,
        )
        
        records_a = store.get_records_by_extraction("ext_A")
        records_b = store.get_records_by_extraction("ext_B")
        
        assert len(records_a) == 2
        assert len(records_b) == 1

    def test_get_stats(self, tmp_path: Path):
        """Test getting feedback statistics."""
        store = FeedbackStore(tmp_path)
        
        store.add_feedback(
            extraction_id="ext_1", block_hash="h1", page=1, bbox=[0, 0, 100, 100],
            original_content="A", original_confidence=0.5, source_type="ocr",
            feedback_type=FeedbackType.CORRECTION, corrected_content="B",
        )
        store.add_feedback(
            extraction_id="ext_2", block_hash="h2", page=2, bbox=[0, 0, 100, 100],
            original_content="C", original_confidence=0.9, source_type="ocr",
            feedback_type=FeedbackType.CONFIRMATION,
        )
        
        stats = store.get_stats()
        
        assert stats["total_records"] == 2
        assert stats["by_type"]["correction"] == 1
        assert stats["by_type"]["confirmation"] == 1
        assert stats["training_examples"] == 2
        assert stats["avg_original_confidence"] == 0.7  # (0.5 + 0.9) / 2

    def test_empty_stats(self, tmp_path: Path):
        """Test getting stats from empty store."""
        store = FeedbackStore(tmp_path)
        
        stats = store.get_stats()
        
        assert stats["total_records"] == 0
        assert stats["training_examples"] == 0
        assert stats["avg_original_confidence"] == 0.0

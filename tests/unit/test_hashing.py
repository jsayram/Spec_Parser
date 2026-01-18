"""
Unit tests for cryptographic hashing utilities.

Tests SHA-256 hashing for PDFs, content blocks, and integrity verification.
"""

import tempfile
from pathlib import Path

import pytest

from spec_parser.utils.hashing import (
    compute_file_hash,
    compute_content_hash,
    compute_block_hash,
    compute_extraction_hash,
    verify_file_hash,
)


class TestComputeFileHash:
    """Tests for compute_file_hash function."""

    def test_hash_text_file(self, tmp_path: Path):
        """Test hashing a text file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        hash_result = compute_file_hash(test_file)
        
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA-256 produces 64 hex chars
        # Known SHA-256 hash for "Hello, World!"
        assert hash_result == "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"

    def test_hash_binary_file(self, tmp_path: Path):
        """Test hashing a binary file."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")
        
        hash_result = compute_file_hash(test_file)
        
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64

    def test_hash_empty_file(self, tmp_path: Path):
        """Test hashing an empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        hash_result = compute_file_hash(test_file)
        
        # Known SHA-256 hash for empty string
        assert hash_result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_hash_large_file(self, tmp_path: Path):
        """Test hashing a large file (tests chunked reading)."""
        test_file = tmp_path / "large.bin"
        # Create 1MB file
        test_file.write_bytes(b"x" * (1024 * 1024))
        
        hash_result = compute_file_hash(test_file)
        
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64

    def test_hash_nonexistent_file(self, tmp_path: Path):
        """Test hashing a file that doesn't exist."""
        nonexistent = tmp_path / "nonexistent.txt"
        
        with pytest.raises(FileNotFoundError):
            compute_file_hash(nonexistent)

    def test_hash_consistency(self, tmp_path: Path):
        """Test that same content produces same hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Consistent content")
        
        hash1 = compute_file_hash(test_file)
        hash2 = compute_file_hash(test_file)
        
        assert hash1 == hash2


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    def test_hash_string(self):
        """Test hashing a string."""
        result = compute_content_hash("test content")
        
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_bytes(self):
        """Test hashing bytes."""
        result = compute_content_hash(b"test content")
        
        assert isinstance(result, str)
        assert len(result) == 64

    def test_string_and_bytes_match(self):
        """Test that string and equivalent bytes produce same hash."""
        string_hash = compute_content_hash("test")
        bytes_hash = compute_content_hash(b"test")
        
        assert string_hash == bytes_hash

    def test_hash_empty_string(self):
        """Test hashing empty string."""
        result = compute_content_hash("")
        
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_hash_unicode(self):
        """Test hashing unicode content."""
        result = compute_content_hash("Hello 世界 🌍")
        
        assert isinstance(result, str)
        assert len(result) == 64


class TestComputeBlockHash:
    """Tests for compute_block_hash function."""

    def test_hash_complete_block(self):
        """Test hashing a block with all fields."""
        block = {
            "content": "Test content",
            "page": 5,
            "bbox": [10.5, 20.5, 100.5, 200.5],
            "source": "text",
        }
        
        result = compute_block_hash(block)
        
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_block_with_text_field(self):
        """Test hashing a block using 'text' instead of 'content'."""
        block = {
            "text": "Test content",
            "page": 5,
            "bbox": [10.5, 20.5, 100.5, 200.5],
            "source": "ocr",
        }
        
        result = compute_block_hash(block)
        
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_minimal_block(self):
        """Test hashing a block with minimal fields."""
        block = {"content": "Test"}
        
        result = compute_block_hash(block)
        
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_deterministic(self):
        """Test that same block produces same hash."""
        block = {
            "content": "Test",
            "page": 1,
            "bbox": [0, 0, 100, 100],
            "source": "text",
        }
        
        hash1 = compute_block_hash(block)
        hash2 = compute_block_hash(block)
        
        assert hash1 == hash2

    def test_different_blocks_different_hashes(self):
        """Test that different blocks produce different hashes."""
        block1 = {"content": "Test 1", "page": 1}
        block2 = {"content": "Test 2", "page": 1}
        
        assert compute_block_hash(block1) != compute_block_hash(block2)


class TestComputeExtractionHash:
    """Tests for compute_extraction_hash function."""

    def test_hash_extraction(self):
        """Test hashing a list of blocks."""
        blocks = [
            {"content": "Block 1", "page": 1, "source": "text"},
            {"content": "Block 2", "page": 2, "source": "ocr"},
        ]
        
        result = compute_extraction_hash(blocks)
        
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_empty_extraction(self):
        """Test hashing empty extraction."""
        result = compute_extraction_hash([])
        
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_order_independent(self):
        """Test that block order doesn't affect hash (sorted internally)."""
        blocks1 = [
            {"content": "A", "page": 1},
            {"content": "B", "page": 2},
        ]
        blocks2 = [
            {"content": "B", "page": 2},
            {"content": "A", "page": 1},
        ]
        
        # Should be same because block hashes are sorted
        assert compute_extraction_hash(blocks1) == compute_extraction_hash(blocks2)


class TestVerifyFileHash:
    """Tests for verify_file_hash function."""

    def test_verify_correct_hash(self, tmp_path: Path):
        """Test verification with correct hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        expected_hash = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        
        result = verify_file_hash(test_file, expected_hash)
        
        assert result is True

    def test_verify_incorrect_hash(self, tmp_path: Path):
        """Test verification with incorrect hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        
        result = verify_file_hash(test_file, wrong_hash)
        
        assert result is False

    def test_verify_case_insensitive(self, tmp_path: Path):
        """Test that hash verification is case-insensitive."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        uppercase_hash = "DFFD6021BB2BD5B0AF676290809EC3A53191DD81C7F70A4B28688A362182986F"
        
        result = verify_file_hash(test_file, uppercase_hash)
        
        assert result is True

    def test_verify_nonexistent_file(self, tmp_path: Path):
        """Test verification of nonexistent file."""
        nonexistent = tmp_path / "nonexistent.txt"
        
        result = verify_file_hash(nonexistent, "somehash")
        
        assert result is False

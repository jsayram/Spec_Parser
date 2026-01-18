"""
Cryptographic hashing utilities for content verification.

Provides SHA-256 hashing for PDFs and content blocks to ensure
data integrity and traceability in medical-grade applications.
"""

import hashlib
from pathlib import Path
from typing import Union, Dict, Any, List


def compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA-256 hash of a file.
    
    Args:
        file_path: Path to the file to hash.
        
    Returns:
        Hex-encoded SHA-256 hash string.
        
    Raises:
        FileNotFoundError: If file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        # Read in 64KB chunks for memory efficiency
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)
    
    return sha256_hash.hexdigest()


def compute_content_hash(content: Union[str, bytes]) -> str:
    """
    Compute SHA-256 hash of content.
    
    Args:
        content: String or bytes content to hash.
        
    Returns:
        Hex-encoded SHA-256 hash string.
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    
    return hashlib.sha256(content).hexdigest()


def compute_block_hash(block: Dict[str, Any]) -> str:
    """
    Compute deterministic hash of a content block.
    
    Includes content, page, bbox, and source type for full provenance.
    
    Args:
        block: Dictionary containing block data with keys like
               'content', 'page', 'bbox', 'source'.
               
    Returns:
        Hex-encoded SHA-256 hash string.
    """
    # Build deterministic string from block components
    components = []
    
    # Content
    content = block.get("content") or block.get("text") or ""
    components.append(f"content:{content}")
    
    # Page number
    page = block.get("page", 0)
    components.append(f"page:{page}")
    
    # Bounding box (normalized to string)
    bbox = block.get("bbox", [])
    if bbox:
        bbox_str = ",".join(f"{v:.2f}" for v in bbox)
        components.append(f"bbox:{bbox_str}")
    
    # Source type
    source = block.get("source", "unknown")
    components.append(f"source:{source}")
    
    # Join with delimiter and hash
    combined = "|".join(components)
    return compute_content_hash(combined)


def compute_extraction_hash(blocks: List[Dict[str, Any]]) -> str:
    """
    Compute hash of entire extraction result for integrity verification.
    
    Args:
        blocks: List of all extracted content blocks.
        
    Returns:
        Hex-encoded SHA-256 hash of combined block hashes.
    """
    if not blocks:
        return compute_content_hash("empty_extraction")
    
    # Hash each block and combine
    block_hashes = [compute_block_hash(block) for block in blocks]
    combined = "|".join(sorted(block_hashes))  # Sort for determinism
    
    return compute_content_hash(combined)


def verify_file_hash(file_path: Path, expected_hash: str) -> bool:
    """
    Verify file integrity against expected hash.
    
    Args:
        file_path: Path to file to verify.
        expected_hash: Expected SHA-256 hash.
        
    Returns:
        True if hash matches, False otherwise.
    """
    try:
        actual_hash = compute_file_hash(file_path)
        return actual_hash.lower() == expected_hash.lower()
    except FileNotFoundError:
        return False

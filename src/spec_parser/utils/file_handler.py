"""
Cross-platform file handling utilities using pathlib.

All file operations use Path objects for cross-platform compatibility.
"""

import json
from pathlib import Path
from typing import Any, Dict
from loguru import logger

from spec_parser.exceptions import FileHandlerError


def ensure_directory(path: Path) -> Path:
    """
    Ensure directory exists, create if needed.
    
    Args:
        path: Directory path
        
    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_file(file_path: Path, encoding: str = "utf-8") -> str:
    """
    Read text file.
    
    Args:
        file_path: Path to file
        encoding: Text encoding
        
    Returns:
        File contents as string
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileHandlerError(f"File not found: {file_path}")
    
    try:
        return file_path.read_text(encoding=encoding)
    except Exception as e:
        raise FileHandlerError(f"Failed to read {file_path}: {e}")


def write_file(content: str, file_path: Path, encoding: str = "utf-8"):
    """
    Write text file.
    
    Args:
        content: Text content to write
        file_path: Path to file
        encoding: Text encoding
    """
    file_path = Path(file_path)
    ensure_directory(file_path.parent)
    
    try:
        file_path.write_text(content, encoding=encoding)
        logger.debug(f"Wrote file: {file_path}")
    except Exception as e:
        raise FileHandlerError(f"Failed to write {file_path}: {e}")


def read_json(file_path: Path) -> Dict[str, Any]:
    """
    Read JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Parsed JSON as dict
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileHandlerError(f"File not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise FileHandlerError(f"Invalid JSON in {file_path}: {e}")
    except Exception as e:
        raise FileHandlerError(f"Failed to read {file_path}: {e}")


def write_json(data: Dict[str, Any], file_path: Path, indent: int = 2):
    """
    Write JSON file.
    
    Args:
        data: Data to write
        file_path: Path to JSON file
        indent: JSON indentation
    """
    file_path = Path(file_path)
    ensure_directory(file_path.parent)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        logger.debug(f"Wrote JSON: {file_path}")
    except Exception as e:
        raise FileHandlerError(f"Failed to write {file_path}: {e}")


def list_files(directory: Path, pattern: str = "*", recursive: bool = False) -> list[Path]:
    """
    List files in directory matching pattern.
    
    Args:
        directory: Directory to search
        pattern: Glob pattern (e.g., "*.pdf")
        recursive: Whether to search recursively
        
    Returns:
        List of matching file paths
    """
    directory = Path(directory)
    
    if not directory.exists():
        raise FileHandlerError(f"Directory not found: {directory}")
    
    if not directory.is_dir():
        raise FileHandlerError(f"Not a directory: {directory}")
    
    if recursive:
        return sorted(directory.rglob(pattern))
    else:
        return sorted(directory.glob(pattern))


def file_size(file_path: Path) -> int:
    """
    Get file size in bytes.
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in bytes
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileHandlerError(f"File not found: {file_path}")
    
    return file_path.stat().st_size


def safe_filename(name: str, replacement: str = "_") -> str:
    """
    Create safe filename by replacing invalid characters.
    
    Args:
        name: Original filename
        replacement: Character to use for replacements
        
    Returns:
        Safe filename
    """
    import re
    
    # Replace invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', replacement, name)
    
    # Trim leading/trailing spaces and dots
    safe = safe.strip('. ')
    
    # Ensure not empty
    if not safe:
        safe = "unnamed"
    
    return safe

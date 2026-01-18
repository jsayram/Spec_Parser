"""
Base extractor class for entity extraction.

All entity extractors inherit from this to ensure consistent interface.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path
from loguru import logger

from ..parsers.table_parser import ParsedTable


class BaseExtractor(ABC):
    """Base class for all entity extractors"""
    
    def __init__(self):
        self.extracted_entities: List[Dict[str, Any]] = []
    
    @abstractmethod
    def extract(self, tables: List[ParsedTable], 
                markdown_content: str, 
                json_data: dict) -> List[Dict[str, Any]]:
        """
        Extract entities from document.
        
        Args:
            tables: List of parsed tables
            markdown_content: Full markdown content (usually master MD)
            json_data: Full JSON sidecar data
        
        Returns:
            List of extracted entities
        """
        pass
    
    def save(self, output_path: Path) -> None:
        """
        Save extracted entities to JSON file.
        
        Args:
            output_path: Path to save JSON file
        """
        import json
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(
                {self.entity_type(): self.extracted_entities},
                f,
                indent=2,
                ensure_ascii=False
            )
        
        logger.info(f"Saved {len(self.extracted_entities)} {self.entity_type()} to {output_path}")
    
    @abstractmethod
    def entity_type(self) -> str:
        """Return entity type name (e.g., 'messages', 'fields')"""
        pass
    
    def get_entities(self) -> List[Dict[str, Any]]:
        """Return extracted entities"""
        return self.extracted_entities
    
    def get_entity_count(self) -> int:
        """Return count of extracted entities"""
        return len(self.extracted_entities)

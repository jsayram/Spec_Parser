"""
Feedback storage for human review and retraining data.

Stores human feedback on extracted content in JSON format,
one file per index, for future model improvement.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from loguru import logger
from pydantic import BaseModel

from ..schemas.audit import FeedbackRecord, FeedbackType


class FeedbackStore:
    """
    Manages feedback storage for an index.
    
    Stores feedback in JSON format, one file per index.
    Supports querying for retraining data.
    """
    
    def __init__(self, index_dir: Path):
        """
        Initialize feedback store.
        
        Args:
            index_dir: Directory containing the index.
        """
        self.index_dir = Path(index_dir)
        self.feedback_file = self.index_dir / "feedback.json"
        self._records: List[FeedbackRecord] = []
        self._load()
    
    def _load(self) -> None:
        """Load existing feedback from disk."""
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, "r") as f:
                    data = json.load(f)
                
                self._records = [
                    FeedbackRecord(**record) 
                    for record in data.get("feedback", [])
                ]
                logger.debug(f"Loaded {len(self._records)} feedback records")
            except Exception as e:
                logger.warning(f"Failed to load feedback: {e}")
                self._records = []
        else:
            self._records = []
    
    def _save(self) -> None:
        """Save feedback to disk."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "total_records": len(self._records),
            "feedback": [
                record.model_dump(mode="json") 
                for record in self._records
            ]
        }
        
        with open(self.feedback_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.debug(f"Saved {len(self._records)} feedback records")
    
    def add_feedback(
        self,
        extraction_id: str,
        block_hash: str,
        page: int,
        bbox: List[float],
        original_content: str,
        original_confidence: float,
        source_type: str,
        feedback_type: FeedbackType,
        corrected_content: Optional[str] = None,
        reviewer_notes: Optional[str] = None,
        reviewer_id: Optional[str] = None,
        include_in_training: bool = True,
    ) -> FeedbackRecord:
        """
        Add a feedback record.
        
        Args:
            extraction_id: ID of the extraction.
            block_hash: Hash of the block.
            page: Page number.
            bbox: Bounding box.
            original_content: Original extracted content.
            original_confidence: Original OCR confidence.
            source_type: Source type (text, ocr, graphics).
            feedback_type: Type of feedback.
            corrected_content: Corrected content if applicable.
            reviewer_notes: Optional reviewer notes.
            reviewer_id: Optional reviewer identifier.
            include_in_training: Whether to include in retraining.
            
        Returns:
            Created FeedbackRecord.
        """
        record = FeedbackRecord(
            feedback_id=f"fb_{uuid.uuid4().hex[:12]}",
            extraction_id=extraction_id,
            block_hash=block_hash,
            page=page,
            bbox=bbox,
            original_content=original_content,
            original_confidence=original_confidence,
            source_type=source_type,
            feedback_type=feedback_type,
            corrected_content=corrected_content,
            reviewer_notes=reviewer_notes,
            reviewer_id=reviewer_id,
            include_in_training=include_in_training,
        )
        
        self._records.append(record)
        self._save()
        
        logger.info(f"Added feedback {record.feedback_id}: {feedback_type.value}")
        return record
    
    def get_training_data(self) -> List[Dict[str, Any]]:
        """
        Get feedback records suitable for retraining.
        
        Returns:
            List of training examples with original and corrected content.
        """
        training_data = []
        
        for record in self._records:
            if not record.include_in_training:
                continue
            
            if record.feedback_type == FeedbackType.CORRECTION:
                if record.corrected_content:
                    training_data.append({
                        "original": record.original_content,
                        "corrected": record.corrected_content,
                        "confidence": record.original_confidence,
                        "source_type": record.source_type,
                    })
            elif record.feedback_type == FeedbackType.CONFIRMATION:
                # Confirmed correct - use as positive example
                training_data.append({
                    "original": record.original_content,
                    "corrected": record.original_content,  # Same
                    "confidence": 1.0,  # Confirmed correct
                    "source_type": record.source_type,
                })
        
        return training_data
    
    def get_records_by_type(
        self, 
        feedback_type: FeedbackType
    ) -> List[FeedbackRecord]:
        """Get all records of a specific type."""
        return [r for r in self._records if r.feedback_type == feedback_type]
    
    def get_records_by_extraction(
        self, 
        extraction_id: str
    ) -> List[FeedbackRecord]:
        """Get all records for a specific extraction."""
        return [r for r in self._records if r.extraction_id == extraction_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        stats = {
            "total_records": len(self._records),
            "by_type": {},
            "training_examples": 0,
            "avg_original_confidence": 0.0,
        }
        
        for ftype in FeedbackType:
            count = len(self.get_records_by_type(ftype))
            stats["by_type"][ftype.value] = count
        
        stats["training_examples"] = len(self.get_training_data())
        
        if self._records:
            stats["avg_original_confidence"] = sum(
                r.original_confidence for r in self._records
            ) / len(self._records)
        
        return stats
    
    @property
    def record_count(self) -> int:
        """Get total number of feedback records."""
        return len(self._records)

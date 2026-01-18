"""
Citation model with mandatory provenance tracking.

Every extracted element MUST have a citation linking back to exact source location.
"""

from typing import Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class Citation(BaseModel):
    """
    Citation with complete provenance for extracted content.
    
    Every piece of extracted data must include:
    - Exact page number
    - Bounding box coordinates
    - Source type (text/ocr/graphics)
    - Content type classification
    """
    
    citation_id: str = Field(
        ...,
        description="Unique citation identifier (e.g., 'p12_txt3', 'p12_img1')"
    )
    page: int = Field(
        ...,
        ge=1,
        description="Page number (1-indexed)"
    )
    bbox: Tuple[float, float, float, float] = Field(
        ...,
        description="Bounding box coordinates (x0, y0, x1, y1)"
    )
    source: str = Field(
        ...,
        description="Source type: 'text', 'ocr', or 'graphics'"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score for OCR results (0-1)"
    )
    content_type: str = Field(
        ...,
        description="Content type: 'text', 'picture', 'table', 'graphics'"
    )
    file_reference: Optional[str] = Field(
        None,
        description="Reference to extracted file (e.g., 'page12_img3.png')"
    )
    content_hash: Optional[str] = Field(
        None,
        description="SHA-256 hash of content for integrity verification"
    )
    requires_human_review: bool = Field(
        False,
        description="Flag indicating content needs human review (OCR confidence 0.5-0.8)"
    )
    confidence_level: Optional[str] = Field(
        None,
        description="OCR confidence classification: 'accepted', 'review', or 'rejected'"
    )
    
    @field_validator('bbox')
    @classmethod
    def validate_bbox(cls, v: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """Validate bounding box coordinates (allow zero-area bboxes for lines/points)"""
        x0, y0, x1, y1 = v
        if x1 < x0:
            raise ValueError(f"Invalid bbox: x1 ({x1}) must be >= x0 ({x0})")
        if y1 < y0:
            raise ValueError(f"Invalid bbox: y1 ({y1}) must be >= y0 ({y0})")
        return v
    
    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Validate source type"""
        valid_sources = {'text', 'ocr', 'graphics'}
        if v not in valid_sources:
            raise ValueError(f"Invalid source: {v}. Must be one of {valid_sources}")
        return v
    
    def to_markdown_footnote(self) -> str:
        """
        Generate markdown footnote for citation.
        
        Returns:
            Markdown footnote string
        """
        parts = [
            f"[^{self.citation_id}]: ",
            f"Page {self.page}, ",
            f"bbox [{self.bbox[0]:.1f}, {self.bbox[1]:.1f}, {self.bbox[2]:.1f}, {self.bbox[3]:.1f}], ",
            f"source: {self.source}"
        ]
        
        if self.confidence is not None:
            parts.append(f", confidence: {self.confidence:.2f}")
        
        if self.confidence_level:
            parts.append(f", level: {self.confidence_level}")
        
        if self.requires_human_review:
            parts.append(" [NEEDS REVIEW]")
        
        if self.file_reference:
            parts.append(f", file: {self.file_reference}")
        
        return "".join(parts)
    
    def overlaps(self, other: "Citation") -> bool:
        """
        Check if this citation's bbox overlaps with another citation.
        
        Args:
            other: Another citation
            
        Returns:
            True if bounding boxes overlap
        """
        if self.page != other.page:
            return False
        
        x0_1, y0_1, x1_1, y1_1 = self.bbox
        x0_2, y0_2, x1_2, y1_2 = other.bbox
        
        # Check for overlap
        return not (x1_1 <= x0_2 or x1_2 <= x0_1 or y1_1 <= y0_2 or y1_2 <= y0_1)
    
    def distance_to(self, other: "Citation") -> float:
        """
        Calculate Manhattan distance between citation centers.
        
        Args:
            other: Another citation
            
        Returns:
            Distance between centers
        """
        if self.page != other.page:
            return float('inf')
        
        # Calculate centers
        center1_x = (self.bbox[0] + self.bbox[2]) / 2
        center1_y = (self.bbox[1] + self.bbox[3]) / 2
        center2_x = (other.bbox[0] + other.bbox[2]) / 2
        center2_y = (other.bbox[1] + other.bbox[3]) / 2
        
        # Manhattan distance
        return abs(center1_x - center2_x) + abs(center1_y - center2_y)

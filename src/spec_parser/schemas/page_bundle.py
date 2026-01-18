"""
Page bundle and block models for structured document representation.

PageBundle contains all extracted content from a single page with complete provenance.
"""

from typing import List, Dict, Optional, Tuple, Union
from pydantic import BaseModel, Field

from spec_parser.schemas.citation import Citation


class Block(BaseModel):
    """Base class for all content blocks"""
    type: str = Field(..., description="Block type: text, picture, table, graphics")
    bbox: Tuple[float, float, float, float] = Field(..., description="Bounding box (x0, y0, x1, y1)")
    citation: str = Field(..., description="Citation ID linking to provenance")


class TextBlock(Block):
    """Text block with markdown slice reference"""
    type: str = Field(default="text", frozen=True)
    md_slice: Tuple[int, int] = Field(..., description="Markdown slice (start, end)")
    content: str = Field(..., description="Extracted text content")


class PictureBlock(Block):
    """Picture/image block with file reference"""
    type: str = Field(default="picture", frozen=True)
    image_ref: str = Field(..., description="Reference to extracted image file")
    source: str = Field(..., description="Source: 'pdf' or 'ocr'")


class TableBlock(Block):
    """Table block with structure preservation"""
    type: str = Field(default="table", frozen=True)
    table_ref: str = Field(..., description="Table identifier (e.g., 'table_1_1')")
    markdown_table: Optional[str] = Field(None, description="Markdown representation of table")


class GraphicsBlock(Block):
    """Graphics/vector block that may need OCR"""
    type: str = Field(default="graphics", frozen=True)
    source: str = Field(..., description="Source: 'vector' or 'cluster'")


class OCRResult(BaseModel):
    """OCR result with confidence tracking"""
    bbox: Tuple[float, float, float, float] = Field(..., description="Region bounding box")
    text: str = Field(..., description="Extracted text from OCR")
    confidence: float = Field(..., ge=0.0, le=1.0, description="OCR confidence score (0-1)")
    source: str = Field(..., description="OCR engine used (e.g., 'tesseract')")
    citation: str = Field(..., description="Citation ID for this OCR result")
    associated_block: Optional[str] = Field(None, description="Citation of associated image/graphics block")
    language: str = Field(default="eng", description="OCR language code")


class PageBundle(BaseModel):
    """
    Complete page bundle with all extracted content and provenance.
    
    This is the core data structure for RLM-style surgical extraction.
    Every element maintains complete citation chain.
    """
    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    markdown: str = Field(..., description="Base markdown extracted from page")
    blocks: List[Union[TextBlock, PictureBlock, TableBlock, GraphicsBlock]] = Field(
        default_factory=list,
        description="All content blocks with citations"
    )
    ocr: List[OCRResult] = Field(
        default_factory=list,
        description="OCR results for image/graphics regions"
    )
    citations: Dict[str, Citation] = Field(
        default_factory=dict,
        description="Citation index: citation_id -> Citation"
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional metadata (pdf_name, etc.)"
    )
    
    def add_block(self, block: Union[TextBlock, PictureBlock, TableBlock, GraphicsBlock], citation: Citation):
        """
        Add block with citation to page bundle.
        
        Args:
            block: Content block
            citation: Citation with provenance
        """
        self.blocks.append(block)
        self.citations[citation.citation_id] = citation
    
    def add_ocr(self, ocr_result: OCRResult):
        """
        Add OCR result with automatic citation.
        
        Args:
            ocr_result: OCR result with citation
        """
        self.ocr.append(ocr_result)
        
        # Create citation for OCR result
        citation = Citation(
            citation_id=ocr_result.citation,
            page=self.page,
            bbox=ocr_result.bbox,
            source="ocr",
            confidence=ocr_result.confidence,
            content_type="ocr"
        )
        self.citations[ocr_result.citation] = citation
    
    def get_blocks_by_type(self, block_type: str) -> List[Union[TextBlock, PictureBlock, TableBlock, GraphicsBlock]]:
        """
        Filter blocks by type.
        
        Args:
            block_type: Block type to filter ('text', 'picture', 'table', 'graphics')
            
        Returns:
            List of blocks matching the type
        """
        return [block for block in self.blocks if block.type == block_type]
    
    def get_citation(self, citation_id: str) -> Optional[Citation]:
        """
        Get citation by ID.
        
        Args:
            citation_id: Citation identifier
            
        Returns:
            Citation or None if not found
        """
        return self.citations.get(citation_id)
    
    def get_block_by_citation(self, citation_id: str) -> Optional[Union[TextBlock, PictureBlock, TableBlock, GraphicsBlock]]:
        """
        Get block by its citation ID.
        
        Args:
            citation_id: Citation identifier
            
        Returns:
            Block with matching citation or None
        """
        for block in self.blocks:
            if block.citation == citation_id:
                return block
        return None
    
    def get_text_in_bbox(self, bbox: Tuple[float, float, float, float], tolerance: float = 10.0) -> List[str]:
        """
        Get all text content within or near a bounding box.
        Used for RLM-style surgical extraction.
        
        Args:
            bbox: Target bounding box
            tolerance: Distance tolerance for "near" matching
            
        Returns:
            List of text strings from matching blocks
        """
        texts = []
        
        for block in self.get_blocks_by_type("text"):
            if isinstance(block, TextBlock):
                # Check if block bbox overlaps or is near target bbox
                citation = self.get_citation(block.citation)
                if citation and self._bbox_near(bbox, citation.bbox, tolerance):
                    texts.append(block.content)
        
        return texts
    
    def _bbox_near(self, bbox1: Tuple[float, float, float, float], 
                   bbox2: Tuple[float, float, float, float], 
                   tolerance: float) -> bool:
        """Check if two bboxes are within tolerance distance"""
        # Calculate center distance
        center1_x = (bbox1[0] + bbox1[2]) / 2
        center1_y = (bbox1[1] + bbox1[3]) / 2
        center2_x = (bbox2[0] + bbox2[2]) / 2
        center2_y = (bbox2[1] + bbox2[3]) / 2
        
        distance = ((center1_x - center2_x) ** 2 + (center1_y - center2_y) ** 2) ** 0.5
        return distance <= tolerance

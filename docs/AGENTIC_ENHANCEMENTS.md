# Agentic Document Extraction Enhancements

Based on LandingAI's Agentic Document Extraction (ADE) framework and DeepLearning.AI course.

## Current State (Already Agentic!)

Our POCT1-A parser already implements many agentic principles:

✅ **Visual + OCR Processing**: PyMuPDF extracts text/images with bboxes, OCR for non-selectable regions
✅ **Provenance Tracking**: Every block has `{page, bbox, source}` citations
✅ **Schema-Driven Extraction**: LLM extracts to structured JSON with defined schemas
✅ **Multi-Step Pipeline**: Extract → Index → Search → LLM Discovery → Field Extraction
✅ **Vendor-Agnostic**: Generic queries and prompts that discover messages from any spec

## Recommended Enhancements

### 1. Layout Detection & Reading Order

**Problem**: Multi-column specs, complex tables, merged cells may confuse reading order

**Solution**: Add layout detection before text extraction
```python
# New module: src/spec_parser/parsers/layout_detector.py
class LayoutDetector:
    """Detect document layout structure for proper reading order."""
    
    def detect_layout(self, page_image: np.ndarray) -> LayoutRegions:
        """
        Detect:
        - Multi-column layouts
        - Tables with merged cells
        - Sidebars, headers, footers
        - Reading order sequence
        
        Returns: LayoutRegions with proper ordering
        """
        pass
    
    def reorder_blocks(self, blocks: List[Block], layout: LayoutRegions) -> List[Block]:
        """Sort blocks into logical reading order."""
        pass
```

**Integration Point**: In `PyMuPDFExtractor.extract_page()` before processing blocks

### 2. Vision-Language Model Integration

**Problem**: Text-only OCR loses visual context (diagrams, table structures, spatial relationships)

**Solution**: Add VLM for visual understanding
```python
# New module: src/spec_parser/parsers/vlm_processor.py
class VLMProcessor:
    """Use vision-language models for visual document understanding."""
    
    def analyze_visual_context(
        self, 
        page_image: np.ndarray, 
        text_blocks: List[Block]
    ) -> VisualContext:
        """
        Analyze page visually to understand:
        - Table structures (headers, merged cells, relationships)
        - Diagram/chart content and captions
        - Spatial relationships between elements
        
        Returns: VisualContext with enhanced understanding
        """
        pass
    
    def enhance_extraction(
        self, 
        block: Block, 
        visual_context: VisualContext
    ) -> EnhancedBlock:
        """Enrich text block with visual understanding."""
        pass
```

**Models to Consider**:
- GPT-4 Vision (multimodal)
- LLaVA (open-source VLM)
- PaddleOCR + Layout models
- LandingAI's ADE API

### 3. Iterative Refinement Agent

**Problem**: Single-pass extraction may miss fields or get low confidence

**Solution**: Add validation + re-extraction loop
```python
# New module: src/spec_parser/llm/validation_agent.py
class ValidationAgent:
    """Validate and iteratively refine extractions."""
    
    def validate_extraction(
        self, 
        extracted_data: dict, 
        schema: Schema
    ) -> ValidationResult:
        """
        Check:
        - All required fields present
        - Data types match schema
        - Confidence scores > threshold
        - Cross-field consistency
        """
        pass
    
    def refine_extraction(
        self, 
        validation_result: ValidationResult,
        searcher: HybridSearcher
    ) -> dict:
        """
        Re-query for missing/low-confidence fields:
        1. Identify gaps
        2. Generate targeted search queries
        3. Re-extract with additional context
        4. Merge with original extraction
        """
        pass
```

**Integration Point**: After `MessageFieldExtractionNode.exec()`, before final output

### 4. Confidence Scoring

**Problem**: No way to know if extraction is reliable

**Solution**: Add confidence tracking throughout pipeline
```python
# Enhance extraction results with confidence
class ExtractionResult:
    """Extraction with confidence metadata."""
    
    data: dict
    confidence: float  # 0.0 - 1.0
    confidence_breakdown: Dict[str, float]  # Per-field confidence
    sources: List[Citation]  # Supporting evidence
    
    def needs_refinement(self, threshold: float = 0.8) -> bool:
        """Check if confidence is below threshold."""
        return self.confidence < threshold
```

**Sources of Confidence**:
- Search result relevance scores
- LLM response consistency
- Schema validation pass/fail
- Multiple citations agreement

### 5. Event-Driven Processing (Future)

**Problem**: Manual CLI execution, no automation

**Solution**: AWS Lambda + S3 event triggers
```python
# New module: src/spec_parser/cloud/aws_handler.py
def lambda_handler(event, context):
    """
    Triggered by S3 upload:
    1. Download PDF from S3
    2. Run full extraction pipeline
    3. Store results in DynamoDB + Vector DB
    4. Notify via SNS
    """
    pass
```

**Infrastructure**:
- S3 bucket for PDF uploads
- Lambda function with extraction code
- DynamoDB for metadata
- Vector DB (Pinecone/Weaviate) for RAG
- SNS for notifications

### 6. RAG Integration Enhancement

**Problem**: Currently just indexes text blocks

**Solution**: Store with visual grounding for RAG
```python
# Enhanced RAG storage
class VisuallyGroundedChunk:
    """RAG chunk with visual context."""
    
    text: str
    embedding: np.ndarray
    page: int
    bbox: Tuple[float, float, float, float]
    cropped_image: bytes  # Actual page region image
    visual_context: dict  # Layout, nearby elements
    
    def retrieve_with_visual(self, query: str) -> tuple[str, bytes]:
        """Return both text and cropped page image."""
        return self.text, self.cropped_image
```

**Use Case**: RAG returns text + visual page snippet for user validation

## Implementation Priority

### Phase 1 (Immediate - High Impact)
1. **Layout Detection**: Fix reading order issues in multi-column specs
2. **Confidence Scoring**: Track extraction reliability
3. **Validation Agent**: Iterative refinement for better accuracy

### Phase 2 (Near-term - Enhanced Quality)
4. **VLM Integration**: Better visual understanding
5. **Visual RAG**: Store + retrieve with page images

### Phase 3 (Future - Production Scale)
6. **Event-Driven**: AWS Lambda automation
7. **Monitoring**: Track extraction metrics over time

## Key Principles from ADE

1. **Visual-First**: Treat documents as images, not just text
2. **Iterative**: Multiple passes with validation and refinement
3. **Grounded**: Always link extractions back to source location
4. **Schema-Driven**: Define expected output structure upfront
5. **Confidence-Aware**: Track and act on confidence scores

## Resources

- [DeepLearning.AI Course](https://www.deeplearning.ai/short-courses/document-ai-from-ocr-to-agentic-doc-extraction/)
- [LandingAI Platform](https://landing.ai/)
- PaddleOCR for layout detection
- LLaVA for open-source VLM
- AWS Lambda for serverless processing

---

**Note**: Our current system is already quite agentic! These enhancements would make it even more robust and production-ready.

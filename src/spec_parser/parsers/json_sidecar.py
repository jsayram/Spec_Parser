"""
JSON sidecar writer for machine-readable output with complete provenance.

Writes structured JSON with all extracted data and metadata.
Includes extraction metadata for compliance and audit trails.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from spec_parser.schemas.page_bundle import PageBundle
from spec_parser.schemas.audit import ExtractionMetadata, ProcessingStats
from spec_parser.utils.file_handler import write_json
from spec_parser.utils.hashing import compute_file_hash, compute_extraction_hash
from spec_parser.exceptions import FileHandlerError


class JSONSidecarWriter:
    """
    Write JSON sidecar files with complete provenance.

    Format:
    {
        "pdf_name": "POCT1A2",
        "total_pages": 42,
        "pages": [
            {
                "page": 1,
                "markdown": "...",
                "blocks": [...],
                "ocr": [...],
                "citations": {...},
                "metadata": {...}
            }
        ]
    }
    """

    def __init__(self):
        """Initialize JSON sidecar writer"""
        pass

    def write_page_bundle(
        self, page_bundle: PageBundle, output_path: Path
    ) -> None:
        """
        Write single page bundle to JSON.

        Args:
            page_bundle: PageBundle to write
            output_path: Output JSON file path
        """
        try:
            data = self._serialize_page_bundle(page_bundle)
            write_json(data, output_path)
            logger.info(f"Wrote page bundle to {output_path}")
        except Exception as e:
            raise FileHandlerError(f"Failed to write page bundle: {e}")

    def write_document(
        self, page_bundles: List[PageBundle], output_path: Path, pdf_name: str,
        pdf_path: Optional[Path] = None,
        extraction_metadata: Optional[ExtractionMetadata] = None,
    ) -> None:
        """
        Write complete document with all pages to JSON.

        Args:
            page_bundles: List of PageBundle objects
            output_path: Output JSON file path
            pdf_name: Name of source PDF
            pdf_path: Optional path to source PDF for hash computation
            extraction_metadata: Optional extraction metadata for compliance
        """
        try:
            # Build extraction metadata if not provided
            metadata_dict = None
            if extraction_metadata:
                metadata_dict = {
                    "extraction_id": extraction_metadata.extraction_id,
                    "extraction_timestamp": extraction_metadata.extraction_timestamp.isoformat(),
                    "extraction_version": extraction_metadata.extraction_version,
                    "source_pdf_hash": extraction_metadata.source_pdf_hash,
                    "source_pdf_size_bytes": extraction_metadata.source_pdf_size_bytes,
                    "stats": {
                        "total_pages": extraction_metadata.stats.total_pages,
                        "processed_pages": extraction_metadata.stats.processed_pages,
                        "total_blocks": extraction_metadata.stats.total_blocks,
                        "text_blocks": extraction_metadata.stats.text_blocks,
                        "image_blocks": extraction_metadata.stats.image_blocks,
                        "ocr_stats": {
                            "total_regions": extraction_metadata.stats.ocr_stats.total_regions,
                            "accepted_count": extraction_metadata.stats.ocr_stats.accepted_count,
                            "review_count": extraction_metadata.stats.ocr_stats.review_count,
                            "rejected_count": extraction_metadata.stats.ocr_stats.rejected_count,
                            "average_confidence": extraction_metadata.stats.ocr_stats.average_confidence,
                        },
                        "processing_time_seconds": extraction_metadata.stats.processing_time_seconds,
                        "error_count": len(extraction_metadata.stats.errors),
                    },
                    "requires_human_review": extraction_metadata.requires_human_review,
                    "review_reason": extraction_metadata.review_reason,
                }
            elif pdf_path and pdf_path.exists():
                # Compute basic metadata from PDF
                pdf_hash = compute_file_hash(pdf_path)
                pdf_size = pdf_path.stat().st_size
                metadata_dict = {
                    "extraction_timestamp": datetime.now().isoformat(),
                    "source_pdf_hash": pdf_hash,
                    "source_pdf_size_bytes": pdf_size,
                }
            
            data = {
                "pdf_name": pdf_name,
                "total_pages": len(page_bundles),
                "extraction_metadata": metadata_dict,
                "pages": [
                    self._serialize_page_bundle(bundle) for bundle in page_bundles
                ],
            }
            write_json(data, output_path)
            logger.info(
                f"Wrote document with {len(page_bundles)} pages to {output_path}"
            )
        except Exception as e:
            raise FileHandlerError(f"Failed to write document: {e}")

    def _serialize_page_bundle(self, page_bundle: PageBundle) -> Dict[str, Any]:
        """
        Serialize PageBundle to JSON-compatible dict.

        Args:
            page_bundle: PageBundle to serialize

        Returns:
            Dictionary representation
        """
        return {
            "page": page_bundle.page,
            "markdown": page_bundle.markdown,
            "blocks": [self._serialize_block(block) for block in page_bundle.blocks],
            "ocr": [self._serialize_ocr(ocr) for ocr in page_bundle.ocr],
            "citations": {
                cid: self._serialize_citation(citation)
                for cid, citation in page_bundle.citations.items()
            },
            "metadata": page_bundle.metadata,
        }

    def _serialize_block(self, block) -> Dict[str, Any]:
        """Serialize Block to dict"""
        data = {
            "type": block.type,
            "bbox": block.bbox,
            "citation": block.citation,
        }

        # Add type-specific fields
        if hasattr(block, "content"):
            data["content"] = block.content
        if hasattr(block, "md_slice"):
            data["md_slice"] = block.md_slice
        if hasattr(block, "image_ref"):
            data["image_ref"] = block.image_ref
            data["source"] = block.source
        if hasattr(block, "table_ref"):
            data["table_ref"] = block.table_ref
            data["markdown_table"] = block.markdown_table
        if hasattr(block, "source") and not hasattr(block, "image_ref"):
            data["source"] = block.source

        return data

    def _serialize_ocr(self, ocr) -> Dict[str, Any]:
        """Serialize OCRResult to dict"""
        return {
            "bbox": ocr.bbox,
            "text": ocr.text,
            "confidence": ocr.confidence,
            "source": ocr.source,
            "citation": ocr.citation,
            "associated_block": ocr.associated_block,
            "language": ocr.language,
        }

    def _serialize_citation(self, citation) -> Dict[str, Any]:
        """Serialize Citation to dict"""
        data = {
            "citation_id": citation.citation_id,
            "page": citation.page,
            "bbox": citation.bbox,
            "source": citation.source,
            "content_type": citation.content_type,
        }

        if citation.confidence is not None:
            data["confidence"] = citation.confidence
        if citation.file_reference:
            data["file_reference"] = citation.file_reference

        return data

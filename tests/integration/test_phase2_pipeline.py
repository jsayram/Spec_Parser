"""
Integration test for Phase 2 PDF parsing pipeline.

Tests complete flow: PDF → PageBundles → OCR → Markdown → JSON
"""

from pathlib import Path
import pytest

from spec_parser.parsers import (
    PyMuPDFExtractor,
    OCRProcessor,
    MarkdownMerger,
    JSONSidecarWriter,
)
from spec_parser.config import settings


class TestPhase2Integration:
    """Integration tests for Phase 2 parsing pipeline"""

    @pytest.fixture
    def test_pdf(self):
        """Find a test PDF in data/specs/"""
        specs_dir = settings.specs_dir
        pdfs = list(specs_dir.glob("*.pdf"))
        
        if not pdfs:
            pytest.skip("No PDF files found in data/specs/")
        
        return pdfs[0]

    def test_full_pipeline(self, test_pdf):
        """Test complete Phase 2 pipeline with real PDF"""
        # Create output session
        output_dir = settings.create_output_session(test_pdf)
        
        print(f"\n✓ Created output session: {output_dir.name}")
        assert output_dir.exists()
        assert settings.image_dir.exists()
        assert settings.markdown_dir.exists()
        assert settings.json_dir.exists()
        
        # Extract PDF
        with PyMuPDFExtractor(test_pdf) as extractor:
            # Extract first 3 pages only for testing
            bundles = []
            max_pages = min(3, len(extractor.doc))
            
            for page_num in range(1, max_pages + 1):
                bundle = extractor.extract_page(page_num)
                bundles.append(bundle)
                
                print(f"✓ Extracted page {page_num}: {len(bundle.blocks)} blocks")
                assert bundle.page == page_num
                assert len(bundle.blocks) > 0
        
        # Run OCR on first page
        if bundles:
            ocr_processor = OCRProcessor(dpi=150)  # Lower DPI for faster testing
            
            with PyMuPDFExtractor(test_pdf) as extractor:
                pdf_page = extractor.doc[0]
                ocr_results = ocr_processor.process_page(bundles[0], pdf_page)
                
                # Add OCR results to bundle
                for ocr in ocr_results:
                    citation_id = f"p{bundles[0].page}_ocr{len(bundles[0].ocr)+1}"
                    ocr.citation = citation_id
                    bundles[0].add_ocr(ocr)
                
                print(f"✓ OCR processed: {len(ocr_results)} results")
        
        # Merge markdown
        merger = MarkdownMerger()
        for bundle in bundles:
            enhanced_md = merger.merge(bundle)
            
            # Write markdown
            md_path = settings.markdown_dir / f"page_{bundle.page}.md"
            md_path.write_text(enhanced_md)
            
            print(f"✓ Wrote markdown: {md_path.name}")
            assert md_path.exists()
            assert len(enhanced_md) > 0
        
        # Write JSON sidecar
        json_writer = JSONSidecarWriter()
        json_path = settings.json_dir / f"{test_pdf.stem}.json"
        json_writer.write_document(bundles, json_path, test_pdf.stem)
        
        print(f"✓ Wrote JSON sidecar: {json_path.name}")
        assert json_path.exists()
        
        print(f"\n✅ Phase 2 pipeline complete!")
        print(f"   Output: {output_dir}")
        print(f"   Pages processed: {len(bundles)}")
        print(f"   Total blocks: {sum(len(b.blocks) for b in bundles)}")
        print(f"   Total OCR results: {sum(len(b.ocr) for b in bundles)}")

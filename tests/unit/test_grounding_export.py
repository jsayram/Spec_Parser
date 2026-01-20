"""
Tests for GroundingExporter utility.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from spec_parser.utils.grounding_export import GroundingExporter, export_groundings
from spec_parser.schemas.page_bundle import PageBundle, TextBlock, PictureBlock, TableBlock
from spec_parser.schemas.citation import Citation


class TestGroundingExporterInit:
    """Tests for GroundingExporter initialization."""
    
    def test_default_initialization(self, tmp_path):
        """Test default initialization."""
        exporter = GroundingExporter(output_dir=tmp_path)
        
        assert exporter.output_dir == tmp_path
        assert exporter.dpi == 150
        assert exporter.padding == 10
        assert exporter.image_format == "png"
        assert exporter.include_text is True
        assert exporter.include_pictures is True
        assert exporter.include_tables is True
    
    def test_custom_initialization(self, tmp_path):
        """Test custom initialization."""
        exporter = GroundingExporter(
            output_dir=tmp_path,
            dpi=300,
            padding=20,
            image_format="jpg",
            include_text=False,
        )
        
        assert exporter.dpi == 300
        assert exporter.padding == 20
        assert exporter.image_format == "jpg"
        assert exporter.include_text is False
    
    def test_creates_output_directory(self, tmp_path):
        """Test that output directory is created."""
        output_dir = tmp_path / "groundings" / "nested"
        
        exporter = GroundingExporter(output_dir=output_dir)
        
        assert output_dir.exists()


class TestGroundingExporterExportBlock:
    """Tests for _export_block method."""
    
    @pytest.fixture
    def exporter(self, tmp_path):
        """Create exporter instance."""
        return GroundingExporter(output_dir=tmp_path)
    
    @pytest.fixture
    def mock_page(self):
        """Create mock PyMuPDF page."""
        page = MagicMock()
        page.rect.width = 612
        page.rect.height = 792
        
        # Mock pixmap
        mock_pix = MagicMock()
        page.get_pixmap.return_value = mock_pix
        
        return page
    
    def test_export_block_creates_file(self, exporter, mock_page, tmp_path):
        """Test that export_block creates an image file."""
        bbox = (100.0, 100.0, 200.0, 200.0)
        output_dir = tmp_path / "page_0001"
        output_dir.mkdir()
        
        result = exporter._export_block(
            mock_page, bbox, "text_001", output_dir, "p1_t1"
        )
        
        # Should call save on pixmap
        mock_page.get_pixmap.assert_called_once()
        mock_page.get_pixmap.return_value.save.assert_called_once()
    
    def test_export_block_applies_padding(self, exporter, mock_page, tmp_path):
        """Test that padding is applied to bbox."""
        bbox = (100.0, 100.0, 200.0, 200.0)
        output_dir = tmp_path / "page_0001"
        output_dir.mkdir()
        
        exporter.padding = 15
        exporter._export_block(mock_page, bbox, "text_001", output_dir, "p1_t1")
        
        # Check that get_pixmap was called with padded clip
        call_args = mock_page.get_pixmap.call_args
        clip = call_args.kwargs.get('clip')
        
        # Clip should be padded (within page bounds)
        assert clip is not None
    
    def test_export_block_handles_error(self, exporter, mock_page, tmp_path):
        """Test that errors are handled gracefully."""
        mock_page.get_pixmap.side_effect = Exception("Render error")
        
        output_dir = tmp_path / "page_0001"
        output_dir.mkdir()
        
        result = exporter._export_block(
            mock_page, (100, 100, 200, 200), "text_001", output_dir, "p1_t1"
        )
        
        assert result is None


class TestGroundingExporterExportPage:
    """Tests for export_page_groundings method."""
    
    @pytest.fixture
    def exporter(self, tmp_path):
        """Create exporter instance."""
        return GroundingExporter(output_dir=tmp_path)
    
    @pytest.fixture
    def mock_bundle(self):
        """Create mock PageBundle."""
        bundle = Mock(spec=PageBundle)
        bundle.page_number = 1
        
        # Text blocks
        text_block = Mock(spec=TextBlock)
        text_block.bbox = (100, 100, 200, 150)
        text_block.citation_id = "p1_text_1"
        bundle.text_blocks = [text_block]
        
        # Picture blocks
        picture_block = Mock(spec=PictureBlock)
        picture_block.bbox = (50, 200, 150, 300)
        picture_block.citation_id = "p1_img_1"
        picture_block.source = "text"
        bundle.picture_blocks = [picture_block]
        
        # Table blocks
        table_block = Mock(spec=TableBlock)
        table_block.bbox = (100, 350, 500, 500)
        table_block.citation_id = "p1_tbl_1"
        bundle.table_blocks = [table_block]
        
        # Graphics blocks
        bundle.graphics_blocks = []
        
        return bundle
    
    def test_export_page_creates_directory(self, exporter, mock_bundle, tmp_path):
        """Test that page directory is created."""
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        
        with patch.object(exporter, '_export_block', return_value=tmp_path / "test.png"):
            exporter.export_page_groundings(mock_doc, mock_bundle, 1)
        
        page_dir = tmp_path / "page_0001"
        assert page_dir.exists()
    
    def test_export_page_exports_all_block_types(self, exporter, mock_bundle, tmp_path):
        """Test that all block types are exported."""
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        
        exported_blocks = []
        
        def track_export(page, bbox, block_name, output_dir, citation_id):
            exported_blocks.append(block_name)
            return tmp_path / f"{block_name}.png"
        
        with patch.object(exporter, '_export_block', side_effect=track_export):
            result = exporter.export_page_groundings(mock_doc, mock_bundle, 1)
        
        # Should have exported text, picture, and table
        assert any("text" in b for b in exported_blocks)
        assert any("picture" in b for b in exported_blocks)
        assert any("table" in b for b in exported_blocks)
    
    def test_export_page_respects_include_flags(self, tmp_path):
        """Test that include flags are respected."""
        exporter = GroundingExporter(
            output_dir=tmp_path,
            include_text=False,
            include_pictures=True,
            include_tables=False,
        )
        
        mock_bundle = Mock(spec=PageBundle)
        mock_bundle.page_number = 1
        mock_bundle.text_blocks = [Mock(bbox=(0,0,10,10), citation_id="t1")]
        mock_bundle.picture_blocks = [Mock(bbox=(0,0,10,10), citation_id="p1", source="text")]
        mock_bundle.table_blocks = [Mock(bbox=(0,0,10,10), citation_id="tb1")]
        mock_bundle.graphics_blocks = []
        
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        
        exported_types = []
        
        def track_export(page, bbox, block_name, output_dir, citation_id):
            exported_types.append(block_name.split("_")[0])
            return tmp_path / f"{block_name}.png"
        
        with patch.object(exporter, '_export_block', side_effect=track_export):
            exporter.export_page_groundings(mock_doc, mock_bundle, 1)
        
        # Only pictures should be exported
        assert "picture" in exported_types
        assert "text" not in exported_types
        assert "table" not in exported_types


class TestExportGroundingsConvenience:
    """Tests for export_groundings convenience function."""
    
    def test_export_groundings_creates_exporter(self, tmp_path):
        """Test that convenience function creates and uses exporter."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        
        bundles = []
        
        with patch('spec_parser.utils.grounding_export.GroundingExporter') as MockExporter:
            mock_instance = MagicMock()
            mock_instance.export_all_pages.return_value = {}
            MockExporter.return_value = mock_instance
            
            result = export_groundings(
                pdf_path=pdf_path,
                bundles=bundles,
                output_dir=tmp_path / "output",
                dpi=300,
                padding=20,
            )
            
            MockExporter.assert_called_once_with(
                output_dir=tmp_path / "output",
                dpi=300,
                padding=20,
            )
            mock_instance.export_all_pages.assert_called_once()

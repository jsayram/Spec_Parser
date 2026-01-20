"""
Tests for VisualizationRenderer utility.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from spec_parser.utils.visualization import (
    VisualizationRenderer,
    visualize_extraction,
    create_comparison_view,
    DEFAULT_COLORS,
)
from spec_parser.schemas.page_bundle import PageBundle, TextBlock, PictureBlock, TableBlock, GraphicsBlock


class TestDefaultColors:
    """Tests for default color configuration."""
    
    def test_all_block_types_have_colors(self):
        """Test that all block types have defined colors."""
        required_types = ["text", "picture", "table", "graphics", "ocr"]
        
        for block_type in required_types:
            assert block_type in DEFAULT_COLORS
    
    def test_colors_are_valid_rgb(self):
        """Test that colors are valid RGB tuples."""
        for name, color in DEFAULT_COLORS.items():
            assert isinstance(color, tuple), f"{name} color is not a tuple"
            assert len(color) == 3, f"{name} color does not have 3 components"
            assert all(0 <= v <= 1 for v in color), f"{name} color values out of range"


class TestVisualizationRendererInit:
    """Tests for VisualizationRenderer initialization."""
    
    def test_default_initialization(self, tmp_path):
        """Test default initialization."""
        renderer = VisualizationRenderer(output_dir=tmp_path)
        
        assert renderer.output_dir == tmp_path
        assert renderer.colors == DEFAULT_COLORS
        assert renderer.line_width == 2.0
        assert renderer.show_labels is True
        assert renderer.label_font_size == 8.0
        assert renderer.dpi == 150
        assert renderer.opacity == 0.3
    
    def test_custom_initialization(self, tmp_path):
        """Test custom initialization."""
        custom_colors = {"text": (1, 0, 0)}
        
        renderer = VisualizationRenderer(
            output_dir=tmp_path,
            colors=custom_colors,
            line_width=3.0,
            show_labels=False,
            dpi=300,
            opacity=0.5,
        )
        
        assert renderer.colors == custom_colors
        assert renderer.line_width == 3.0
        assert renderer.show_labels is False
        assert renderer.dpi == 300
        assert renderer.opacity == 0.5
    
    def test_creates_output_directory(self, tmp_path):
        """Test that output directory is created."""
        output_dir = tmp_path / "viz" / "nested"
        
        renderer = VisualizationRenderer(output_dir=output_dir)
        
        assert output_dir.exists()


class TestVisualizationRendererRenderPage:
    """Tests for render_page method."""
    
    @pytest.fixture
    def renderer(self, tmp_path):
        """Create renderer instance."""
        return VisualizationRenderer(output_dir=tmp_path)
    
    @pytest.fixture
    def mock_bundle(self):
        """Create mock PageBundle with various block types."""
        bundle = Mock(spec=PageBundle)
        bundle.page_number = 5
        
        # Text blocks
        text_block = Mock(spec=TextBlock)
        text_block.bbox = (100, 100, 300, 150)
        text_block.citation_id = "p5_text_1"
        bundle.text_blocks = [text_block]
        
        # Picture blocks
        picture_block = Mock(spec=PictureBlock)
        picture_block.bbox = (50, 200, 250, 400)
        picture_block.citation_id = "p5_img_1"
        picture_block.source = "text"
        bundle.picture_blocks = [picture_block]
        
        # Table blocks
        table_block = Mock(spec=TableBlock)
        table_block.bbox = (100, 450, 500, 600)
        table_block.citation_id = "p5_tbl_1"
        bundle.table_blocks = [table_block]
        
        # Graphics blocks
        graphics_block = Mock(spec=GraphicsBlock)
        graphics_block.bbox = (300, 100, 400, 180)
        graphics_block.citation_id = "p5_gfx_1"
        bundle.graphics_blocks = [graphics_block]
        
        return bundle
    
    @pytest.fixture
    def mock_doc(self):
        """Create mock PyMuPDF document."""
        doc = MagicMock()
        
        mock_page = MagicMock()
        mock_shape = MagicMock()
        mock_page.new_shape.return_value = mock_shape
        mock_page.get_pixmap.return_value = MagicMock()
        
        doc.__getitem__ = Mock(return_value=mock_page)
        
        return doc
    
    def test_render_page_creates_shape(self, renderer, mock_bundle, mock_doc):
        """Test that render_page creates shape for drawing."""
        renderer.render_page(mock_doc, mock_bundle, 5)
        
        mock_page = mock_doc[4]  # 0-indexed
        mock_page.new_shape.assert_called_once()
    
    def test_render_page_commits_shape(self, renderer, mock_bundle, mock_doc):
        """Test that shape is committed after drawing."""
        renderer.render_page(mock_doc, mock_bundle, 5)
        
        mock_page = mock_doc[4]
        mock_shape = mock_page.new_shape.return_value
        mock_shape.commit.assert_called_once()
    
    def test_render_page_saves_pixmap(self, renderer, mock_bundle, mock_doc, tmp_path):
        """Test that rendered page is saved."""
        result = renderer.render_page(mock_doc, mock_bundle, 5)
        
        mock_page = mock_doc[4]
        mock_page.get_pixmap.assert_called_once()
        mock_page.get_pixmap.return_value.save.assert_called_once()
    
    def test_render_page_returns_path(self, renderer, mock_bundle, mock_doc, tmp_path):
        """Test that render_page returns output path."""
        result = renderer.render_page(mock_doc, mock_bundle, 5)
        
        assert result is not None
        assert "page_0005_annotated.png" in str(result)
    
    def test_render_page_handles_error(self, renderer, mock_bundle, mock_doc):
        """Test error handling in render_page."""
        mock_doc.__getitem__.side_effect = Exception("Page error")
        
        result = renderer.render_page(mock_doc, mock_bundle, 5)
        
        assert result is None


class TestVisualizationRendererDrawBbox:
    """Tests for _draw_bbox method."""
    
    @pytest.fixture
    def renderer(self, tmp_path):
        """Create renderer instance."""
        return VisualizationRenderer(output_dir=tmp_path)
    
    def test_draw_bbox_uses_correct_color(self, renderer):
        """Test that correct color is used for block type."""
        mock_shape = MagicMock()
        
        renderer._draw_bbox(mock_shape, (100, 100, 200, 200), "text", label=None)
        
        # Check that finish was called with text color
        call_args = mock_shape.finish.call_args
        assert call_args.kwargs['color'] == DEFAULT_COLORS["text"]
    
    def test_draw_bbox_fallback_color(self, renderer):
        """Test fallback color for unknown block type."""
        mock_shape = MagicMock()
        
        renderer._draw_bbox(mock_shape, (100, 100, 200, 200), "unknown_type", label=None)
        
        # Should use gray fallback
        call_args = mock_shape.finish.call_args
        assert call_args.kwargs['color'] == (0.5, 0.5, 0.5)
    
    def test_draw_bbox_with_label(self, renderer):
        """Test that label is drawn when provided."""
        mock_shape = MagicMock()
        renderer.show_labels = True
        
        renderer._draw_bbox(mock_shape, (100, 100, 200, 200), "text", label="test_label")
        
        mock_shape.insert_text.assert_called_once()
    
    def test_draw_bbox_without_label_when_disabled(self, renderer):
        """Test that label is not drawn when show_labels=False."""
        mock_shape = MagicMock()
        renderer.show_labels = False
        
        renderer._draw_bbox(mock_shape, (100, 100, 200, 200), "text", label="test_label")
        
        mock_shape.insert_text.assert_not_called()


class TestVisualizationRendererRenderAllPages:
    """Tests for render_all_pages method."""
    
    @pytest.fixture
    def renderer(self, tmp_path):
        """Create renderer instance."""
        return VisualizationRenderer(output_dir=tmp_path)
    
    def test_render_all_pages_opens_pdf(self, renderer, tmp_path):
        """Test that PDF is opened."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        
        with patch('pymupdf.open') as mock_open:
            mock_doc = MagicMock()
            mock_open.return_value.__enter__ = Mock(return_value=mock_doc)
            mock_open.return_value.__exit__ = Mock(return_value=False)
            
            with patch.object(renderer, 'render_page', return_value=tmp_path / "page.png"):
                renderer.render_all_pages(pdf_path, [])
            
            mock_open.assert_called_once_with(pdf_path)
    
    def test_render_all_pages_renders_each_bundle(self, renderer, tmp_path):
        """Test that each bundle is rendered."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        
        bundles = []
        for i in range(3):
            b = Mock(spec=PageBundle)
            b.page_number = i + 1
            bundles.append(b)
        
        with patch('pymupdf.open') as mock_open:
            mock_doc = MagicMock()
            mock_open.return_value.__enter__ = Mock(return_value=mock_doc)
            mock_open.return_value.__exit__ = Mock(return_value=False)
            
            with patch.object(renderer, 'render_page', return_value=tmp_path / "page.png") as mock_render:
                result = renderer.render_all_pages(pdf_path, bundles)
            
            assert mock_render.call_count == 3
            assert len(result) == 3


class TestVisualizeExtractionConvenience:
    """Tests for visualize_extraction convenience function."""
    
    def test_visualize_extraction_creates_renderer(self, tmp_path):
        """Test that convenience function creates renderer."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        
        with patch('spec_parser.utils.visualization.VisualizationRenderer') as MockRenderer:
            mock_instance = MagicMock()
            mock_instance.render_all_pages.return_value = []
            MockRenderer.return_value = mock_instance
            
            visualize_extraction(
                pdf_path=pdf_path,
                bundles=[],
                output_dir=tmp_path / "output",
                dpi=200,
                show_labels=False,
            )
            
            MockRenderer.assert_called_once_with(
                output_dir=tmp_path / "output",
                dpi=200,
                show_labels=False,
            )


class TestCreateComparisonView:
    """Tests for create_comparison_view function."""
    
    def test_comparison_creates_before_after_dirs(self, tmp_path):
        """Test that before/after directories are created."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        
        bundle_before = Mock(spec=PageBundle)
        bundle_before.page_number = 1
        bundle_after = Mock(spec=PageBundle)
        bundle_after.page_number = 1
        
        with patch('pymupdf.open') as mock_open:
            mock_doc = MagicMock()
            mock_open.return_value.__enter__ = Mock(return_value=mock_doc)
            mock_open.return_value.__exit__ = Mock(return_value=False)
            
            with patch('spec_parser.utils.visualization.VisualizationRenderer') as MockRenderer:
                mock_instance = MagicMock()
                mock_instance.render_page.return_value = tmp_path / "page.png"
                MockRenderer.return_value = mock_instance
                
                before_path, after_path = create_comparison_view(
                    pdf_path=pdf_path,
                    bundles_before=[bundle_before],
                    bundles_after=[bundle_after],
                    output_dir=tmp_path / "compare",
                    page_num=1,
                )
    
    def test_comparison_handles_missing_bundle(self, tmp_path):
        """Test handling when bundle for page doesn't exist."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()
        
        bundle = Mock(spec=PageBundle)
        bundle.page_number = 1
        
        with patch('pymupdf.open') as mock_open:
            mock_doc = MagicMock()
            mock_open.return_value.__enter__ = Mock(return_value=mock_doc)
            mock_open.return_value.__exit__ = Mock(return_value=False)
            
            with patch('spec_parser.utils.visualization.VisualizationRenderer') as MockRenderer:
                mock_instance = MagicMock()
                mock_instance.render_page.return_value = tmp_path / "page.png"
                MockRenderer.return_value = mock_instance
                
                # Request page 5 which doesn't exist in bundles
                before_path, after_path = create_comparison_view(
                    pdf_path=pdf_path,
                    bundles_before=[bundle],
                    bundles_after=[],
                    output_dir=tmp_path / "compare",
                    page_num=5,
                )
                
                # Should return None for missing bundles
                assert before_path is None
                assert after_path is None

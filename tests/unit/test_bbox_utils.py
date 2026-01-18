"""
Unit tests for bbox utilities.
"""

import pytest

from spec_parser.utils.bbox_utils import (
    bbox_overlap,
    bbox_distance,
    bbox_iou,
    bbox_merge,
    validate_bbox,
    bbox_contains_point,
    bbox_contains,
    bbox_area,
)


class TestBBoxUtils:
    """Test bounding box utilities"""
    
    def test_bbox_overlap_overlapping(self, sample_bbox, overlapping_bbox):
        """Test overlap detection for overlapping boxes"""
        assert bbox_overlap(sample_bbox, overlapping_bbox) is True
    
    def test_bbox_overlap_non_overlapping(self, sample_bbox, non_overlapping_bbox):
        """Test overlap detection for non-overlapping boxes"""
        assert bbox_overlap(sample_bbox, non_overlapping_bbox) is False
    
    def test_bbox_overlap_identical(self, sample_bbox):
        """Test overlap for identical boxes"""
        assert bbox_overlap(sample_bbox, sample_bbox) is True
    
    def test_bbox_distance(self):
        """Test distance calculation between boxes"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (200, 200, 300, 300)
        
        distance = bbox_distance(bbox1, bbox2)
        assert distance > 0
        
        # Distance should be symmetric
        assert bbox_distance(bbox1, bbox2) == bbox_distance(bbox2, bbox1)
    
    def test_bbox_distance_zero_for_same(self, sample_bbox):
        """Test distance is zero for same box"""
        distance = bbox_distance(sample_bbox, sample_bbox)
        assert distance == 0
    
    def test_bbox_iou_identical(self, sample_bbox):
        """Test IoU for identical boxes"""
        iou = bbox_iou(sample_bbox, sample_bbox)
        assert iou == 1.0
    
    def test_bbox_iou_non_overlapping(self, sample_bbox, non_overlapping_bbox):
        """Test IoU for non-overlapping boxes"""
        iou = bbox_iou(sample_bbox, non_overlapping_bbox)
        assert iou == 0.0
    
    def test_bbox_iou_partial_overlap(self, sample_bbox, overlapping_bbox):
        """Test IoU for partially overlapping boxes"""
        iou = bbox_iou(sample_bbox, overlapping_bbox)
        assert 0.0 < iou < 1.0
    
    def test_bbox_merge_single(self, sample_bbox):
        """Test merging single bbox"""
        merged = bbox_merge([sample_bbox])
        assert merged == sample_bbox
    
    def test_bbox_merge_multiple(self):
        """Test merging multiple bboxes"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (50, 50, 150, 150)
        bbox3 = (100, 100, 200, 200)
        
        merged = bbox_merge([bbox1, bbox2, bbox3])
        assert merged == (0, 0, 200, 200)
    
    def test_bbox_merge_empty(self):
        """Test merging empty list"""
        merged = bbox_merge([])
        assert merged == (0, 0, 0, 0)
    
    def test_validate_bbox_valid(self, sample_bbox):
        """Test validation with valid bbox"""
        assert validate_bbox(sample_bbox) is True
    
    def test_validate_bbox_invalid_x(self):
        """Test validation with invalid x coordinates"""
        bbox = (100, 0, 50, 100)  # x1 < x0
        assert validate_bbox(bbox) is False
    
    def test_validate_bbox_invalid_y(self):
        """Test validation with invalid y coordinates"""
        bbox = (0, 100, 100, 50)  # y1 < y0
        assert validate_bbox(bbox) is False
    
    def test_bbox_contains_point_inside(self):
        """Test point inside bbox"""
        bbox = (0, 0, 100, 100)
        point = (50, 50)
        assert bbox_contains_point(bbox, point) is True
    
    def test_bbox_contains_point_outside(self):
        """Test point outside bbox"""
        bbox = (0, 0, 100, 100)
        point = (150, 150)
        assert bbox_contains_point(bbox, point) is False
    
    def test_bbox_contains_point_on_edge(self):
        """Test point on bbox edge"""
        bbox = (0, 0, 100, 100)
        point = (100, 100)
        assert bbox_contains_point(bbox, point) is True
    
    def test_bbox_contains_inner(self):
        """Test bbox fully contains another"""
        outer = (0, 0, 200, 200)
        inner = (50, 50, 150, 150)
        assert bbox_contains(outer, inner) is True
    
    def test_bbox_contains_not_contained(self):
        """Test bbox does not contain another"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (50, 50, 150, 150)
        assert bbox_contains(bbox1, bbox2) is False
    
    def test_bbox_area(self):
        """Test area calculation"""
        bbox = (0, 0, 100, 100)
        assert bbox_area(bbox) == 10000
    
    def test_bbox_area_non_square(self):
        """Test area for non-square bbox"""
        bbox = (0, 0, 100, 50)
        assert bbox_area(bbox) == 5000

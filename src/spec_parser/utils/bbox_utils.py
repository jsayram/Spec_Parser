"""
Bounding box utilities for spatial operations.

All bbox operations use (x0, y0, x1, y1) format.
"""

from typing import List, Tuple


def bbox_overlap(bbox1: Tuple[float, float, float, float], 
                 bbox2: Tuple[float, float, float, float]) -> bool:
    """
    Check if two bounding boxes overlap.
    
    Args:
        bbox1: First bbox (x0, y0, x1, y1)
        bbox2: Second bbox (x0, y0, x1, y1)
        
    Returns:
        True if boxes overlap
    """
    x0_1, y0_1, x1_1, y1_1 = bbox1
    x0_2, y0_2, x1_2, y1_2 = bbox2
    
    return not (x1_1 <= x0_2 or x1_2 <= x0_1 or y1_1 <= y0_2 or y1_2 <= y0_1)


def bbox_distance(bbox1: Tuple[float, float, float, float],
                  bbox2: Tuple[float, float, float, float]) -> float:
    """
    Calculate Manhattan distance between bbox centers.
    
    Args:
        bbox1: First bbox (x0, y0, x1, y1)
        bbox2: Second bbox (x0, y0, x1, y1)
        
    Returns:
        Manhattan distance between centers
    """
    # Calculate centers
    center1_x = (bbox1[0] + bbox1[2]) / 2
    center1_y = (bbox1[1] + bbox1[3]) / 2
    center2_x = (bbox2[0] + bbox2[2]) / 2
    center2_y = (bbox2[1] + bbox2[3]) / 2
    
    # Manhattan distance
    return abs(center1_x - center2_x) + abs(center1_y - center2_y)


def bbox_iou(bbox1: Tuple[float, float, float, float],
             bbox2: Tuple[float, float, float, float]) -> float:
    """
    Calculate Intersection over Union (IoU) of two bboxes.
    
    Args:
        bbox1: First bbox (x0, y0, x1, y1)
        bbox2: Second bbox (x0, y0, x1, y1)
        
    Returns:
        IoU score (0-1)
    """
    x0_1, y0_1, x1_1, y1_1 = bbox1
    x0_2, y0_2, x1_2, y1_2 = bbox2
    
    # Calculate intersection
    x0_i = max(x0_1, x0_2)
    y0_i = max(y0_1, y0_2)
    x1_i = min(x1_1, x1_2)
    y1_i = min(y1_1, y1_2)
    
    if x1_i <= x0_i or y1_i <= y0_i:
        return 0.0
    
    intersection = (x1_i - x0_i) * (y1_i - y0_i)
    
    # Calculate union
    area1 = (x1_1 - x0_1) * (y1_1 - y0_1)
    area2 = (x1_2 - x0_2) * (y1_2 - y0_2)
    union = area1 + area2 - intersection
    
    if union == 0:
        return 0.0
    
    return intersection / union


def bbox_merge(bboxes: List[Tuple[float, float, float, float]]) -> Tuple[float, float, float, float]:
    """
    Merge multiple bboxes into single bbox containing all.
    
    Args:
        bboxes: List of bboxes to merge
        
    Returns:
        Merged bbox containing all input bboxes
    """
    if not bboxes:
        return (0, 0, 0, 0)
    
    x0_min = min(bbox[0] for bbox in bboxes)
    y0_min = min(bbox[1] for bbox in bboxes)
    x1_max = max(bbox[2] for bbox in bboxes)
    y1_max = max(bbox[3] for bbox in bboxes)
    
    return (x0_min, y0_min, x1_max, y1_max)


def validate_bbox(bbox: Tuple[float, float, float, float]) -> bool:
    """
    Validate bbox coordinates.
    
    Args:
        bbox: Bbox to validate (x0, y0, x1, y1)
        
    Returns:
        True if valid
    """
    x0, y0, x1, y1 = bbox
    return x1 > x0 and y1 > y0


def bbox_contains_point(bbox: Tuple[float, float, float, float], 
                        point: Tuple[float, float]) -> bool:
    """
    Check if bbox contains a point.
    
    Args:
        bbox: Bounding box (x0, y0, x1, y1)
        point: Point (x, y)
        
    Returns:
        True if point is inside bbox
    """
    x0, y0, x1, y1 = bbox
    x, y = point
    return x0 <= x <= x1 and y0 <= y <= y1


def bbox_contains(bbox1: Tuple[float, float, float, float],
                  bbox2: Tuple[float, float, float, float]) -> bool:
    """
    Check if bbox1 completely contains bbox2.
    
    Args:
        bbox1: Outer bbox (x0, y0, x1, y1)
        bbox2: Inner bbox (x0, y0, x1, y1)
        
    Returns:
        True if bbox1 contains bbox2
    """
    x0_1, y0_1, x1_1, y1_1 = bbox1
    x0_2, y0_2, x1_2, y1_2 = bbox2
    
    return x0_1 <= x0_2 and y0_1 <= y0_2 and x1_1 >= x1_2 and y1_1 >= y1_2


def bbox_area(bbox: Tuple[float, float, float, float]) -> float:
    """
    Calculate area of bbox.
    
    Args:
        bbox: Bounding box (x0, y0, x1, y1)
        
    Returns:
        Area in square units
    """
    x0, y0, x1, y1 = bbox
    return (x1 - x0) * (y1 - y0)

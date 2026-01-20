"""
Confidence scoring for extraction results.

Tracks extraction quality and reliability through the pipeline.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


@dataclass
class ConfidenceScore:
    """Confidence score with breakdown and evidence."""
    
    overall: float  # 0.0 - 1.0
    breakdown: Dict[str, float] = field(default_factory=dict)  # Component scores
    evidence: List[str] = field(default_factory=list)  # Supporting reasons
    
    def __post_init__(self):
        """Validate confidence score."""
        if not 0.0 <= self.overall <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.overall}")
    
    def add_component(self, name: str, score: float, weight: float = 1.0):
        """Add a component score to the breakdown."""
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"Component score must be 0.0-1.0, got {score}")
        
        self.breakdown[name] = score
        
        # Recalculate overall as weighted average
        if self.breakdown:
            total_score = sum(s * weight for s in self.breakdown.values())
            self.overall = total_score / len(self.breakdown)
    
    def add_evidence(self, reason: str):
        """Add evidence supporting this confidence score."""
        self.evidence.append(reason)
    
    def needs_refinement(self, threshold: float = 0.8) -> bool:
        """Check if confidence is below acceptable threshold."""
        return self.overall < threshold


class ExtractionResult(BaseModel):
    """Extraction result with confidence metadata."""
    
    data: Dict[str, Any] = Field(..., description="Extracted data")
    confidence: ConfidenceScore = Field(..., description="Overall confidence score")
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Source citations supporting extraction"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (model, timestamps, etc.)"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    def get_field_confidence(self, field_name: str) -> Optional[float]:
        """Get confidence score for a specific field."""
        return self.confidence.breakdown.get(field_name)
    
    def get_low_confidence_fields(self, threshold: float = 0.7) -> List[str]:
        """Get list of fields with confidence below threshold."""
        return [
            field for field, score in self.confidence.breakdown.items()
            if score < threshold
        ]
    
    def needs_refinement(self, threshold: float = 0.8) -> bool:
        """Check if this extraction needs refinement."""
        return self.confidence.needs_refinement(threshold)


class SearchConfidence:
    """Calculate confidence from search results."""
    
    @staticmethod
    def from_search_scores(
        search_results: List[Dict[str, Any]],
        top_k: int = 5
    ) -> float:
        """
        Calculate confidence from search result scores.
        
        High confidence when:
        - Top results have high scores
        - Scores are consistent (low variance)
        - Multiple relevant results found
        
        Args:
            search_results: List of search results with 'score' field
            top_k: Number of top results to consider
            
        Returns:
            Confidence score 0.0 - 1.0
        """
        if not search_results:
            return 0.0
        
        # Get top k scores
        scores = [r.get("score", 0.0) for r in search_results[:top_k]]
        
        if not scores:
            return 0.0
        
        # Average of top scores
        avg_score = sum(scores) / len(scores)
        
        # Penalize if variance is high (inconsistent results)
        if len(scores) > 1:
            variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
            consistency = max(0, 1.0 - variance)
        else:
            consistency = 0.5
        
        # Combine average score with consistency
        confidence = (avg_score * 0.7) + (consistency * 0.3)
        
        return min(1.0, max(0.0, confidence))


class LLMConfidence:
    """Calculate confidence from LLM responses."""
    
    @staticmethod
    def from_response_quality(
        response: str,
        expected_fields: List[str],
        extracted_data: Dict[str, Any]
    ) -> ConfidenceScore:
        """
        Calculate confidence based on LLM response quality.
        
        High confidence when:
        - All expected fields present
        - Fields have non-empty values
        - Response is valid JSON
        - No parsing errors
        
        Args:
            response: Raw LLM response
            expected_fields: Fields expected in extraction
            extracted_data: Parsed extraction data
            
        Returns:
            ConfidenceScore with breakdown
        """
        confidence = ConfidenceScore(overall=0.0)
        
        # Field completeness
        if expected_fields:
            present_fields = sum(
                1 for f in expected_fields 
                if f in extracted_data and extracted_data[f]
            )
            completeness = present_fields / len(expected_fields)
            confidence.add_component("completeness", completeness)
            
            if completeness == 1.0:
                confidence.add_evidence("All expected fields present")
            elif completeness > 0.8:
                confidence.add_evidence("Most expected fields present")
            else:
                confidence.add_evidence(
                    f"Missing {len(expected_fields) - present_fields} fields"
                )
        
        # Field value quality (non-empty, reasonable length)
        if extracted_data:
            quality_scores = []
            for key, value in extracted_data.items():
                if isinstance(value, str):
                    # Non-empty string with reasonable length
                    if len(value) > 0 and len(value) < 1000:
                        quality_scores.append(1.0)
                    elif len(value) == 0:
                        quality_scores.append(0.0)
                    else:
                        quality_scores.append(0.8)  # Too long
                elif isinstance(value, (list, dict)):
                    # Non-empty collection
                    quality_scores.append(1.0 if value else 0.5)
                else:
                    quality_scores.append(1.0)
            
            if quality_scores:
                field_quality = sum(quality_scores) / len(quality_scores)
                confidence.add_component("field_quality", field_quality)
        
        # Response parsability (already parsed successfully if we have data)
        if extracted_data:
            confidence.add_component("parsability", 1.0)
            confidence.add_evidence("Response parsed successfully")
        else:
            confidence.add_component("parsability", 0.0)
            confidence.add_evidence("Failed to parse response")
        
        return confidence
    
    @staticmethod
    def from_multiple_responses(
        responses: List[Dict[str, Any]]
    ) -> ConfidenceScore:
        """
        Calculate confidence from multiple LLM responses (ensemble).
        
        High confidence when responses agree on extracted values.
        
        Args:
            responses: List of extraction results from different calls
            
        Returns:
            ConfidenceScore based on agreement
        """
        if not responses:
            return ConfidenceScore(overall=0.0)
        
        if len(responses) == 1:
            # Single response, use moderate confidence
            return ConfidenceScore(overall=0.7)
        
        # Calculate agreement across responses
        # For each field, check if values match
        all_fields = set()
        for r in responses:
            all_fields.update(r.keys())
        
        agreement_scores = []
        for field in all_fields:
            values = [r.get(field) for r in responses if field in r]
            if not values:
                continue
            
            # Check if all values are the same
            unique_values = len(set(str(v) for v in values))
            agreement = 1.0 / unique_values  # Perfect agreement = 1.0
            agreement_scores.append(agreement)
        
        if not agreement_scores:
            return ConfidenceScore(overall=0.5)
        
        avg_agreement = sum(agreement_scores) / len(agreement_scores)
        
        confidence = ConfidenceScore(overall=avg_agreement)
        confidence.add_evidence(
            f"{len(responses)} responses, {avg_agreement:.0%} agreement"
        )
        
        return confidence


class ValidationConfidence:
    """Calculate confidence from validation checks."""
    
    @staticmethod
    def from_schema_validation(
        extracted_data: Dict[str, Any],
        schema: Dict[str, Any],
        validation_errors: List[str]
    ) -> float:
        """
        Calculate confidence based on schema validation.
        
        Args:
            extracted_data: Extracted data
            schema: Expected schema
            validation_errors: List of validation errors
            
        Returns:
            Confidence score 0.0 - 1.0
        """
        if not validation_errors:
            return 1.0
        
        # Penalize based on number of errors
        # Fewer errors = higher confidence
        error_penalty = len(validation_errors) * 0.1
        confidence = max(0.0, 1.0 - error_penalty)
        
        return confidence
    
    @staticmethod
    def from_cross_field_consistency(
        extracted_data: Dict[str, Any],
        consistency_rules: List[Dict[str, Any]]
    ) -> float:
        """
        Check cross-field consistency.
        
        Example rules:
        - If message_type contains "OBS", direction should be "device_to_host"
        - If namespace is set, message_category should be "vendor_extension"
        
        Args:
            extracted_data: Extracted data
            consistency_rules: List of consistency rules to check
            
        Returns:
            Confidence score 0.0 - 1.0
        """
        if not consistency_rules:
            return 1.0
        
        passed = 0
        for rule in consistency_rules:
            # Simple rule checking (can be enhanced)
            field = rule.get("field")
            expected_value = rule.get("expected")
            actual_value = extracted_data.get(field)
            
            if actual_value == expected_value:
                passed += 1
        
        return passed / len(consistency_rules) if consistency_rules else 1.0

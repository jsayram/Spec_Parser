"""
Validation agent for iterative extraction refinement.

Validates extraction results and re-queries for missing or low-confidence data.
"""

from typing import Dict, List, Any, Optional
from loguru import logger

from spec_parser.llm.llm_interface import LLMInterface
from spec_parser.llm.prompts import PromptTemplates
from spec_parser.search.hybrid_search import HybridSearcher
from spec_parser.schemas.confidence import (
    ExtractionResult,
    ConfidenceScore,
    LLMConfidence,
    ValidationConfidence
)


class ValidationAgent:
    """
    Validates and iteratively refines extractions.
    
    Process:
    1. Validate extraction against schema
    2. Check confidence scores
    3. Identify gaps or low-confidence fields
    4. Re-query for missing data
    5. Merge refined data with original
    6. Repeat until confidence threshold met or max iterations
    """
    
    def __init__(
        self,
        llm: LLMInterface,
        searcher: HybridSearcher,
        confidence_threshold: float = 0.8,
        max_iterations: int = 3
    ):
        """
        Initialize validation agent.
        
        Args:
            llm: LLM interface for re-extraction
            searcher: Hybrid searcher for context retrieval
            confidence_threshold: Minimum acceptable confidence (0.0-1.0)
            max_iterations: Maximum refinement iterations
        """
        self.llm = llm
        self.searcher = searcher
        self.confidence_threshold = confidence_threshold
        self.max_iterations = max_iterations
    
    def validate_and_refine(
        self,
        extraction_result: ExtractionResult,
        schema: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ExtractionResult:
        """
        Validate extraction and refine if needed.
        
        Args:
            extraction_result: Initial extraction result
            schema: Expected data schema
            context: Additional context (device_name, etc.)
            
        Returns:
            Refined ExtractionResult with improved confidence
        """
        current_result = extraction_result
        iteration = 0
        
        logger.info(
            f"Starting validation: confidence={current_result.confidence.overall:.2f}, "
            f"threshold={self.confidence_threshold}"
        )
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Check if refinement needed
            if not current_result.needs_refinement(self.confidence_threshold):
                logger.info(
                    f"Confidence threshold met after {iteration-1} iterations: "
                    f"{current_result.confidence.overall:.2f}"
                )
                break
            
            logger.info(f"Refinement iteration {iteration}/{self.max_iterations}")
            
            # Identify what needs improvement
            validation_result = self._validate_extraction(
                current_result.data, schema
            )
            
            if not validation_result["needs_refinement"]:
                logger.info("Validation passed, no refinement needed")
                break
            
            # Re-extract missing or low-confidence fields
            refined_data = self._refine_extraction(
                current_result,
                validation_result,
                context
            )
            
            if not refined_data:
                logger.warning("Refinement produced no new data, stopping")
                break
            
            # Merge refined data
            merged_data = self._merge_extractions(
                current_result.data,
                refined_data
            )
            
            # Recalculate confidence
            new_confidence = self._calculate_confidence(
                merged_data,
                schema,
                current_result.confidence
            )
            
            current_result = ExtractionResult(
                data=merged_data,
                confidence=new_confidence,
                sources=current_result.sources,
                metadata={
                    **current_result.metadata,
                    "refinement_iterations": iteration,
                    "final_confidence": new_confidence.overall
                }
            )
            
            logger.info(
                f"After refinement {iteration}: "
                f"confidence={new_confidence.overall:.2f}"
            )
        
        return current_result
    
    def _validate_extraction(
        self,
        extracted_data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate extraction against schema.
        
        Args:
            extracted_data: Extracted data
            schema: Expected schema
            
        Returns:
            ValidationResult with gaps and issues
        """
        validation_result = {
            "needs_refinement": False,
            "missing_fields": [],
            "low_confidence_fields": [],
            "errors": []
        }
        
        # Check required fields
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in extracted_data or not extracted_data[field]:
                validation_result["missing_fields"].append(field)
                validation_result["needs_refinement"] = True
        
        # Check field types
        properties = schema.get("properties", {})
        for field, value in extracted_data.items():
            if field not in properties:
                continue
            
            expected_type = properties[field].get("type")
            actual_type = type(value).__name__
            
            type_map = {
                "string": "str",
                "number": ["int", "float"],
                "array": "list",
                "object": "dict",
                "boolean": "bool"
            }
            
            expected_types = type_map.get(expected_type, [expected_type])
            if isinstance(expected_types, str):
                expected_types = [expected_types]
            
            if actual_type not in expected_types:
                validation_result["errors"].append(
                    f"Field '{field}': expected {expected_type}, got {actual_type}"
                )
                validation_result["needs_refinement"] = True
        
        return validation_result
    
    def _refine_extraction(
        self,
        current_result: ExtractionResult,
        validation_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Re-extract missing or low-confidence fields.
        
        Args:
            current_result: Current extraction result
            validation_result: Validation results
            context: Additional context
            
        Returns:
            Refined data dictionary or None
        """
        missing_fields = validation_result.get("missing_fields", [])
        
        if not missing_fields:
            return None
        
        logger.info(f"Re-extracting {len(missing_fields)} missing fields")
        
        # Build targeted query for missing fields
        field_names = ", ".join(missing_fields)
        query = f"Find information about: {field_names}"
        
        # Search for relevant context
        search_results = self.searcher.search(query, k=10)
        
        if not search_results:
            logger.warning("No search results for refinement query")
            return None
        
        context_chunks = [r["text"] for r in search_results]
        
        # Build refinement prompt
        prompt = self._build_refinement_prompt(
            missing_fields,
            context_chunks,
            current_result.data,
            context.get("device_name", "Unknown Device")
        )
        
        # Call LLM
        try:
            response = self.llm.generate(prompt)
            
            # Parse response
            from spec_parser.llm.nodes import strip_markdown_json
            import json
            
            cleaned = strip_markdown_json(response)
            refined_data = json.loads(cleaned)
            
            return refined_data
            
        except Exception as e:
            logger.error(f"Refinement extraction failed: {e}")
            return None
    
    def _build_refinement_prompt(
        self,
        missing_fields: List[str],
        context_chunks: List[str],
        current_data: Dict[str, Any],
        device_name: str
    ) -> str:
        """Build prompt for refinement extraction."""
        context = "\n\n---\n\n".join(context_chunks)
        field_list = "\n".join(f"- {field}" for field in missing_fields)
        
        return f"""You are refining an extraction for the {device_name} device.

**Current extraction** (incomplete):
{current_data}

**Missing fields that need to be found**:
{field_list}

**Additional context from specification**:
{context}

**Your task**: Extract ONLY the missing fields listed above from the provided context.

Return a JSON object with only the missing fields. For each field:
- Extract the value from the context
- If not found, use null
- Include brief justification from context

Example output:
{{
  "field_name": {{
    "value": "extracted value",
    "justification": "Found in section X, page Y"
  }}
}}

Return ONLY valid JSON, no explanations.
"""
    
    def _merge_extractions(
        self,
        original: Dict[str, Any],
        refined: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge refined data with original.
        
        Strategy:
        - Keep original values if present and non-empty
        - Fill in missing values from refined data
        - For conflicts, prefer refined data (it's more targeted)
        
        Args:
            original: Original extraction
            refined: Refined extraction
            
        Returns:
            Merged data dictionary
        """
        merged = original.copy()
        
        for key, value in refined.items():
            # Handle nested value/justification structure
            if isinstance(value, dict) and "value" in value:
                actual_value = value["value"]
            else:
                actual_value = value
            
            # Only update if original is missing or empty
            if key not in merged or not merged[key]:
                merged[key] = actual_value
                logger.debug(f"Merged field '{key}': {actual_value}")
        
        return merged
    
    def _calculate_confidence(
        self,
        merged_data: Dict[str, Any],
        schema: Dict[str, Any],
        previous_confidence: ConfidenceScore
    ) -> ConfidenceScore:
        """
        Recalculate confidence after refinement.
        
        Args:
            merged_data: Merged extraction data
            schema: Expected schema
            previous_confidence: Previous confidence score
            
        Returns:
            Updated ConfidenceScore
        """
        # Field completeness
        required_fields = schema.get("required", [])
        if required_fields:
            present = sum(1 for f in required_fields if f in merged_data and merged_data[f])
            completeness = present / len(required_fields)
        else:
            completeness = 1.0
        
        # Schema validation
        validation_errors = []
        properties = schema.get("properties", {})
        for field, value in merged_data.items():
            if field in properties:
                expected_type = properties[field].get("type")
                actual_type = type(value).__name__
                # Basic type checking
                if expected_type == "string" and not isinstance(value, str):
                    validation_errors.append(f"{field}: type mismatch")
        
        schema_confidence = ValidationConfidence.from_schema_validation(
            merged_data, schema, validation_errors
        )
        
        # Combine scores
        new_confidence = ConfidenceScore(overall=0.0)
        new_confidence.add_component("completeness", completeness)
        new_confidence.add_component("schema_validation", schema_confidence)
        
        # Give some weight to previous confidence
        new_confidence.add_component("previous", previous_confidence.overall, weight=0.5)
        
        if completeness == 1.0:
            new_confidence.add_evidence("All required fields present after refinement")
        
        return new_confidence

"""LLM extraction orchestration using BatchNode pattern."""

import json
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from spec_parser.llm.llm_interface import LLMInterface
from spec_parser.llm.prompts import PromptTemplates
from spec_parser.search.hybrid_search import HybridSearcher
from spec_parser.search.faiss_indexer import FAISSIndexer
from spec_parser.search.bm25_searcher import BM25Searcher
from spec_parser.schemas.confidence import (
    ExtractionResult,
    ConfidenceScore,
    SearchConfidence,
    LLMConfidence,
    ValidationConfidence,
)
from spec_parser.llm.validation_agent import ValidationAgent


def strip_markdown_json(text: str) -> str:
    """Strip markdown code block markers and explanatory text from JSON response.
    
    LLMs often wrap JSON in ```json ... ``` markers or add explanatory text.
    """
    text = text.strip()
    
    # Find JSON block in markdown
    if "```json" in text:
        # Extract content between ```json and ```
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end != -1:
            text = text[start:end]
    elif "```" in text:
        # Extract content between ``` and ```
        start = text.find("```") + 3
        end = text.find("```", start)
        if end != -1:
            text = text[start:end]
    else:
        # Try to find JSON array or object markers
        # Look for first [ or { and last ] or }
        start_bracket = text.find("[")
        start_brace = text.find("{")
        
        if start_bracket != -1 and (start_brace == -1 or start_bracket < start_brace):
            # Array
            end = text.rfind("]")
            if end != -1:
                text = text[start_bracket:end+1]
        elif start_brace != -1:
            # Object
            end = text.rfind("}")
            if end != -1:
                text = text[start_brace:end+1]
    
    return text.strip()


class ExtractionNode:
    """Base class for extraction nodes (PocketFlow-inspired)."""

    def __init__(self, name: str, llm: LLMInterface):
        """Initialize extraction node.
        
        Args:
            name: Node identifier for logging
            llm: LLM interface with caching
        """
        self.name = name
        self.llm = llm
        self.prompts = PromptTemplates()

    def prep(self, context: dict[str, Any]) -> dict[str, Any]:
        """Prepare node execution (pre-processing).
        
        Args:
            context: Shared execution context
            
        Returns:
            Updated context
        """
        logger.debug(f"[{self.name}] Prep phase")
        return context

    def exec(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute node (main LLM call).
        
        Args:
            context: Shared execution context
            
        Returns:
            Updated context with results
        """
        logger.info(f"[{self.name}] Exec phase")
        return context

    def post(self, context: dict[str, Any]) -> dict[str, Any]:
        """Post-process node results.
        
        Args:
            context: Shared execution context
            
        Returns:
            Finalized context
        """
        logger.debug(f"[{self.name}] Post phase")
        return context

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run full node lifecycle: prep → exec → post.
        
        Args:
            context: Shared execution context
            
        Returns:
            Updated context
        """
        context = self.prep(context)
        context = self.exec(context)
        context = self.post(context)
        return context


class MessageDiscoveryNode(ExtractionNode):
    """Discover all POCT1-A messages in specification."""

    def __init__(self, llm: LLMInterface, searcher: HybridSearcher):
        """Initialize message discovery node.
        
        Args:
            llm: LLM interface
            searcher: Hybrid search for context retrieval
        """
        super().__init__("MessageDiscovery", llm)
        self.searcher = searcher

    def prep(self, context: dict[str, Any]) -> dict[str, Any]:
        """Retrieve relevant chunks about message types.
        
        Args:
            context: Must contain 'device_name'
            
        Returns:
            Context with 'discovery_chunks' and 'discovery_search_results'
        """
        device_name = context["device_name"]
        
        # Search for message discovery with POCT1-A specific patterns
        # Generic search queries for ANY POCT1-A specification
        # Discover ALL message types, vendor extensions, and bidirectional patterns
        queries = [
            "POCT1-A message type structure supported communication",
            "table of contents messages message structure",
            "bidirectional communication host analyzer device interface",
            "message definition field structure data type",
            "vendor specific extension custom message namespace",
            "message flow diagram sequence bidirectional request response",
            "supported messages implemented protocol specification",
            "message trigger event query response acknowledgment",
            "communication pattern host device analyzer bidirectional",
            "message structure component segment field cardinality optionality"
        ]
        
        chunks = []
        all_results = []
        seen_texts = set()
        for query in queries:
            results = self.searcher.search(query, k=5)
            all_results.extend(results)
            for r in results:
                text = r["text"]
                # Deduplicate by content
                if text not in seen_texts:
                    chunks.append(text)
                    seen_texts.add(text)
        
        context["discovery_chunks"] = chunks[:20]  # Increase to 20 best chunks
        context["discovery_search_results"] = all_results  # Store for confidence calculation
        logger.info(f"[{self.name}] Retrieved {len(context['discovery_chunks'])} context chunks")
        
        return context

    def exec(self, context: dict[str, Any]) -> dict[str, Any]:
        """Call LLM to extract message types.
        
        Args:
            context: Must contain 'device_name', 'discovery_chunks', 'discovery_search_results'
            
        Returns:
            Context with 'discovered_messages' as ExtractionResult
        """
        prompt = self.prompts.message_discovery(
            context_chunks=context["discovery_chunks"],
            device_name=context["device_name"]
        )
        
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=self.prompts.system_prompt(),
            device_id=context.get("device_id"),
            message_type="discovery"
        )
        
        # Parse JSON response (strip markdown if present)
        try:
            cleaned_response = strip_markdown_json(response)
            messages = json.loads(cleaned_response)
            
            # Calculate confidence scores
            search_results = context.get("discovery_search_results", [])
            
            # Search confidence: average score + consistency
            search_conf = SearchConfidence.calculate(search_results)
            
            # LLM confidence: response quality + completeness
            required_fields = ["message_type", "direction", "description"]
            llm_conf = LLMConfidence.calculate_from_response(
                response=messages,
                required_fields=required_fields,
                raw_response=response
            )
            
            # Overall confidence: weighted combination
            overall_score = 0.4 * search_conf.score + 0.6 * llm_conf.score
            
            confidence = ConfidenceScore(
                overall=overall_score,
                breakdown={
                    "search": search_conf.score,
                    "llm": llm_conf.score,
                },
                evidence=[
                    *search_conf.evidence,
                    *llm_conf.evidence,
                ]
            )
            
            # Create ExtractionResult
            extraction_result = ExtractionResult(
                data=messages,
                confidence=confidence,
                sources=[r.get("citation", "unknown") for r in search_results[:5]],
                metadata={
                    "num_chunks": len(context["discovery_chunks"]),
                    "num_messages": len(messages),
                }
            )
            
            context["discovered_messages"] = extraction_result
            logger.info(
                f"[{self.name}] Discovered {len(messages)} messages "
                f"(confidence: {overall_score:.2f})"
            )
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Failed to parse LLM response: {e}")
            logger.debug(f"[{self.name}] Raw response: {response[:200]}...")
            
            # Return empty result with low confidence
            context["discovered_messages"] = ExtractionResult(
                data=[],
                confidence=ConfidenceScore(
                    overall=0.0,
                    breakdown={"parse_error": 0.0},
                    evidence=["Failed to parse JSON response"]
                ),
                sources=[],
                metadata={"error": str(e)}
            )
        
        return context


class MessageFieldExtractionNode(ExtractionNode):
    """Extract field definitions for a specific message (BatchNode pattern)."""

    def __init__(self, llm: LLMInterface, searcher: HybridSearcher, message_type: str):
        """Initialize field extraction node for one message.
        
        Args:
            llm: LLM interface
            searcher: Hybrid search
            message_type: POCT1-A message type (e.g., "OBS.R01")
        """
        super().__init__(f"FieldExtraction[{message_type}]", llm)
        self.searcher = searcher
        self.message_type = message_type

    def prep(self, context: dict[str, Any]) -> dict[str, Any]:
        """Retrieve chunks relevant to this message.
        
        Args:
            context: Must contain 'device_name'
            
        Returns:
            Context with 'field_chunks' and 'field_search_results'
        """
        # Search for message-specific content
        query = f"{self.message_type} field definitions structure"
        results = self.searcher.search(query, k=5)
        
        context["field_chunks"] = [r["text"] for r in results]
        context["field_search_results"] = results
        logger.info(
            f"[{self.name}] Retrieved {len(context['field_chunks'])} chunks "
            f"for {self.message_type}"
        )
        
        return context

    def exec(self, context: dict[str, Any]) -> dict[str, Any]:
        """Extract field definitions for this message.
        
        Args:
            context: Must contain 'device_name', 'field_chunks', 'field_search_results'
            
        Returns:
            Context with 'fields' as ExtractionResult
        """
        prompt = self.prompts.message_field_extraction(
            message_type=self.message_type,
            context_chunks=context["field_chunks"],
            device_name=context["device_name"]
        )
        
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=self.prompts.system_prompt(),
            device_id=context.get("device_id"),
            message_type=self.message_type
        )
        
        # Parse JSON response (strip markdown if present)
        try:
            cleaned_response = strip_markdown_json(response)
            fields = json.loads(cleaned_response)
            
            # Calculate confidence scores
            search_results = context.get("field_search_results", [])
            
            # Search confidence
            search_conf = SearchConfidence.calculate(search_results)
            
            # LLM confidence
            required_fields = ["field_name", "data_type"]
            llm_conf = LLMConfidence.calculate_from_response(
                response=fields,
                required_fields=required_fields,
                raw_response=response
            )
            
            # Field-level confidence: Check individual field completeness
            field_confidence = {}
            for field in fields:
                completeness = sum(
                    1 for key in ["field_name", "data_type", "cardinality", "description"]
                    if field.get(key)
                ) / 4.0
                field_confidence[field.get("field_name", "unknown")] = completeness
            
            avg_field_confidence = (
                sum(field_confidence.values()) / len(field_confidence)
                if field_confidence else 0.0
            )
            
            # Overall confidence
            overall_score = (
                0.3 * search_conf.score +
                0.5 * llm_conf.score +
                0.2 * avg_field_confidence
            )
            
            confidence = ConfidenceScore(
                overall=overall_score,
                breakdown={
                    "search": search_conf.score,
                    "llm": llm_conf.score,
                    "field_completeness": avg_field_confidence,
                },
                evidence=[
                    *search_conf.evidence,
                    *llm_conf.evidence,
                    f"Average field completeness: {avg_field_confidence:.2f}"
                ]
            )
            
            # Create ExtractionResult
            extraction_result = ExtractionResult(
                data=fields,
                confidence=confidence,
                sources=[r.get("citation", "unknown") for r in search_results],
                metadata={
                    "message_type": self.message_type,
                    "num_fields": len(fields),
                    "field_confidence": field_confidence,
                }
            )
            
            context["fields"] = extraction_result
            logger.info(
                f"[{self.name}] Extracted {len(fields)} fields "
                f"(confidence: {overall_score:.2f})"
            )
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Failed to parse fields: {e}")
            logger.debug(f"[{self.name}] Raw response: {response[:200]}...")
            
            context["fields"] = ExtractionResult(
                data=[],
                confidence=ConfidenceScore(
                    overall=0.0,
                    breakdown={"parse_error": 0.0},
                    evidence=["Failed to parse JSON response"]
                ),
                sources=[],
                metadata={"error": str(e)}
            )
        
        return context


class BlueprintFlow:
    """Orchestrate full blueprint extraction using node pipeline."""

    def __init__(
        self,
        device_id: str,
        device_name: str,
        index_dir: Path,
        llm: Optional[LLMInterface] = None
    ):
        """Initialize blueprint extraction flow.
        
        Args:
            device_id: Device identifier (e.g., "Roche_CobasLiat")
            device_name: Human-readable device name
            index_dir: Path to FAISS/BM25 index directory
            llm: LLM interface (or None to create default)
        """
        self.device_id = device_id
        self.device_name = device_name
        
        # Initialize LLM
        self.llm = llm or LLMInterface()
        
        # Load indexes
        from spec_parser.embeddings.embedding_model import EmbeddingModel
        
        embedding_model = EmbeddingModel()
        
        faiss_path = index_dir / "faiss"
        bm25_path = index_dir / "bm25"
        
        # Load FAISS index (classmethod)
        faiss_indexer = FAISSIndexer.load(
            index_path=faiss_path,
            embedding_model=embedding_model
        )
        
        # Load BM25 index (classmethod)
        bm25_searcher = BM25Searcher.load(index_path=bm25_path)
        
        # Initialize hybrid search
        self.searcher = HybridSearcher(
            faiss_indexer=faiss_indexer,
            bm25_searcher=bm25_searcher
        )
        
        # Initialize validation agent
        self.validation_agent = ValidationAgent(
            llm=self.llm,
            searcher=self.searcher,
            confidence_threshold=0.7,  # Refine if confidence < 70%
            max_iterations=2  # Up to 2 refinement iterations
        )
        
        logger.info(f"Initialized BlueprintFlow for {device_name}")

    def run(self) -> dict[str, Any]:
        """Execute full blueprint extraction pipeline.
        
        Returns:
            Complete device blueprint with all message definitions
        """
        # Shared context
        context = {
            "device_id": self.device_id,
            "device_name": self.device_name
        }
        
        # Step 1: Discover messages
        logger.info("=" * 60)
        logger.info("STEP 1: Message Discovery")
        logger.info("=" * 60)
        discovery = MessageDiscoveryNode(self.llm, self.searcher)
        context = discovery.run(context)
        
        # Extract data from ExtractionResult
        discovery_result = context.get("discovered_messages")
        if isinstance(discovery_result, ExtractionResult):
            discovered = discovery_result.data
            discovery_confidence = discovery_result.confidence.overall
            logger.info(f"Discovery confidence: {discovery_confidence:.2f}")
            
            # Refine discovery if confidence is low
            if discovery_confidence < self.validation_agent.confidence_threshold:
                logger.info("Discovery confidence below threshold, refining...")
                schema = {
                    "required_fields": ["message_type", "direction", "description"],
                    "field_types": {
                        "message_type": str,
                        "direction": str,
                        "description": str,
                    }
                }
                discovery_result = self.validation_agent.validate_and_refine(
                    extraction=discovery_result,
                    schema=schema,
                    extraction_type="message_discovery"
                )
                discovered = discovery_result.data
                discovery_confidence = discovery_result.confidence.overall
                logger.info(f"Refined discovery confidence: {discovery_confidence:.2f}")
        else:
            # Fallback for old format
            discovered = discovery_result if discovery_result else []
            discovery_confidence = 0.0
        
        if not discovered:
            logger.error("No messages discovered - aborting")
            return {"error": "No messages found in specification"}
        
        # Step 2: Extract fields for each message (BatchNode pattern)
        logger.info("=" * 60)
        logger.info(f"STEP 2: Field Extraction ({len(discovered)} messages)")
        logger.info("=" * 60)
        
        message_definitions = []
        for msg_info in discovered:
            message_type = msg_info["message_type"]
            
            # Create node for this message
            field_node = MessageFieldExtractionNode(
                self.llm,
                self.searcher,
                message_type
            )
            
            # Run extraction for this message
            msg_context = field_node.run(context.copy())
            
            # Extract data from ExtractionResult
            field_result = msg_context.get("fields")
            if isinstance(field_result, ExtractionResult):
                fields = field_result.data
                field_confidence = field_result.confidence.overall
                field_metadata = field_result.metadata
                
                # Refine field extraction if confidence is low
                if field_confidence < self.validation_agent.confidence_threshold:
                    logger.info(f"Field confidence for {message_type} below threshold, refining...")
                    schema = {
                        "required_fields": ["field_name", "data_type"],
                        "field_types": {
                            "field_name": str,
                            "data_type": str,
                        }
                    }
                    field_result = self.validation_agent.validate_and_refine(
                        extraction=field_result,
                        schema=schema,
                        extraction_type=f"field_extraction_{message_type}"
                    )
                    fields = field_result.data
                    field_confidence = field_result.confidence.overall
                    field_metadata = field_result.metadata
                    logger.info(f"Refined field confidence for {message_type}: {field_confidence:.2f}")
            else:
                fields = field_result if field_result else []
                field_confidence = 0.0
                field_metadata = {}
            
            # Combine with discovery info
            message_def = {
                **msg_info,
                "fields": fields,
                "confidence": field_confidence,
                "field_metadata": field_metadata,
            }
            message_definitions.append(message_def)
        
        # Step 3: Consolidate blueprint
        logger.info("=" * 60)
        logger.info("STEP 3: Blueprint Consolidation")
        logger.info("=" * 60)
        
        blueprint = {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "spec_version": "POCT1-A",  # Could extract this from spec
            "messages": message_definitions,
            "summary": {
                "total_messages": len(message_definitions),
                "core_messages": sum(
                    1 for m in message_definitions
                    if m["message_type"] in ["HELLO", "DST", "OBS", "QCN", "RGT", "EOT", "ACK", "REQ", "CONFG"]
                ),
                "vendor_extensions": sum(
                    1 for m in message_definitions
                    if m["message_type"].startswith("Z")
                ),
                "field_count": sum(len(m["fields"]) for m in message_definitions)
            },
            "cache_stats": self.llm.cache_stats()
        }
        
        logger.info(f"Blueprint complete: {blueprint['summary']}")
        
        return blueprint

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
            Context with 'discovery_chunks'
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
        seen_texts = set()
        for query in queries:
            results = self.searcher.search(query, k=5)
            for r in results:
                text = r["text"]
                # Deduplicate by content
                if text not in seen_texts:
                    chunks.append(text)
                    seen_texts.add(text)
        
        context["discovery_chunks"] = chunks[:20]  # Increase to 20 best chunks
        logger.info(f"[{self.name}] Retrieved {len(context['discovery_chunks'])} context chunks")
        
        return context

    def exec(self, context: dict[str, Any]) -> dict[str, Any]:
        """Call LLM to extract message types.
        
        Args:
            context: Must contain 'device_name', 'discovery_chunks'
            
        Returns:
            Context with 'discovered_messages'
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
            context["discovered_messages"] = messages
            logger.info(f"[{self.name}] Discovered {len(messages)} messages")
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Failed to parse LLM response: {e}")
            logger.debug(f"[{self.name}] Raw response: {response[:200]}...")
            context["discovered_messages"] = []
        
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
            Context with 'field_chunks'
        """
        # Search for message-specific content
        query = f"{self.message_type} field definitions structure"
        results = self.searcher.search(query, k=5)
        
        context["field_chunks"] = [r["text"] for r in results]
        logger.info(
            f"[{self.name}] Retrieved {len(context['field_chunks'])} chunks "
            f"for {self.message_type}"
        )
        
        return context

    def exec(self, context: dict[str, Any]) -> dict[str, Any]:
        """Extract field definitions for this message.
        
        Args:
            context: Must contain 'device_name', 'field_chunks'
            
        Returns:
            Context with 'fields' list
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
            context["fields"] = fields
            logger.info(f"[{self.name}] Extracted {len(fields)} fields")
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Failed to parse fields: {e}")
            logger.debug(f"[{self.name}] Raw response: {response[:200]}...")
            context["fields"] = []
        
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
        
        discovered = context.get("discovered_messages", [])
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
            
            # Combine with discovery info
            message_def = {
                **msg_info,
                "fields": msg_context.get("fields", [])
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

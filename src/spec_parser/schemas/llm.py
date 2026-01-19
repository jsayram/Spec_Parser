"""Pydantic schemas for LLM-related data structures."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class LLMCorrectionRecord(BaseModel):
    """Record of an LLM output correction for caching and refinement."""

    prompt_hash: str = Field(
        ...,
        description="SHA-256 hash of the prompt text for cache lookups"
    )
    model: str = Field(
        ...,
        description="LLM model identifier (e.g., 'qwen2.5-coder:7b', 'claude-3.5-sonnet')"
    )
    prompt_text: str = Field(
        ...,
        description="Full prompt text for debugging and few-shot examples"
    )
    original_response: str = Field(
        ...,
        description="Initial LLM output before human correction"
    )
    corrected_response: Optional[str] = Field(
        None,
        description="Human-corrected output, or None if original was approved"
    )
    is_verified: bool = Field(
        default=False,
        description="True if human has reviewed and approved/corrected this output"
    )
    device_id: Optional[str] = Field(
        None,
        description="Device scope (e.g., 'Roche_CobasLiat') or None for global corrections"
    )
    message_type: Optional[str] = Field(
        None,
        description="POCT1-A message type (e.g., 'HELLO', 'OBS', 'QCN') or None"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When the LLM output was first generated"
    )
    reviewed_at: Optional[datetime] = Field(
        None,
        description="When human review was completed"
    )
    hit_count: int = Field(
        default=0,
        description="Number of times this cached response was used"
    )

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LLMExtractionRequest(BaseModel):
    """Request for LLM-based entity extraction."""

    device_id: str = Field(..., description="Device identifier")
    message_type: Optional[str] = Field(None, description="Specific message to extract")
    context_chunks: list[str] = Field(
        ...,
        description="Text chunks retrieved from FAISS/BM25 search"
    )
    max_tokens: int = Field(4000, description="Maximum response tokens")
    temperature: float = Field(0.0, description="LLM temperature for determinism")


class LLMExtractionResponse(BaseModel):
    """Response from LLM extraction."""

    message_type: str = Field(..., description="Extracted message type")
    field_definitions: list[dict] = Field(
        default_factory=list,
        description="Extracted field definitions with types and constraints"
    )
    sample_messages: list[str] = Field(
        default_factory=list,
        description="Example message instances from spec"
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Citation IDs for provenance"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score"
    )
    model_used: str = Field(..., description="LLM model that generated this")
    prompt_hash: str = Field(..., description="Hash for caching")

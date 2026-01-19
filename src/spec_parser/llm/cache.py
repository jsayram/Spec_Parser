"""SQLite-based cache for LLM corrections with deterministic lookups."""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from spec_parser.schemas.llm import LLMCorrectionRecord


class CorrectionCache:
    """SQLite cache for storing and retrieving LLM corrections.
    
    Provides O(1) lookup by prompt hash with automatic cache hit tracking.
    Thread-safe with SQLite's built-in locking. Portable across all platforms.
    """

    def __init__(self, db_path: Path):
        """Initialize correction cache with SQLite database.
        
        Args:
            db_path: Path to SQLite database file (will be created if missing)
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"Initialized correction cache at {db_path}")

    def _init_db(self) -> None:
        """Create corrections table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corrections (
                    prompt_hash TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    original_response TEXT NOT NULL,
                    corrected_response TEXT,
                    is_verified INTEGER NOT NULL,
                    device_id TEXT,
                    message_type TEXT,
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    hit_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_device_message 
                ON corrections(device_id, message_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_verified 
                ON corrections(is_verified)
            """)
            conn.commit()

    @staticmethod
    def compute_hash(prompt_text: str, model: str) -> str:
        """Compute SHA-256 hash for prompt + model combination.
        
        Args:
            prompt_text: Full prompt text
            model: LLM model identifier
            
        Returns:
            64-character hex hash string
        """
        combined = f"{model}::{prompt_text}"
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    def get(self, prompt_hash: str, increment_hit: bool = True) -> Optional[LLMCorrectionRecord]:
        """Retrieve correction by prompt hash.
        
        Args:
            prompt_hash: SHA-256 hash of prompt + model
            increment_hit: If True, increment hit_count (default: True)
            
        Returns:
            LLMCorrectionRecord if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM corrections WHERE prompt_hash = ?",
                (prompt_hash,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            # Increment hit count if requested
            if increment_hit:
                conn.execute(
                    "UPDATE corrections SET hit_count = hit_count + 1 WHERE prompt_hash = ?",
                    (prompt_hash,)
                )
                conn.commit()
            
            # Convert to Pydantic model
            return LLMCorrectionRecord(
                prompt_hash=row['prompt_hash'],
                model=row['model'],
                prompt_text=row['prompt_text'],
                original_response=row['original_response'],
                corrected_response=row['corrected_response'],
                is_verified=bool(row['is_verified']),
                device_id=row['device_id'],
                message_type=row['message_type'],
                created_at=datetime.fromisoformat(row['created_at']),
                reviewed_at=datetime.fromisoformat(row['reviewed_at']) if row['reviewed_at'] else None,
                hit_count=row['hit_count'] + (1 if increment_hit else 0)
            )

    def put(self, record: LLMCorrectionRecord) -> None:
        """Store or update correction record.
        
        Args:
            record: LLMCorrectionRecord to store
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO corrections (
                    prompt_hash, model, prompt_text, original_response,
                    corrected_response, is_verified, device_id, message_type,
                    created_at, reviewed_at, hit_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.prompt_hash,
                record.model,
                record.prompt_text,
                record.original_response,
                record.corrected_response,
                int(record.is_verified),
                record.device_id,
                record.message_type,
                record.created_at.isoformat(),
                record.reviewed_at.isoformat() if record.reviewed_at else None,
                record.hit_count
            ))
            conn.commit()
        
        logger.debug(f"Stored correction: {record.prompt_hash[:8]}... (verified={record.is_verified})")

    def find_similar(
        self,
        device_id: Optional[str] = None,
        message_type: Optional[str] = None,
        verified_only: bool = True,
        limit: int = 5
    ) -> list[LLMCorrectionRecord]:
        """Find similar verified corrections for few-shot examples.
        
        Args:
            device_id: Filter by device (None = any device)
            message_type: Filter by message type (None = any type)
            verified_only: Only return human-verified corrections
            limit: Maximum number of results
            
        Returns:
            List of correction records, ordered by hit_count descending
        """
        query = "SELECT * FROM corrections WHERE 1=1"
        params = []
        
        if device_id is not None:
            query += " AND device_id = ?"
            params.append(device_id)
        
        if message_type is not None:
            query += " AND message_type = ?"
            params.append(message_type)
        
        if verified_only:
            query += " AND is_verified = 1"
        
        query += " ORDER BY hit_count DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        
        return [
            LLMCorrectionRecord(
                prompt_hash=row['prompt_hash'],
                model=row['model'],
                prompt_text=row['prompt_text'],
                original_response=row['original_response'],
                corrected_response=row['corrected_response'],
                is_verified=bool(row['is_verified']),
                device_id=row['device_id'],
                message_type=row['message_type'],
                created_at=datetime.fromisoformat(row['created_at']),
                reviewed_at=datetime.fromisoformat(row['reviewed_at']) if row['reviewed_at'] else None,
                hit_count=row['hit_count']
            )
            for row in rows
        ]

    def mark_verified(self, prompt_hash: str, corrected_response: Optional[str] = None) -> None:
        """Mark a correction as human-verified.
        
        Args:
            prompt_hash: Hash of the correction to verify
            corrected_response: Optional corrected output (None = original was correct)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE corrections 
                SET is_verified = 1, 
                    reviewed_at = ?,
                    corrected_response = ?
                WHERE prompt_hash = ?
            """, (datetime.now().isoformat(), corrected_response, prompt_hash))
            conn.commit()
        
        logger.info(f"Marked correction as verified: {prompt_hash[:8]}...")

    def stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dictionary with total, verified, and hit rate stats
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) as verified,
                    SUM(hit_count) as total_hits,
                    AVG(hit_count) as avg_hits
                FROM corrections
            """)
            row = cursor.fetchone()
        
        return {
            "total_corrections": row[0],
            "verified_corrections": row[1] or 0,
            "total_cache_hits": row[2] or 0,
            "avg_hits_per_correction": round(row[3] or 0, 2)
        }

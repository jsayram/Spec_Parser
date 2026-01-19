"""Token bucket rate limiter for external API calls."""

import time
from threading import Lock
from typing import Optional

from loguru import logger


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter for API calls.
    
    Implements the token bucket algorithm with configurable rate and burst capacity.
    Used to prevent hitting rate limits on external APIs (Claude, OpenAI, etc.).
    """

    def __init__(
        self,
        rate: float,
        capacity: Optional[int] = None,
        name: str = "RateLimiter"
    ):
        """Initialize rate limiter.
        
        Args:
            rate: Tokens per second (e.g., 1.0 = 60 requests/min)
            capacity: Bucket capacity (burst size). Defaults to rate * 60
            name: Identifier for logging
        """
        self.rate = rate
        self.capacity = capacity or int(rate * 60)
        self.name = name
        
        self.tokens = float(self.capacity)
        self.last_update = time.time()
        self.lock = Lock()
        
        logger.info(
            f"Initialized {name}: {rate:.2f} tokens/sec, "
            f"capacity={self.capacity} (≈{rate*60:.0f} req/min)"
        )

    def acquire(self, tokens: int = 1, block: bool = True) -> bool:
        """Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire (default: 1)
            block: If True, wait until tokens available. If False, return immediately.
            
        Returns:
            True if tokens were acquired, False if not available (only when block=False)
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Refill bucket based on elapsed time
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now
            
            # Check if enough tokens available
            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(
                    f"{self.name}: Acquired {tokens} token(s), "
                    f"{self.tokens:.1f} remaining"
                )
                return True
            
            # Not enough tokens
            if not block:
                logger.debug(f"{self.name}: Not enough tokens, returning False")
                return False
        
        # Wait outside lock to avoid blocking other threads
        wait_time = (tokens - self.tokens) / self.rate
        logger.debug(f"{self.name}: Waiting {wait_time:.2f}s for tokens")
        time.sleep(wait_time)
        
        # Try again after waiting
        return self.acquire(tokens, block=False)

    def __enter__(self):
        """Context manager entry."""
        self.acquire(tokens=1, block=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass


class NoOpRateLimiter:
    """No-op rate limiter for local models with no rate limits."""

    def __init__(self, name: str = "NoOpRateLimiter"):
        """Initialize no-op rate limiter.
        
        Args:
            name: Identifier for logging
        """
        self.name = name
        logger.debug(f"Initialized {name}: no rate limiting")

    def acquire(self, tokens: int = 1, block: bool = True) -> bool:
        """Always returns True immediately.
        
        Args:
            tokens: Ignored
            block: Ignored
            
        Returns:
            Always True
        """
        return True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

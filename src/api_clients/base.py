"""Base API client with connection pooling and rate limiting."""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: int, burst: int = 10):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()

    def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens, return True if successful."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_for_token(self, tokens: int = 1):
        """Wait until tokens are available."""
        while not self.acquire(tokens):
            time.sleep(0.1)


class BaseAPIClient(ABC):
    """Base class for API clients."""

    def __init__(self, api_key: str, rate_limit: int, model: str):
        self.api_key = api_key
        self.model = model
        self.rate_limiter = RateLimiter(rate=rate_limit / 60)
        self.client: Optional[httpx.Client] = None
        self._request_count = 0
        self._error_count = 0
        self._total_latency = 0.0

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client with connection pooling."""
        if self.client is None or self.client.is_closed:
            self.client = httpx.Client(
                timeout=httpx.Timeout(60.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self.client

    def close(self):
        """Close the HTTP client."""
        if self.client and not self.client.is_closed:
            self.client.close()
            self.client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _make_request(self, *args, **kwargs) -> Any:
        """Make API request with retry logic."""
        self.rate_limiter.wait_for_token()

        start_time = time.time()
        try:
            result = self._execute_request(*args, **kwargs)
            latency = time.time() - start_time

            self._request_count += 1
            self._total_latency += latency

            logger.info(
                "api_request_success",
                model=self.model,
                latency=latency,
                request_count=self._request_count,
            )
            return result

        except Exception as e:
            self._error_count += 1
            logger.error(
                "api_request_failed",
                model=self.model,
                error=str(e),
                error_count=self._error_count,
            )
            raise

    @abstractmethod
    def _execute_request(self, *args, **kwargs) -> Any:
        """Execute the actual API request."""
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response from the model."""
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics."""
        avg_latency = self._total_latency / self._request_count if self._request_count > 0 else 0
        error_rate = self._error_count / self._request_count if self._request_count > 0 else 0

        return {
            "model": self.model,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": error_rate,
            "avg_latency": avg_latency,
        }

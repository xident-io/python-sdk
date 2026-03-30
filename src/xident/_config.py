"""SDK configuration — immutable after construction.

Mirrors the PHP SDK's Config class: readonly properties, sensible defaults,
validation on construction.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass


DEFAULT_BASE_URL = "http://localhost:9000"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
API_VERSION = "verify/v1"
SDK_VERSION = "1.0.0"


@dataclass(frozen=True)
class Config:
    """Immutable SDK configuration.

    Attributes:
        api_key: Your Xident secret API key (sk_live_xxx or sk_test_xxx).
        base_url: API base URL (default: http://localhost:9000).
        timeout: Request timeout in seconds (default: 30).
        max_retries: Max retries on 5xx errors (default: 3).
        headers: Extra headers to send with every request.
    """

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    headers: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("API key cannot be empty")
        # Strip trailing slash from base_url
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))
        # Clamp timeout to at least 1
        object.__setattr__(self, "timeout", max(1, self.timeout))
        # Clamp max_retries to at least 0
        object.__setattr__(self, "max_retries", max(0, self.max_retries))

    @property
    def api_url(self) -> str:
        """Full API URL (base + version prefix)."""
        return f"{self.base_url}/{API_VERSION}"

    @property
    def user_agent(self) -> str:
        """User-Agent header value."""
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return f"Xident-Python/{SDK_VERSION} Python/{py_version} {platform.system()}/{platform.release()}"

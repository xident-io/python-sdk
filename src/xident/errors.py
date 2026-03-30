"""Exception hierarchy for the Xident SDK.

Maps HTTP status codes to typed exceptions, following the OpenAI/Stripe
pattern. Every exception carries the API error code and request ID for
debugging and support tickets.

Hierarchy::

    XidentError (base)
    +-- APIError (has status_code, error_code, request_id)
    |   +-- AuthenticationError (401/403)
    |   +-- ValidationError (400)
    |   +-- NotFoundError (404)
    |   +-- RateLimitError (429, has retry_after)
    |   +-- ServerError (5xx)
    +-- NetworkError (connection failed, timeout, DNS)
"""

from __future__ import annotations


class XidentError(Exception):
    """Base exception for all Xident SDK errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class APIError(XidentError):
    """Raised when the Xident API returns an error response.

    Attributes:
        status_code: HTTP status code (e.g. 400, 401, 404, 429, 500).
        error_code: API error code string (e.g. "INVALID_REQUEST").
        request_id: Unique request identifier for support tickets.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        error_code: str = "",
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id

    def __str__(self) -> str:
        parts = [self.message]
        if self.error_code:
            parts.append(f"code={self.error_code}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        parts.append(f"status={self.status_code}")
        return " | ".join(parts)


class AuthenticationError(APIError):
    """Raised when the API key is invalid, expired, or missing (HTTP 401/403)."""


class ValidationError(APIError):
    """Raised when request parameters are invalid (HTTP 400)."""


class NotFoundError(APIError):
    """Raised when the requested resource does not exist (HTTP 404)."""


class RateLimitError(APIError):
    """Raised when the API rate limit is exceeded (HTTP 429).

    Attributes:
        retry_after: Seconds to wait before retrying, or None if not provided.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        error_code: str = "",
        request_id: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            error_code=error_code,
            request_id=request_id,
        )
        self.retry_after = retry_after


class ServerError(APIError):
    """Raised when the Xident API returns a server error (HTTP 5xx)."""


class NetworkError(XidentError):
    """Raised when a network error occurs (DNS, timeout, SSL, connection refused)."""

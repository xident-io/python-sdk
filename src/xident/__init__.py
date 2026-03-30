"""Xident Python SDK -- official client for the Xident age & identity verification API.

Usage::

    import xident

    # Synchronous
    client = xident.Xident(api_key="sk_live_...")
    result = client.verification.init(callback_url="https://example.com/cb", min_age=18)
    print(result.verify_url)

    # Asynchronous
    client = xident.AsyncXident(api_key="sk_live_...")
    result = await client.verification.init(callback_url="https://example.com/cb", min_age=18)

    # Webhook verification
    event = client.webhooks.construct_event(payload, signature, secret)
"""

from ._client import AsyncXident, Xident
from ._config import SDK_VERSION
from ._types import SessionStatus
from .errors import (
    APIError,
    AuthenticationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    XidentError,
)
from .responses import InitResult, SessionResult

__version__ = SDK_VERSION

__all__ = [
    # Clients
    "Xident",
    "AsyncXident",
    # Responses
    "InitResult",
    "SessionResult",
    # Types
    "SessionStatus",
    # Errors
    "XidentError",
    "APIError",
    "AuthenticationError",
    "ValidationError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    # Version
    "__version__",
]

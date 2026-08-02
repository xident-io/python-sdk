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
from .responses import (
    BlacklistEntry,
    BlacklistPage,
    Face2FAChallenge,
    Face2FAEnrollment,
    Face2FAStatus,
    InitResult,
    SessionResult,
)

__version__ = SDK_VERSION

# Grouped by role rather than sorted alphabetically: this list doubles as the
# public-API map a reader scans first. noqa keeps ruff's RUF022 from flattening
# the grouping away.
__all__ = [  # noqa: RUF022
    # Clients
    "Xident",
    "AsyncXident",
    # Responses
    "InitResult",
    "SessionResult",
    "Face2FAChallenge",
    "Face2FAStatus",
    "Face2FAEnrollment",
    "BlacklistEntry",
    "BlacklistPage",
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

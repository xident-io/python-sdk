"""Type definitions for the Xident SDK.

Contains TypedDicts for API parameters and the SessionStatus enum.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, TypedDict


class SessionStatus(str, Enum):
    """Verification session lifecycle states.

    Mirrors the Go backend's SessionStatus enum and the PHP SDK's
    SessionStatus enum exactly.

    Note on spelling: the server-side ``GET /result/{token}`` status uses the
    American spelling ``"canceled"`` (this enum). The browser callback query
    parameter ``?status=`` uses the British spelling ``"cancelled"`` (values:
    ``success`` | ``failed`` | ``cancelled``) -- that value is only ever present
    on the callback URL, never in the ``/result`` response body.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    CLAIMED = "claimed"

    @property
    def is_terminal(self) -> bool:
        """Whether the session has reached a terminal state (no more changes possible)."""
        return self in (
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.CANCELED,
            SessionStatus.CLAIMED,
        )


class InitParams(TypedDict, total=False):
    """Parameters for creating an init token.

    Attributes:
        callback_url: URL where user is redirected after verification (required).
        min_age: Minimum age threshold (1-99). When ``purpose`` is
            "id_verification", 0 is also accepted (identity-only, no age gate).
        success_url: Override redirect URL on success.
        failed_url: Override redirect URL on failure.
        user_id: Your application's user identifier.
        theme: Widget theme ("light", "dark", "system").
        locale: Widget locale (e.g. "en", "de", "fr").
        metadata: Opaque string stored with the session.
        purpose: Verification purpose ("age_verification" or "id_verification").
    """

    callback_url: str
    min_age: int
    success_url: str
    failed_url: str
    user_id: str
    theme: str
    locale: str
    metadata: str
    purpose: str


class _APIResponseData(TypedDict, total=False):
    """Internal: parsed API response envelope."""

    success: bool
    data: Optional[dict]  # type: ignore[type-arg]
    error: Optional[dict]  # type: ignore[type-arg]
    meta: Optional[dict]  # type: ignore[type-arg]

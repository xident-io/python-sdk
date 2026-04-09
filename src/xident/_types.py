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
        min_age: Minimum age threshold (12, 15, 18, 21, 25).
        success_url: Override redirect URL on success.
        failed_url: Override redirect URL on failure.
        user_id: Your application's user identifier.
        theme: Widget theme ("light", "dark", "auto").
        locale: Widget locale (e.g. "en", "de", "fr").
        metadata: Opaque string stored with the session.
    """

    callback_url: str
    min_age: int
    success_url: str
    failed_url: str
    user_id: str
    theme: str
    locale: str
    metadata: str


class _APIResponseData(TypedDict, total=False):
    """Internal: parsed API response envelope."""

    success: bool
    data: Optional[dict]  # type: ignore[type-arg]
    error: Optional[dict]  # type: ignore[type-arg]
    meta: Optional[dict]  # type: ignore[type-arg]

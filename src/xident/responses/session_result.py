"""Verification session result.

Contains the full session state including liveness, age, and OCR results.
Use the helper methods and properties to check the verification outcome.

Mirrors the PHP SDK's SessionResult exactly: same fields, same helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .._types import SessionStatus


@dataclass(frozen=True)
class SessionResult:
    """Verification session result.

    Contains the full session state including liveness, age, and OCR results.
    Use the helper methods to check the verification outcome.

    Attributes:
        id: Session UUID.
        status: Current session status.
        liveness_result: Liveness check outcome dict, or None.
        age_result: Age verification outcome dict, or None.
        ocr_result: Document OCR outcome dict, or None.
        face_match_result: Face matching outcome dict, or None.
        ocr_task_id: Async OCR task identifier, or None.
        country_code: ISO 3166-1 alpha-2 country code, or None.
        regime: Applied verification regime, or None.
        min_age: Required minimum age threshold, or None.
        external_user_id: Your application's user identifier, or None.
        required_methods: List of required verification methods, or None.
        remaining_attempts: Number of remaining retry attempts, or None.
        created_at: ISO 8601 timestamp of session creation.
        started_at: ISO 8601 timestamp of session start, or None.
        completed_at: ISO 8601 timestamp of session completion, or None.
        expires_at: ISO 8601 timestamp of session expiry, or None.
    """

    id: str
    status: SessionStatus
    liveness_result: dict[str, Any] | None = None
    age_result: dict[str, Any] | None = None
    ocr_result: dict[str, Any] | None = None
    face_match_result: dict[str, Any] | None = None
    ocr_task_id: str | None = None
    country_code: str | None = None
    regime: str | None = None
    min_age: int | None = None
    external_user_id: str | None = None
    required_methods: list[str] | None = field(default=None)
    remaining_attempts: int | None = None
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    expires_at: str | None = None

    def is_verified(self) -> bool:
        """Session completed successfully (age verification passed)."""
        return self.status == SessionStatus.COMPLETED

    def is_completed(self) -> bool:
        """Session completed (any outcome)."""
        return self.status == SessionStatus.COMPLETED

    def is_failed(self) -> bool:
        """Session failed verification."""
        return self.status == SessionStatus.FAILED

    def is_pending(self) -> bool:
        """Session is still in progress (pending or in_progress)."""
        return self.status in (SessionStatus.PENDING, SessionStatus.IN_PROGRESS)

    def is_terminal(self) -> bool:
        """Session has reached a terminal state (no more changes possible)."""
        return self.status.is_terminal

    def age_bracket(self) -> int | None:
        """The verified age bracket (12, 15, 18, 21, 25) or None if not yet determined."""
        if self.age_result is None:
            return None
        bracket = self.age_result.get("verified_bracket")
        if bracket is not None:
            return int(bracket)
        estimated = self.age_result.get("estimated_age")
        if estimated is not None:
            return int(estimated)
        return None

    def method(self) -> str | None:
        """How the age was verified (e.g. "ml_fast", "ocr", "self_declaration")."""
        if self.age_result is None:
            return None
        return self.age_result.get("method")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionResult:
        """Create a SessionResult from an API response data dict."""
        status_str = str(data.get("status", "pending"))
        try:
            status = SessionStatus(status_str)
        except ValueError:
            status = SessionStatus.PENDING

        min_age_raw = data.get("min_age")
        remaining_raw = data.get("remaining_attempts")

        # The /result DTO returns the session identifier as "token" (xtk_...),
        # not "id". Prefer "token"; fall back to "id" for backwards compatibility.
        return cls(
            id=str(data.get("token") or data.get("id", "")),
            status=status,
            liveness_result=data.get("liveness_result"),
            age_result=data.get("age_result"),
            ocr_result=data.get("ocr_result"),
            face_match_result=data.get("face_match_result"),
            ocr_task_id=data.get("ocr_task_id"),
            country_code=data.get("country_code"),
            regime=data.get("regime"),
            min_age=int(min_age_raw) if min_age_raw is not None else None,
            external_user_id=data.get("external_user_id"),
            required_methods=data.get("required_methods"),
            remaining_attempts=int(remaining_raw) if remaining_raw is not None else None,
            created_at=str(data.get("created_at", "")),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            expires_at=data.get("expires_at"),
        )

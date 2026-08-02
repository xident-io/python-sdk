"""Face 2FA response value objects.

Face 2FA is an asynchronous product: register/verify return a challenge to
poll, and the status endpoint reports the pass/fail outcome. The API never
returns confidence scores or biometric data -- only pass/fail plus a
failure-reason taxonomy.

Frozen dataclasses -- immutable after construction (value object semantics).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Challenge kinds returned in :attr:`Face2FAStatus.kind`.
FACE_2FA_KIND_ENROLL = "enroll"
FACE_2FA_KIND_VERIFY = "verify"

#: Challenge lifecycle states returned in :attr:`Face2FAStatus.status`.
FACE_2FA_STATUS_PROCESSING = "processing"
FACE_2FA_STATUS_COMPLETED = "completed"
FACE_2FA_STATUS_FAILED = "failed"
FACE_2FA_STATUS_EXPIRED = "expired"


@dataclass(frozen=True)
class Face2FAChallenge:
    """Result of submitting a face 2FA register or verify call.

    Processing is asynchronous -- poll ``client.face_2fa.get_status()``
    with :attr:`challenge_id` until the status is terminal.

    Attributes:
        challenge_id: Identifier to poll for the outcome.
        status: Initial challenge status (always "processing").
    """

    challenge_id: str
    status: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Face2FAChallenge:
        """Create a Face2FAChallenge from an API response data dict."""
        return cls(
            challenge_id=str(data.get("challenge_id", "")),
            status=str(data.get("status", "")),
        )


@dataclass(frozen=True)
class Face2FAStatus:
    """Outcome of a face 2FA challenge (register or verify).

    Attributes:
        challenge_id: The polled challenge identifier.
        kind: What was requested -- "enroll" or "verify".
        status: Lifecycle state: "processing", "completed", "failed"
            or "expired". Treat the set as open.
        passed: The verdict: True (passed), False (failed), or None while
            the challenge is still processing.
        failure_reason: Why the challenge failed, or None. Known values:
            ``invalid_image``, ``no_face_detected``, ``not_enrolled``,
            ``face_mismatch``, ``blacklist_match``, ``expired``,
            ``internal_error``. Treat the set as open -- always handle
            a default.
        expires_at: ISO 8601 timestamp after which the challenge expires.
        completed_at: ISO 8601 timestamp of completion, or None.
    """

    challenge_id: str
    kind: str
    status: str
    passed: bool | None = None
    failure_reason: str | None = None
    expires_at: str = ""
    completed_at: str | None = None

    def is_processing(self) -> bool:
        """Challenge is still being processed -- keep polling."""
        return self.status == FACE_2FA_STATUS_PROCESSING

    def is_passed(self) -> bool:
        """The verdict is a definite PASS. This is the check to gate on.

        False both for a failed challenge and for one still processing.
        """
        return self.passed is True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Face2FAStatus:
        """Create a Face2FAStatus from an API response data dict."""
        passed_raw = data.get("passed")
        return cls(
            challenge_id=str(data.get("challenge_id", "")),
            kind=str(data.get("kind", "")),
            status=str(data.get("status", "")),
            passed=bool(passed_raw) if passed_raw is not None else None,
            failure_reason=data.get("failure_reason"),
            expires_at=str(data.get("expires_at", "")),
            completed_at=data.get("completed_at"),
        )


@dataclass(frozen=True)
class Face2FAEnrollment:
    """Whether one of your users has a 2FA face enrolled.

    Attributes:
        enrolled: True if the user has an active face enrollment.
        enrolled_at: ISO 8601 timestamp of the (latest) enrollment, or None.
    """

    enrolled: bool
    enrolled_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Face2FAEnrollment:
        """Create a Face2FAEnrollment from an API response data dict."""
        return cls(
            enrolled=bool(data.get("enrolled", False)),
            enrolled_at=data.get("enrolled_at"),
        )

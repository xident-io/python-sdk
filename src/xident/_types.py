"""Type definitions for the Xident SDK.

Contains TypedDicts for API parameters and the SessionStatus enum.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, TypedDict

#: The value the pass verdict carried before July 2026.
#:
#: Kept only so an SDK pointed at a deployment older than that rename still
#: behaves -- an SDK outlives a rollout window, and gets aimed at self-hosted
#: and lagging installs long after our own migration finished.
_LEGACY_SUCCESS = "completed"


class SessionStatus(str, Enum):
    """Verification session states.

    The API uses ONE vocabulary for the outcome across every surface -- the
    result endpoint, the webhook payload and the browser callback's
    ``?status=`` query parameter all use these same words. Earlier versions of
    this SDK documented a spelling difference between the callback and the
    result endpoint; that is no longer true.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"

    #: The PASS verdict: the user met the age threshold and every required
    #: check passed.
    #:
    #: This is a verdict, not a lifecycle marker. A session that ran to the end
    #: of the flow but did not meet the threshold is ``FAILED``, not this.
    SUCCESS = "success"

    FAILED = "failed"
    CANCELED = "canceled"
    CLAIMED = "claimed"

    #: .. deprecated::
    #:     The API renamed this verdict from ``"completed"`` to ``"success"``
    #:     in July 2026, because "completed" described a lifecycle and was read
    #:     by at least one integrator as "the flow finished" regardless of the
    #:     age result. Use :attr:`SUCCESS`.
    #:
    #: Because this repeats SUCCESS's value, Python makes it an ALIAS rather
    #: than a distinct member: ``SessionStatus.COMPLETED is
    #: SessionStatus.SUCCESS``. So existing ``status == SessionStatus.COMPLETED``
    #: code keeps working AND keeps being correct. Had it kept the old literal
    #: it would still run and quietly report every verified user as unverified.
    #: Being an alias, it is also excluded from ``list(SessionStatus)``.
    COMPLETED = "success"

    @classmethod
    def _missing_(cls, value: object) -> SessionStatus | None:
        """Map a legacy wire value onto the current vocabulary.

        Python calls this when value lookup fails, so ``SessionStatus(raw)``
        handles a pre-rename deployment anywhere it is called -- including in
        user code we cannot see, which a helper in our own parser would miss.

        Returning ``None`` for anything else preserves the normal ``ValueError``
        so an unrecognised status is never silently turned into a verdict.
        """
        if value == _LEGACY_SUCCESS:
            return cls.SUCCESS
        return None

    @property
    def is_terminal(self) -> bool:
        """Whether the session has reached a terminal state (no more changes possible)."""
        return self in (
            SessionStatus.SUCCESS,
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
        verification_mode: Overrides the rule engine's choice of methods for
            this session: "auto" (default), "document" to force document +
            face match, or "facial" to force on-device age estimation.
            Composes with ``min_age`` rather than replacing it -- "document"
            with ``min_age`` 21 still enforces 21, it just insists the proof
            be a document.
        liveness_difficulty: Overrides the number of liveness actions the
            widget requires: "easy", "medium", or "hard".
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
    verification_mode: str
    liveness_difficulty: str


class _APIResponseData(TypedDict, total=False):
    """Internal: parsed API response envelope."""

    success: bool
    data: dict[str, Any] | None
    error: dict[str, Any] | None
    meta: dict[str, Any] | None

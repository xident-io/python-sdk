"""Verification session result.

Mirrors the v1 tenant result contract -- the frozen `data` shape of
`GET /result/{token}`: `token, status, verified, reason, verification_mode,
ip_country, external_user_id, checks{liveness, age, document, face_match},
created_at, completed_at, expires_at`. That contract is additive-only (see the golden
fixture `tests/testdata/tenant_result_v1.golden.json`, copied byte-for-byte
from the API repo), so `from_dict` stays as tolerant of unrecognised or
missing keys as it always was.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .._types import SessionStatus


@dataclass(frozen=True)
class LivenessCheck:
    """Outcome of the liveness check.

    Attributes:
        performed: Whether the check ran at all.
        passed: Whether it passed. Meaningless if ``performed`` is False.
    """

    performed: bool = False
    passed: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> LivenessCheck:
        data = data or {}
        return cls(
            performed=bool(data.get("performed", False)),
            passed=bool(data.get("passed", False)),
        )


@dataclass(frozen=True)
class AgeCheck:
    """Outcome of the age check.

    Attributes:
        performed: Whether the check ran at all.
        passed: Whether it passed. Meaningless if ``performed`` is False.
        gate: The age threshold (12, 15, 18, 21, 25) it was checked against,
            or None if not performed.
    """

    performed: bool = False
    passed: bool = False
    gate: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AgeCheck:
        data = data or {}
        gate_raw = data.get("gate")
        return cls(
            performed=bool(data.get("performed", False)),
            passed=bool(data.get("passed", False)),
            gate=int(gate_raw) if gate_raw is not None else None,
        )


@dataclass(frozen=True)
class DocumentCheck:
    """Outcome of the document verification check.

    Attributes:
        performed: Whether the check ran at all.
        passed: Whether it passed. Meaningless if ``performed`` is False.
        document_type: e.g. "passport", "drivers_license", or None.
        country: ISO 3166-1 alpha-2 issuing country, or None.
    """

    performed: bool = False
    passed: bool = False
    document_type: str | None = None
    country: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DocumentCheck:
        data = data or {}
        return cls(
            performed=bool(data.get("performed", False)),
            passed=bool(data.get("passed", False)),
            document_type=data.get("document_type"),
            country=data.get("country"),
        )


@dataclass(frozen=True)
class FaceMatchCheck:
    """Outcome of the face-match check (selfie vs. document photo).

    Attributes:
        performed: Whether the check ran at all.
        passed: Whether it passed. Meaningless if ``performed`` is False.
    """

    performed: bool = False
    passed: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FaceMatchCheck:
        data = data or {}
        return cls(
            performed=bool(data.get("performed", False)),
            passed=bool(data.get("passed", False)),
        )


@dataclass(frozen=True)
class Checks:
    """The four checks a verification session can run.

    Any check not required by the session's verification path reports
    ``performed=False`` rather than being omitted -- always safe to read
    every field without a None-check first.
    """

    liveness: LivenessCheck = field(default_factory=LivenessCheck)
    age: AgeCheck = field(default_factory=AgeCheck)
    document: DocumentCheck = field(default_factory=DocumentCheck)
    face_match: FaceMatchCheck = field(default_factory=FaceMatchCheck)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Checks:
        data = data or {}
        return cls(
            liveness=LivenessCheck.from_dict(data.get("liveness")),
            age=AgeCheck.from_dict(data.get("age")),
            document=DocumentCheck.from_dict(data.get("document")),
            face_match=FaceMatchCheck.from_dict(data.get("face_match")),
        )


@dataclass(frozen=True)
class SessionResult:
    """Verification session result -- the v1 tenant result contract.

    Attributes:
        token: The result token (``xtk_`` prefixed). Primary identifier; use
            this, not the deprecated :attr:`id` alias.
        status: Current session status.
        verified: The pass/fail verdict as a plain bool. Prefer
            :meth:`is_verified`, which reads ``status`` and is unaffected by
            this field also being present -- they always agree in practice, but
            ``status`` is the field every helper on this class is defined
            against.
        reason: Why a non-success terminal status came out that way; empty
            when ``status`` is SUCCESS. Known values: ``age_below_threshold``,
            ``dob_unreadable``, ``face_mismatch``, ``face_not_detected``,
            ``docverify_reject``, ``blacklist_match``. Treat the set as open --
            new reasons may be added, so always handle a default.
        verification_mode: Which PATH produced the verdict -- ``"full"``
            (document path: OCR and/or document-to-selfie face match),
            ``"age_check"`` (browser-only: liveness and/or age bracket, no
            document), ``"xident_id"`` (returning user reused a bracket on
            their Xident account) or ``"eu_wallet"``. Treat the set as open.
            NOT the ``verification_mode`` *request* parameter
            (``auto``/``document``/``facial``), which selects methods up
            front. See :meth:`method`.
        ip_country: ISO 3166-1 alpha-2 country the end user connected from,
            IP-derived, or None on sessions created before 2026-08-04 or
            where IP geolocation failed. Distinct from
            ``checks.document.country``, which is the document's issuing
            country -- the two can legitimately differ.
        external_user_id: Your application's user identifier, or None.
        checks: The four checks the session ran (liveness, age, document,
            face_match) -- see :class:`Checks`.
        created_at: ISO 8601 timestamp of session creation.
        completed_at: ISO 8601 timestamp of session completion, or None.
        expires_at: ISO 8601 timestamp of session expiry, or None.
    """

    token: str
    status: SessionStatus
    verified: bool = False
    reason: str = ""
    verification_mode: str | None = None
    ip_country: str | None = None
    external_user_id: str | None = None
    checks: Checks = field(default_factory=Checks)
    created_at: str = ""
    completed_at: str | None = None
    expires_at: str | None = None

    @property
    def id(self) -> str:
        """Deprecated alias of :attr:`token`.

        .. deprecated::
            The wire field was renamed from ``id`` to ``token`` when the
            tenant result contract was frozen at v1. Use :attr:`token`.
        """
        return self.token

    def is_verified(self) -> bool:
        """The user PASSED verification. This is the check to gate on.

        False for a session that ran all the way through the flow but did not
        meet the age threshold -- that session is FAILED with ``reason``
        ``age_below_threshold``.
        """
        return self.status == SessionStatus.SUCCESS

    def is_completed(self) -> bool:
        """Alias of :meth:`is_verified`.

        .. deprecated::
            The docstring used to claim "any outcome", which the code never
            did -- it has always returned the pass verdict only. For "reached
            any terminal state" use :meth:`is_terminal`.
        """
        return self.is_verified()

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
        """The verified age bracket (12, 15, 18, 21, 25), or None.

        None whenever the age check did not pass -- whether because it was
        never performed, or because it ran and failed. A ``gate`` value on a
        failed check describes what was tested against, not a verified fact,
        so it is never surfaced here.
        """
        if self.checks.age.passed:
            return self.checks.age.gate
        return None

    def method(self) -> str | None:
        """How the session was verified (e.g. "full", "document", "facial")."""
        return self.verification_mode

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionResult:
        """Create a SessionResult from an API response data dict.

        Tolerant of missing and unrecognised keys: an old-shaped payload (this
        SDK's pre-2.0.0 response, or a not-yet-migrated deployment) still
        parses without raising, so ``.get()`` is used throughout rather than
        direct indexing.
        """
        # SessionStatus._missing_ maps a legacy "completed" from a
        # pre-July-2026 deployment onto SUCCESS. An unrecognised value still
        # raises and falls back to PENDING, which is neither terminal nor
        # verified -- so a caller polling for an outcome keeps polling rather
        # than treating something it does not understand as a finished
        # verification.
        status_str = str(data.get("status", "pending"))
        try:
            status = SessionStatus(status_str)
        except ValueError:
            status = SessionStatus.PENDING

        # The v1 contract's primary identifier is "token" (xtk_...). "id" is
        # the pre-v1 field name -- kept as a fallback so an old fixture or a
        # lagging deployment still resolves an identifier.
        return cls(
            token=str(data.get("token") or data.get("id", "")),
            status=status,
            verified=bool(data.get("verified", False)),
            reason=str(data.get("reason", "")),
            verification_mode=data.get("verification_mode"),
            ip_country=data.get("ip_country"),
            external_user_id=data.get("external_user_id"),
            checks=Checks.from_dict(data.get("checks")),
            created_at=str(data.get("created_at", "")),
            completed_at=data.get("completed_at"),
            expires_at=data.get("expires_at"),
        )

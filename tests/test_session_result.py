"""Tests for the SessionResult response object.

SessionResult mirrors the v1 tenant result contract -- the frozen `data` shape
of `GET /result/{token}` (see `api/internal/domain/services/testdata/
tenant_result_v1.golden.json`, copied byte-for-byte into
`tests/testdata/tenant_result_v1.golden.json`). That contract is
additive-only, so this file also carries an old-payload tolerance test: a
pre-v1 verbose dict (the shape this SDK sent before 2.0.0) must still parse
without raising, and `is_verified()` must still be correct on it.
"""

import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

import xident
from xident._types import SessionStatus
from xident.responses.session_result import (
    AgeCheck,
    Checks,
    DocumentCheck,
    FaceMatchCheck,
    LivenessCheck,
    SessionResult,
)

GOLDEN_PATH = Path(__file__).parent / "testdata" / "tenant_result_v1.golden.json"


class TestPublicExports:
    """The typed checks classes are part of the public API, like SessionResult."""

    def test_checks_classes_importable_from_top_level(self) -> None:
        assert xident.Checks is Checks
        assert xident.LivenessCheck is LivenessCheck
        assert xident.AgeCheck is AgeCheck
        assert xident.DocumentCheck is DocumentCheck
        assert xident.FaceMatchCheck is FaceMatchCheck

    def test_checks_classes_in_dunder_all(self) -> None:
        for name in ("Checks", "LivenessCheck", "AgeCheck", "DocumentCheck", "FaceMatchCheck"):
            assert name in xident.__all__


def load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text())


class TestSessionStatus:
    def test_all_values(self) -> None:
        assert SessionStatus.PENDING.value == "pending"
        assert SessionStatus.IN_PROGRESS.value == "in_progress"
        assert SessionStatus.SUCCESS.value == "success"
        assert SessionStatus.FAILED.value == "failed"
        assert SessionStatus.CANCELED.value == "canceled"
        assert SessionStatus.CLAIMED.value == "claimed"

    def test_is_terminal_true(self) -> None:
        assert SessionStatus.SUCCESS.is_terminal is True
        assert SessionStatus.FAILED.is_terminal is True
        assert SessionStatus.CANCELED.is_terminal is True
        assert SessionStatus.CLAIMED.is_terminal is True

    def test_is_terminal_false(self) -> None:
        assert SessionStatus.PENDING.is_terminal is False
        assert SessionStatus.IN_PROGRESS.is_terminal is False

    def test_str_enum(self) -> None:
        """SessionStatus should be usable as a string."""
        assert str(SessionStatus.SUCCESS) == "SessionStatus.SUCCESS"
        assert SessionStatus.SUCCESS == "success"

    def test_from_string(self) -> None:
        assert SessionStatus("pending") == SessionStatus.PENDING
        assert SessionStatus("in_progress") == SessionStatus.IN_PROGRESS

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            SessionStatus("nonexistent")


class TestChecks:
    """The typed `checks` sub-objects: liveness, age, document, face_match."""

    def test_liveness_from_dict(self) -> None:
        check = LivenessCheck.from_dict({"performed": True, "passed": True})
        assert check.performed is True
        assert check.passed is True

    def test_liveness_from_none_defaults_not_performed(self) -> None:
        check = LivenessCheck.from_dict(None)
        assert check.performed is False
        assert check.passed is False

    def test_liveness_from_empty_dict(self) -> None:
        check = LivenessCheck.from_dict({})
        assert check.performed is False
        assert check.passed is False

    def test_age_from_dict(self) -> None:
        check = AgeCheck.from_dict({"performed": True, "passed": True, "gate": 21})
        assert check.performed is True
        assert check.passed is True
        assert check.gate == 21

    def test_age_gate_none_when_absent(self) -> None:
        check = AgeCheck.from_dict({"performed": True, "passed": False})
        assert check.gate is None

    def test_age_gate_int_coercion(self) -> None:
        check = AgeCheck.from_dict({"performed": True, "passed": True, "gate": "18"})
        assert check.gate == 18
        assert isinstance(check.gate, int)

    def test_age_from_none(self) -> None:
        check = AgeCheck.from_dict(None)
        assert check.performed is False
        assert check.passed is False
        assert check.gate is None

    def test_document_from_dict(self) -> None:
        check = DocumentCheck.from_dict(
            {
                "performed": True,
                "passed": True,
                "document_type": "passport",
                "country": "DE",
            }
        )
        assert check.performed is True
        assert check.passed is True
        assert check.document_type == "passport"
        assert check.country == "DE"

    def test_document_from_none(self) -> None:
        check = DocumentCheck.from_dict(None)
        assert check.performed is False
        assert check.passed is False
        assert check.document_type is None
        assert check.country is None

    def test_face_match_from_dict(self) -> None:
        check = FaceMatchCheck.from_dict({"performed": True, "passed": False})
        assert check.performed is True
        assert check.passed is False

    def test_face_match_from_none(self) -> None:
        check = FaceMatchCheck.from_dict(None)
        assert check.performed is False
        assert check.passed is False

    def test_checks_from_dict_full(self) -> None:
        checks = Checks.from_dict(
            {
                "liveness": {"performed": True, "passed": True},
                "age": {"performed": True, "passed": True, "gate": 21},
                "document": {
                    "performed": True,
                    "passed": True,
                    "document_type": "passport",
                    "country": "DE",
                },
                "face_match": {"performed": True, "passed": True},
            }
        )
        assert checks.liveness.passed is True
        assert checks.age.gate == 21
        assert checks.document.document_type == "passport"
        assert checks.face_match.passed is True

    def test_checks_from_none(self) -> None:
        checks = Checks.from_dict(None)
        assert checks.liveness.performed is False
        assert checks.age.performed is False
        assert checks.document.performed is False
        assert checks.face_match.performed is False

    def test_checks_from_empty_dict(self) -> None:
        checks = Checks.from_dict({})
        assert checks.liveness.performed is False
        assert checks.age.performed is False
        assert checks.document.performed is False
        assert checks.face_match.performed is False

    def test_checks_frozen(self) -> None:
        checks = Checks.from_dict(None)
        with pytest.raises(AttributeError):
            checks.liveness = LivenessCheck.from_dict(None)  # type: ignore[misc]


class TestSessionResultGolden:
    """The pinned v1 contract: `tests/testdata/tenant_result_v1.golden.json`."""

    def test_parses_golden_fixture(self) -> None:
        result = SessionResult.from_dict(load_golden())

        assert result.token == "xtk_golden0001"
        assert result.status == SessionStatus.SUCCESS
        assert result.verified is True
        assert result.reason == ""
        assert result.verification_mode == "full"
        assert result.ip_country == "DE"
        assert result.external_user_id == "cust-4711"
        assert result.created_at == "2026-08-03T10:00:00Z"
        assert result.completed_at == "2026-08-03T10:02:30Z"
        assert result.expires_at == "2026-08-03T10:15:00Z"

    def test_golden_checks_liveness(self) -> None:
        result = SessionResult.from_dict(load_golden())
        assert result.checks.liveness.performed is True
        assert result.checks.liveness.passed is True

    def test_golden_checks_age(self) -> None:
        result = SessionResult.from_dict(load_golden())
        assert result.checks.age.performed is True
        assert result.checks.age.passed is True
        assert result.checks.age.gate == 21

    def test_golden_checks_document(self) -> None:
        result = SessionResult.from_dict(load_golden())
        assert result.checks.document.performed is True
        assert result.checks.document.passed is True
        assert result.checks.document.document_type == "passport"
        assert result.checks.document.country == "DE"

    def test_golden_checks_face_match(self) -> None:
        result = SessionResult.from_dict(load_golden())
        assert result.checks.face_match.performed is True
        assert result.checks.face_match.passed is True

    def test_golden_is_verified(self) -> None:
        result = SessionResult.from_dict(load_golden())
        assert result.is_verified() is True

    def test_golden_age_bracket(self) -> None:
        result = SessionResult.from_dict(load_golden())
        assert result.age_bracket() == 21

    def test_golden_method(self) -> None:
        result = SessionResult.from_dict(load_golden())
        assert result.method() == "full"

    def test_golden_deprecated_id_alias(self) -> None:
        result = SessionResult.from_dict(load_golden())
        assert result.id == result.token == "xtk_golden0001"


class TestSessionResult:
    def test_from_dict_minimal(self) -> None:
        data = {"token": "xtk_min", "status": "pending"}
        result = SessionResult.from_dict(data)

        assert result.token == "xtk_min"
        assert result.status == SessionStatus.PENDING
        assert result.verified is False
        assert result.reason == ""
        assert result.verification_mode is None
        assert result.ip_country is None
        assert result.external_user_id is None
        assert result.completed_at is None
        assert result.expires_at is None
        assert result.checks.liveness.performed is False

    def test_from_dict_maps_token_as_primary(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_abc", "status": "success"})
        assert result.token == "xtk_abc"
        assert result.id == "xtk_abc"

    def test_from_dict_unknown_status_defaults_pending(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "unknown_status"})
        assert result.status == SessionStatus.PENDING

    def test_from_dict_missing_status_defaults_pending(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s"})
        assert result.status == SessionStatus.PENDING

    def test_from_dict_empty(self) -> None:
        result = SessionResult.from_dict({})
        assert result.token == ""
        assert result.status == SessionStatus.PENDING
        assert result.created_at == ""

    def test_is_verified(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "success"})
        assert result.is_verified() is True

    def test_is_verified_false(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "failed"})
        assert result.is_verified() is False

    def test_is_completed_deprecated_alias(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "success"})
        assert result.is_completed() is True

    def test_is_failed(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "failed"})
        assert result.is_failed() is True

    def test_is_pending_for_pending(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "pending"})
        assert result.is_pending() is True

    def test_is_pending_for_in_progress(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "in_progress"})
        assert result.is_pending() is True

    def test_is_pending_false_for_completed(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "success"})
        assert result.is_pending() is False

    def test_is_terminal(self) -> None:
        for status in ["success", "failed", "canceled", "claimed"]:
            result = SessionResult.from_dict({"token": "xtk_s", "status": status})
            assert result.is_terminal() is True, f"{status} should be terminal"

    def test_is_not_terminal(self) -> None:
        for status in ["pending", "in_progress"]:
            result = SessionResult.from_dict({"token": "xtk_s", "status": status})
            assert result.is_terminal() is False, f"{status} should not be terminal"

    def test_age_bracket_when_passed(self) -> None:
        result = SessionResult.from_dict(
            {
                "token": "xtk_s",
                "status": "success",
                "checks": {"age": {"performed": True, "passed": True, "gate": 21}},
            }
        )
        assert result.age_bracket() == 21

    def test_age_bracket_none_when_not_passed(self) -> None:
        """A gate value present but the check failed -- must not leak the gate."""
        result = SessionResult.from_dict(
            {
                "token": "xtk_s",
                "status": "failed",
                "checks": {"age": {"performed": True, "passed": False, "gate": 21}},
            }
        )
        assert result.age_bracket() is None

    def test_age_bracket_none_when_not_performed(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "pending"})
        assert result.age_bracket() is None

    def test_method_returns_verification_mode(self) -> None:
        result = SessionResult.from_dict(
            {"token": "xtk_s", "status": "success", "verification_mode": "document"}
        )
        assert result.method() == "document"

    def test_method_none_when_absent(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "pending"})
        assert result.method() is None

    def test_frozen_immutability(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_s", "status": "pending"})
        with pytest.raises(AttributeError):
            result.token = "changed"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            result.status = SessionStatus.COMPLETED  # type: ignore[misc]

    def test_id_is_read_only(self) -> None:
        """`.id` is a deprecated property, not a field -- it cannot be assigned."""
        result = SessionResult.from_dict({"token": "xtk_s", "status": "pending"})
        with pytest.raises(AttributeError):
            result.id = "changed"  # type: ignore[misc]

    def test_reason_carried_for_failure(self) -> None:
        result = SessionResult.from_dict(
            {"token": "xtk_s", "status": "failed", "reason": "age_below_threshold"}
        )
        assert result.reason == "age_below_threshold"

    def test_external_user_id(self) -> None:
        result = SessionResult.from_dict(
            {"token": "xtk_s", "status": "success", "external_user_id": "cust-1"}
        )
        assert result.external_user_id == "cust-1"


class TestOldPayloadTolerance:
    """The pre-2.0.0 verbose payload shape must still parse without raising.

    The v1 tenant result contract is additive-only, but this SDK's own
    request/response shape changed underneath it (blob fields -> typed
    `checks`). A caller who kept an old fixture around, or hit a
    not-yet-migrated deployment, must not get an exception -- and the one
    guarantee this SDK makes for that shape is that `is_verified()` still
    reflects `status` correctly.
    """

    OLD_PAYLOAD: ClassVar[dict[str, Any]] = {
        "id": "sess_legacy_123",
        "status": "success",
        "liveness_result": {"passed": True},
        "age_result": {"verified_bracket": 18, "method": "ml_fast"},
        "ocr_result": {"dob": "2000-01-01"},
        "face_match_result": {"score": 0.95},
        "ocr_task_id": "task_123",
        "country_code": "DE",
        "regime": "medium",
        "min_age": 18,
        "external_user_id": "user_42",
        "required_methods": ["liveness", "age"],
        "remaining_attempts": 2,
        "created_at": "2026-01-01T00:00:00Z",
        "started_at": "2026-01-01T00:00:01Z",
        "completed_at": "2026-01-01T00:00:05Z",
        "expires_at": "2026-01-01T00:10:00Z",
    }

    def test_old_payload_does_not_raise(self) -> None:
        SessionResult.from_dict(self.OLD_PAYLOAD)

    def test_old_payload_is_verified_still_correct(self) -> None:
        result = SessionResult.from_dict(self.OLD_PAYLOAD)
        assert result.is_verified() is True

    def test_old_payload_failed_is_verified_still_correct(self) -> None:
        payload = {**self.OLD_PAYLOAD, "status": "failed"}
        result = SessionResult.from_dict(payload)
        assert result.is_verified() is False

    def test_old_payload_id_falls_back_since_no_token(self) -> None:
        result = SessionResult.from_dict(self.OLD_PAYLOAD)
        assert result.token == "sess_legacy_123"
        assert result.id == "sess_legacy_123"

    def test_old_payload_external_user_id_still_read(self) -> None:
        result = SessionResult.from_dict(self.OLD_PAYLOAD)
        assert result.external_user_id == "user_42"

    def test_old_payload_no_checks_key_defaults_empty(self) -> None:
        """checks weren't sent under that name -- the typed checks are all not-performed."""
        result = SessionResult.from_dict(self.OLD_PAYLOAD)
        assert result.checks.age.performed is False
        assert result.age_bracket() is None

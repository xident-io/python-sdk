"""Tests for the SessionResult response object."""

import pytest

from xident._types import SessionStatus
from xident.responses.session_result import SessionResult


class TestSessionStatus:
    def test_all_values(self) -> None:
        assert SessionStatus.PENDING.value == "pending"
        assert SessionStatus.IN_PROGRESS.value == "in_progress"
        assert SessionStatus.COMPLETED.value == "completed"
        assert SessionStatus.FAILED.value == "failed"
        assert SessionStatus.CANCELED.value == "canceled"
        assert SessionStatus.CLAIMED.value == "claimed"

    def test_is_terminal_true(self) -> None:
        assert SessionStatus.COMPLETED.is_terminal is True
        assert SessionStatus.FAILED.is_terminal is True
        assert SessionStatus.CANCELED.is_terminal is True
        assert SessionStatus.CLAIMED.is_terminal is True

    def test_is_terminal_false(self) -> None:
        assert SessionStatus.PENDING.is_terminal is False
        assert SessionStatus.IN_PROGRESS.is_terminal is False

    def test_str_enum(self) -> None:
        """SessionStatus should be usable as a string."""
        assert str(SessionStatus.COMPLETED) == "SessionStatus.COMPLETED"
        assert SessionStatus.COMPLETED == "completed"

    def test_from_string(self) -> None:
        assert SessionStatus("pending") == SessionStatus.PENDING
        assert SessionStatus("in_progress") == SessionStatus.IN_PROGRESS

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            SessionStatus("nonexistent")


class TestSessionResult:
    def test_from_dict_full(self) -> None:
        data = {
            "id": "sess_abc",
            "status": "completed",
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
        result = SessionResult.from_dict(data)

        assert result.id == "sess_abc"
        assert result.status == SessionStatus.COMPLETED
        assert result.liveness_result == {"passed": True}
        assert result.age_result == {"verified_bracket": 18, "method": "ml_fast"}
        assert result.ocr_result == {"dob": "2000-01-01"}
        assert result.face_match_result == {"score": 0.95}
        assert result.ocr_task_id == "task_123"
        assert result.country_code == "DE"
        assert result.regime == "medium"
        assert result.min_age == 18
        assert result.external_user_id == "user_42"
        assert result.required_methods == ["liveness", "age"]
        assert result.remaining_attempts == 2
        assert result.created_at == "2026-01-01T00:00:00Z"
        assert result.started_at == "2026-01-01T00:00:01Z"
        assert result.completed_at == "2026-01-01T00:00:05Z"
        assert result.expires_at == "2026-01-01T00:10:00Z"

    def test_from_dict_minimal(self) -> None:
        data = {"id": "sess_min", "status": "pending"}
        result = SessionResult.from_dict(data)

        assert result.id == "sess_min"
        assert result.status == SessionStatus.PENDING
        assert result.liveness_result is None
        assert result.age_result is None
        assert result.ocr_result is None
        assert result.face_match_result is None
        assert result.min_age is None
        assert result.required_methods is None

    def test_from_dict_unknown_status_defaults_pending(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "unknown_status"})
        assert result.status == SessionStatus.PENDING

    def test_from_dict_missing_status_defaults_pending(self) -> None:
        result = SessionResult.from_dict({"id": "s"})
        assert result.status == SessionStatus.PENDING

    def test_from_dict_empty(self) -> None:
        result = SessionResult.from_dict({})
        assert result.id == ""
        assert result.status == SessionStatus.PENDING
        assert result.created_at == ""

    def test_is_verified(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "completed"})
        assert result.is_verified() is True

    def test_is_verified_false(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "failed"})
        assert result.is_verified() is False

    def test_is_completed(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "completed"})
        assert result.is_completed() is True

    def test_is_failed(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "failed"})
        assert result.is_failed() is True

    def test_is_pending_for_pending(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "pending"})
        assert result.is_pending() is True

    def test_is_pending_for_in_progress(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "in_progress"})
        assert result.is_pending() is True

    def test_is_pending_false_for_completed(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "completed"})
        assert result.is_pending() is False

    def test_is_terminal(self) -> None:
        for status in ["completed", "failed", "canceled", "claimed"]:
            result = SessionResult.from_dict({"id": "s", "status": status})
            assert result.is_terminal() is True, f"{status} should be terminal"

    def test_is_not_terminal(self) -> None:
        for status in ["pending", "in_progress"]:
            result = SessionResult.from_dict({"id": "s", "status": status})
            assert result.is_terminal() is False, f"{status} should not be terminal"

    def test_age_bracket_from_verified(self) -> None:
        result = SessionResult.from_dict(
            {"id": "s", "status": "completed", "age_result": {"verified_bracket": 21}}
        )
        assert result.age_bracket() == 21

    def test_age_bracket_from_estimated(self) -> None:
        result = SessionResult.from_dict(
            {"id": "s", "status": "completed", "age_result": {"estimated_age": 25}}
        )
        assert result.age_bracket() == 25

    def test_age_bracket_prefers_verified_over_estimated(self) -> None:
        result = SessionResult.from_dict(
            {
                "id": "s",
                "status": "completed",
                "age_result": {"verified_bracket": 18, "estimated_age": 25},
            }
        )
        assert result.age_bracket() == 18

    def test_age_bracket_none_when_no_age_result(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "pending"})
        assert result.age_bracket() is None

    def test_age_bracket_none_when_empty_age_result(self) -> None:
        result = SessionResult.from_dict(
            {"id": "s", "status": "completed", "age_result": {}}
        )
        assert result.age_bracket() is None

    def test_method(self) -> None:
        result = SessionResult.from_dict(
            {"id": "s", "status": "completed", "age_result": {"method": "ocr"}}
        )
        assert result.method() == "ocr"

    def test_method_none_when_no_age_result(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "pending"})
        assert result.method() is None

    def test_frozen_immutability(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "pending"})
        with pytest.raises(AttributeError):
            result.id = "changed"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            result.status = SessionStatus.COMPLETED  # type: ignore[misc]

    def test_min_age_int_coercion(self) -> None:
        result = SessionResult.from_dict({"id": "s", "status": "pending", "min_age": "18"})
        assert result.min_age == 18
        assert isinstance(result.min_age, int)

    def test_remaining_attempts_int_coercion(self) -> None:
        result = SessionResult.from_dict(
            {"id": "s", "status": "pending", "remaining_attempts": "3"}
        )
        assert result.remaining_attempts == 3
        assert isinstance(result.remaining_attempts, int)

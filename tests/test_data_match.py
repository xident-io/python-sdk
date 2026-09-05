"""checks.data_match is OPTIONAL on the wire (sent since 2026-09-05).

Two fixtures pin both states: the base golden has no ``data_match`` key and
must parse to ``None``; the data_match golden has it and must parse in full,
with nothing the API sends dropped on the way through.
"""

from __future__ import annotations

import json
from pathlib import Path

from xident.responses.session_result import DataMatchCheck, DataMatchFields, SessionResult

TESTDATA = Path(__file__).parent / "testdata"


def _load(name: str) -> dict:
    return json.loads((TESTDATA / name).read_text(encoding="utf-8"))


def test_data_match_absent_on_the_base_golden() -> None:
    result = SessionResult.from_dict(_load("tenant_result_v1.golden.json"))
    assert result.checks.data_match is None


def test_data_match_parsed_from_its_golden() -> None:
    result = SessionResult.from_dict(_load("tenant_result_v1_data_match.golden.json"))
    dm = result.checks.data_match
    assert isinstance(dm, DataMatchCheck)
    assert dm.performed is True
    assert dm.passed is False
    assert dm.fields == DataMatchFields(first_name="match", date_of_birth="mismatch")
    # The result is still a successful verification: report policy.
    assert result.verified is True


def test_data_match_unknown_outcome_is_none() -> None:
    dm = DataMatchCheck.from_dict({"performed": True, "passed": False, "fields": {"first_name": "maybe", "last_name": "match"}})
    assert dm is not None
    assert dm.fields.first_name is None
    assert dm.fields.last_name == "match"
    assert DataMatchCheck.from_dict(None) is None
    assert DataMatchCheck.from_dict("nope") is None  # type: ignore[arg-type]

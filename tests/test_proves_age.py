"""SessionResult.proves_age(): the age half of a callback's decision.

A callback must not accept a result just because it is a success. Two real
results are a success and still prove nothing about the age a site requires:

- an ID verification result, which carries no ``checks.age.gate`` (an ID
  session stores no minimum age, api#44): it proves an identity, not 21+;
- an age verification made for a LOWER age, such as an 18+ result replayed at
  a 21+ checkout.

``tests/testdata/tenant_result_v1.golden.json`` is the API's own golden file
(gate 21). ``tenant_result_v1_id_no_gate.json`` is the same result with
``checks.age.gate`` removed, which is how the API renders a passed ID
verification (``buildResultChecks`` in the API's
``internal/domain/services/session_result_view.go``: the age check is performed
and passed from the document date of birth, and the gate is the session's
``min_age``, 0, omitted).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from xident import SessionResult

TESTDATA = Path(__file__).parent / "testdata"


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((TESTDATA / name).read_text())
    return data


AGE_21 = "tenant_result_v1.golden.json"
ID_ONLY = "tenant_result_v1_id_no_gate.json"


class TestProvesAge:
    @pytest.mark.parametrize("min_age", [12, 15, 18, 19, 20, 21])
    def test_gate_21_proves_every_age_up_to_21(self, min_age: int) -> None:
        # 19 and 20 are enforced as band 21, so a gate-21 result proves them.
        assert SessionResult.from_dict(load(AGE_21)).proves_age(min_age) is True

    @pytest.mark.parametrize("min_age", [22, 25])
    def test_gate_21_does_not_prove_a_higher_age(self, min_age: int) -> None:
        assert SessionResult.from_dict(load(AGE_21)).proves_age(min_age) is False

    def test_an_18_result_replayed_at_a_21_checkout_is_refused(self) -> None:
        data = load(AGE_21)
        data["checks"]["age"]["gate"] = 18
        result = SessionResult.from_dict(data)
        assert result.is_verified()  # a real success...
        assert result.proves_age(21) is False  # ...that does not prove 21

    @pytest.mark.parametrize("min_age", [12, 18, 25])
    def test_an_id_verification_proves_no_age(self, min_age: int) -> None:
        result = SessionResult.from_dict(load(ID_ONLY))
        assert result.is_verified()
        assert result.checks.age.passed  # passed from the document date of birth
        assert result.checks.age.gate is None
        assert result.proves_age(min_age) is False

    def test_a_failed_session_proves_nothing(self) -> None:
        data = load(AGE_21)
        data["status"] = "failed"
        data["verified"] = False
        assert SessionResult.from_dict(data).proves_age(18) is False

    def test_a_failed_age_check_proves_nothing(self) -> None:
        data = load(AGE_21)
        data["checks"]["age"]["passed"] = False
        assert SessionResult.from_dict(data).proves_age(18) is False

    def test_an_old_result_without_checks_proves_nothing(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_old", "status": "success"})
        assert result.proves_age(18) is False

    @pytest.mark.parametrize("min_age", [0, 11, 26, 99, -1, True, 18.0, "18", None])
    def test_a_required_age_outside_12_to_25_is_a_programming_error(self, min_age: Any) -> None:
        # 26 could never be proven (the top band is 25), so it would silently
        # refuse everyone; 0 would make the check meaningless. Both are bugs
        # in the caller, so they raise instead of returning False.
        result = SessionResult.from_dict(load(AGE_21))
        with pytest.raises(ValueError, match="12 to 25"):
            result.proves_age(min_age)

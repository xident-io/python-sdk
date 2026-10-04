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

``tenant_result_v1_xident_id_reuse.json`` is a passed Xident ID reuse (a
returning user's age, proven earlier on their account, answers the session).
It is built from the API code of api#45 at c2d6890: ``account_reuse.go``
completes the session with kind ``xident_id`` and reason ``xident_id_reused``
and records no evidence, so ``buildResultChecks`` reports every check
``performed: false, passed: false`` and the age gate is the session's
``min_age`` (21). It must prove the age: ``checks.age.passed`` is not part of
the rule.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

import pytest

from xident import SessionResult
from xident.resources.webhooks import Webhooks

TESTDATA = Path(__file__).parent / "testdata"


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((TESTDATA / name).read_text())
    return data


AGE_21 = "tenant_result_v1.golden.json"
ID_ONLY = "tenant_result_v1_id_no_gate.json"
REUSE_21 = "tenant_result_v1_xident_id_reuse.json"


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

    @pytest.mark.parametrize("min_age", [18, 21])
    def test_an_xident_id_reuse_proves_its_gate(self, min_age: int) -> None:
        result = SessionResult.from_dict(load(REUSE_21))
        assert result.verification_type == "xident_id"
        assert result.checks.age.performed is False  # no new evidence...
        assert result.checks.age.passed is False
        assert result.proves_age(min_age) is True  # ...and still a proven 21+

    def test_an_xident_id_reuse_does_not_prove_a_higher_age(self) -> None:
        assert SessionResult.from_dict(load(REUSE_21)).proves_age(25) is False

    def test_the_document_golden_proves_18_and_21_but_not_25(self) -> None:
        result = SessionResult.from_dict(load(AGE_21))
        assert result.proves_age(18) is True
        assert result.proves_age(21) is True
        assert result.proves_age(25) is False

    def test_verified_false_proves_nothing_even_with_a_gate(self) -> None:
        # The rule reads the wire field ``verified``, not only the status.
        data = load(REUSE_21)
        data["verified"] = False
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


class TestProvesAgeFromWebhook:
    """The same rule applied to a webhook: ``data`` is the same tenant result.

    The envelope is the API's ``models.WebhookEventPayload`` (id, type,
    api_version, created, data), signed the way the API signs it.
    """

    @pytest.mark.parametrize(
        ("fixture", "expected"),
        [(AGE_21, True), (REUSE_21, True), (ID_ONLY, False)],
    )
    def test_a_signed_session_success_webhook(self, fixture: str, expected: bool) -> None:
        envelope = {
            "id": "evt_0001",
            "type": "session.success",
            "api_version": "2026-08-13",
            "created": 1785751350,
            "data": load(fixture),
        }
        payload = json.dumps(envelope)
        ts = int(time.time())
        sig = hmac.new(b"whsec_test", f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()

        event = Webhooks().construct_event(payload, f"t={ts},v1={sig}", "whsec_test")
        result = SessionResult.from_dict(event["data"])

        assert result.external_user_id == "cust-4711"
        assert result.proves_age(21) is expected

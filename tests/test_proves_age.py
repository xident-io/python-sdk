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

``tenant_result_v1_eu_wallet.json`` is a passed EU Digital Identity Wallet
presentation and ``tenant_result_v1_test_mode.json`` a test key's settle, both
built from ``TenantResultView`` at api c2d6890: the wallet path stores only
the wallet result (reason ``all_methods_verified``, ``checks.eu_wallet``
passed, ``checks.age`` not performed, gate 21); the test settle
(``settleTestSession``, reason ``test_mode``, every check not performed, gate
21) carries ``"test": true``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

import pytest

import xident
from xident import SessionResult
from xident.resources.webhooks import Webhooks

from .conftest import AsyncMockTransport, MockTransport

TESTDATA = Path(__file__).parent / "testdata"


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((TESTDATA / name).read_text())
    return data


AGE_21 = "tenant_result_v1.golden.json"
ID_ONLY = "tenant_result_v1_id_no_gate.json"
REUSE_21 = "tenant_result_v1_xident_id_reuse.json"
WALLET_21 = "tenant_result_v1_eu_wallet.json"
TEST_MODE_21 = "tenant_result_v1_test_mode.json"


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


def as_test_key(fixture: str) -> dict[str, Any]:
    """The fixture as a test key's session returns it: ``"test": true`` added.

    A test key settles the session at once with no real check (the API's
    ``settleTestSession``), yet the result is verified and carries the gate.
    """
    data = load(fixture)
    data["test"] = True
    return data


class TestTestKeyResults:
    """Round 2 addendum: a test-key verdict proves nothing unless opted in.

    The security scan flagged that, once ``checks.age.passed`` left the rule,
    a verified test-key result with a gate counted as proof of age.
    """

    def test_the_test_field_is_read(self) -> None:
        assert SessionResult.from_dict(as_test_key(AGE_21)).test is True
        assert SessionResult.from_dict(load(AGE_21)).test is False  # absent on live sessions
        assert SessionResult.from_dict({**load(AGE_21), "test": "true"}).test is False

    @pytest.mark.parametrize("min_age", [18, 21])
    def test_a_test_mode_gate_21_result_is_refused_by_default(self, min_age: int) -> None:
        result = SessionResult.from_dict(as_test_key(AGE_21))
        assert result.verified is True
        assert result.proves_age(min_age) is False

    @pytest.mark.parametrize("min_age", [18, 21])
    def test_a_test_mode_result_is_accepted_only_with_the_opt_in(self, min_age: int) -> None:
        result = SessionResult.from_dict(as_test_key(AGE_21))
        assert result.proves_age(min_age, allow_test=True) is True
        assert result.proves_age(25, allow_test=True) is False  # the gate still applies

    def test_a_live_reuse_result_is_accepted_without_the_opt_in(self) -> None:
        assert SessionResult.from_dict(load(REUSE_21)).proves_age(21) is True

    @pytest.mark.parametrize("data", [load(ID_ONLY), as_test_key(ID_ONLY)])
    def test_an_id_only_result_is_refused_even_with_the_opt_in(self, data: dict[str, Any]) -> None:
        assert SessionResult.from_dict(data).proves_age(12, allow_test=True) is False

    def test_through_the_sync_client(self, mock_transport: MockTransport) -> None:
        mock_transport.queue_success(as_test_key(AGE_21))
        mock_transport.queue_success(load(REUSE_21))
        client = xident.Xident(api_key="sk_test_123", transport=mock_transport)

        test_result = client.verification.get_result("xtk_golden0001")
        live_result = client.verification.get_result("xtk_golden0003")

        assert test_result.proves_age(21) is False
        assert test_result.proves_age(21, allow_test=True) is True
        assert live_result.proves_age(21) is True

    @pytest.mark.asyncio
    async def test_through_the_async_client(self) -> None:
        transport = AsyncMockTransport()
        transport.queue_success(as_test_key(AGE_21))
        transport.queue_success(load(REUSE_21))
        client = xident.AsyncXident(api_key="sk_test_123", transport=transport)

        test_result = await client.verification.get_result("xtk_golden0001")
        live_result = await client.verification.get_result("xtk_golden0003")

        assert test_result.proves_age(21) is False
        assert test_result.proves_age(21, allow_test=True) is True
        assert live_result.proves_age(21) is True


class TestFiveShapes:
    """Every result shape the API produces today, against one rule."""

    @pytest.mark.parametrize(
        ("fixture", "min_age", "expected"),
        [
            (AGE_21, 18, True), (AGE_21, 21, True), (AGE_21, 25, False),
            (ID_ONLY, 12, False), (ID_ONLY, 18, False), (ID_ONLY, 25, False),
            (REUSE_21, 18, True), (REUSE_21, 21, True), (REUSE_21, 25, False),
            (WALLET_21, 18, True), (WALLET_21, 21, True), (WALLET_21, 25, False),
            (TEST_MODE_21, 18, False), (TEST_MODE_21, 21, False), (TEST_MODE_21, 25, False),
        ],
    )
    def test_the_rule(self, fixture: str, min_age: int, expected: bool) -> None:
        assert SessionResult.from_dict(load(fixture)).proves_age(min_age) is expected

    @pytest.mark.parametrize(("min_age", "expected"), [(18, True), (21, True), (25, False)])
    def test_the_test_settle_with_the_opt_in(self, min_age: int, expected: bool) -> None:
        result = SessionResult.from_dict(load(TEST_MODE_21))
        assert result.test is True
        assert result.proves_age(min_age, allow_test=True) is expected

    @pytest.mark.parametrize(
        ("fixture", "expected"),
        [
            (AGE_21, True),
            (ID_ONLY, False),
            (REUSE_21, True),
            (WALLET_21, True),
            (TEST_MODE_21, False),
        ],
    )
    def test_through_a_signed_webhook(self, fixture: str, expected: bool) -> None:
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

        assert SessionResult.from_dict(event["data"]).proves_age(21) is expected


class TestAgeBracketFollowsProvesAge:
    """age_bracket() uses the proves_age rule, so the two never disagree.

    Mutations caught: requiring checks.age.passed (the reuse and wallet rows
    fail); dropping the verified check; dropping the test-key check; letting
    a gate of 0 through.
    """

    @pytest.mark.parametrize(
        ("name", "want", "want_allow_test"),
        [
            (AGE_21, 21, 21),
            (REUSE_21, 21, 21),
            (WALLET_21, 21, 21),
            (ID_ONLY, None, None),
            (TEST_MODE_21, None, 21),
        ],
    )
    def test_the_five_shapes(
        self, name: str, want: int | None, want_allow_test: int | None
    ) -> None:
        result = SessionResult.from_dict(load(name))
        assert result.age_bracket() == want
        assert result.age_bracket(allow_test=True) == want_allow_test
        for age in (12, 15, 18, 21, 25):
            bracket = result.age_bracket()
            assert result.proves_age(age) is (bracket is not None and bracket >= age)
            bracket_t = result.age_bracket(allow_test=True)
            proven_t = bracket_t is not None and bracket_t >= age
            assert result.proves_age(age, allow_test=True) is proven_t

    def test_a_failed_session_has_no_band(self) -> None:
        data = load(AGE_21)
        data["status"] = "failed"
        data["verified"] = False
        assert SessionResult.from_dict(data).age_bracket() is None

    def test_a_zero_gate_is_no_band(self) -> None:
        data = load(REUSE_21)
        data["checks"]["age"]["gate"] = 0
        assert SessionResult.from_dict(data).age_bracket() is None

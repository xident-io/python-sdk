"""Every field the API sends must have somewhere to land.

The test this SDK needed and did not have.

``tests/testdata/tenant_result_v1.golden.json`` is a copy of the API's own
frozen fixture, and every SDK's test suite claimed it was a byte-for-byte copy.
For a week it was not: the API's was 836 bytes and all four SDK copies were 659,
missing ``risk``, ``checks.eu_wallet`` and ``checks.aml``. Nothing caught it,
because:

* ``from_dict`` ignores unrecognised keys on purpose, so that an additive API
  change never raises in a customer's process -- that behaviour is correct and
  is not what we are fixing; and
* the existing tests parse the fixture and assert individual attributes, so a
  field that neither the fixture nor the dataclass contained was invisible.

The fixture and the dataclasses agreed with each other perfectly while both
disagreed with the API. A test that only reads the fixture therefore cannot
catch this class of drift. This one walks the fixture and asserts that every
wire key has a field to land in.
"""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from xident.responses.session_result import SessionResult

GOLDEN = Path(__file__).parent / "testdata" / "tenant_result_v1.golden.json"


@pytest.fixture()
def golden() -> dict[str, Any]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _dropped(data: dict[str, Any], obj: Any, prefix: str = "") -> list[str]:
    """Return every wire key path that has no corresponding field on obj.

    Recurses into nested dataclasses so ``checks.aml`` and ``risk.band`` are
    covered, not just the top level -- the original drift was two levels deep.
    """
    missing: list[str] = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        names = {f.name for f in fields(obj)} if is_dataclass(obj) else set()
        if key not in names:
            missing.append(path)
            continue
        child = getattr(obj, key, None)
        if isinstance(value, dict) and is_dataclass(child):
            missing.extend(_dropped(value, child, path))
    return sorted(missing)


def test_no_wire_field_is_dropped(golden: dict[str, Any]) -> None:
    result = SessionResult.from_dict(golden)
    dropped = _dropped(golden, result)
    assert not dropped, (
        "SessionResult has no field for these keys, so the API sends them and "
        f"this SDK discards them: {dropped}. Add the fields; do not trim the fixture."
    )


def test_golden_carries_every_documented_check(golden: dict[str, Any]) -> None:
    """The fixture must stay in step with the API's copy.

    Asserts the field set we expect it to carry, so a future sync that silently
    trims it fails here rather than in a customer's integration.
    """
    for name in ("liveness", "age", "document", "face_match", "eu_wallet", "aml"):
        assert name in golden["checks"], (
            f"golden fixture is missing checks.{name} -- it is out of sync with "
            "the API's testdata/tenant_result_v1.golden.json"
        )
    assert "risk" in golden, "golden fixture is missing the risk object"


def test_the_recovered_fields_are_actually_readable(golden: dict[str, Any]) -> None:
    """A field that parses but cannot be reached is only half-shipped."""
    result = SessionResult.from_dict(golden)

    assert result.risk is not None, "risk is None after parsing a fixture that sets it"
    assert result.risk.band == golden["risk"]["band"]

    # eu_wallet and aml are both performed=False in the fixture, so asserting on
    # `passed` would prove nothing. What matters is that the attributes exist and
    # carry the wire values -- the drop test above proves the keys were consumed.
    assert result.checks.eu_wallet.performed == golden["checks"]["eu_wallet"]["performed"]
    assert result.checks.aml.performed == golden["checks"]["aml"]["performed"]


def test_absent_risk_stays_none() -> None:
    """Absent must not become a Risk with an empty band.

    ``risk`` is omitempty on the wire, so absent means "no risk signals" -- which
    is materially different from a band of "". Callers branch on ``is None``, so
    collapsing the two would silently change their control flow.
    """
    result = SessionResult.from_dict({"token": "xtk_x", "status": "success"})
    assert result.risk is None

    # An explicitly empty object is also absent, not a band of "".
    assert SessionResult.from_dict({"token": "xtk_x", "status": "success", "risk": {}}).risk is None

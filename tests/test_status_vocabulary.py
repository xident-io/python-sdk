"""Guard the session-status vocabulary against the API contract.

The API renamed the pass verdict from "completed" to "success" and dropped the
British "cancelled" from the browser callback. This SDK kept the old
vocabulary and so reported every verified user as unverified.

The api repo has a guard for this, but it walks only the api module and is
structurally incapable of seeing a sibling repo -- which is exactly how all
seven SDKs missed the rename. There is no CI spanning the eight repos, so each
one needs its own copy.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from xident._types import SessionStatus
from xident.responses.session_result import SessionResult

#: The value the pass verdict carried before July 2026.
LEGACY_SUCCESS = "completed"

ROOT = Path(__file__).resolve().parent.parent
# examples/ is shipped documentation -- an integrator copies it verbatim, so a
# stale comparison there is as harmful as one in the library.
SOURCE_DIRS = [ROOT / "src", ROOT / "examples"]


def _source_files() -> list[Path]:
    files: list[Path] = []
    for directory in SOURCE_DIRS:
        if directory.is_dir():
            files.extend(
                p for p in directory.rglob("*.py") if "__pycache__" not in p.parts
            )
    return files


class TestWireValues:
    def test_current_vocabulary(self) -> None:
        # These strings are the API contract. Changing one here without
        # changing the API is how an SDK stops recognising a real verdict.
        assert SessionStatus.PENDING.value == "pending"
        assert SessionStatus.IN_PROGRESS.value == "in_progress"
        assert SessionStatus.SUCCESS.value == "success"
        assert SessionStatus.FAILED.value == "failed"
        assert SessionStatus.CANCELED.value == "canceled"
        assert SessionStatus.CLAIMED.value == "claimed"

    def test_retired_literal_is_not_a_member_value(self) -> None:
        assert LEGACY_SUCCESS not in {m.value for m in SessionStatus}


class TestDeprecatedAlias:
    def test_completed_is_the_success_member(self) -> None:
        """The alias must resolve to the CURRENT member.

        Existing consumer code comparing against it has to keep being correct,
        not merely keep running. Python makes a same-valued member an alias
        automatically, so this is identity, not equality.
        """
        assert SessionStatus.COMPLETED is SessionStatus.SUCCESS

    def test_alias_is_excluded_from_iteration(self) -> None:
        assert [m.name for m in SessionStatus] == [
            "PENDING",
            "IN_PROGRESS",
            "SUCCESS",
            "FAILED",
            "CANCELED",
            "CLAIMED",
        ]

    def test_pre_rename_consumer_comparison_still_matches(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_a", "status": "success"})
        assert result.status == SessionStatus.COMPLETED


class TestLegacyNormalisation:
    def test_value_lookup_maps_legacy_forward(self) -> None:
        """A deployment older than the rename still sends "completed".

        _missing_ handles it at the enum, so user code doing its own
        ``SessionStatus(raw)`` lookup is covered too -- not just our parser.
        """
        assert SessionStatus(LEGACY_SUCCESS) is SessionStatus.SUCCESS

    def test_unknown_value_still_raises(self) -> None:
        with pytest.raises(ValueError):
            SessionStatus("quarantined")

    def test_legacy_status_normalises_through_session_result(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_a", "status": LEGACY_SUCCESS})
        assert result.status is SessionStatus.SUCCESS
        assert result.is_verified() is True
        assert result.is_terminal() is True
        assert result.is_pending() is False

    def test_unknown_status_is_neither_verified_nor_terminal(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_a", "status": "quarantined"})
        assert result.is_verified() is False
        assert result.is_terminal() is False


class TestReason:
    def test_reason_is_carried_for_non_success_terminal_status(self) -> None:
        result = SessionResult.from_dict(
            {"token": "xtk_a", "status": "failed", "reason": "age_below_threshold"}
        )
        assert result.is_verified() is False
        assert result.reason == "age_below_threshold"

    def test_reason_defaults_to_empty(self) -> None:
        result = SessionResult.from_dict({"token": "xtk_a", "status": "success"})
        assert result.reason == ""


class TestNoStaleVocabularyInSource:
    def test_scans_a_non_zero_number_of_files(self) -> None:
        assert _source_files(), "scanned no files -- the guard would pass vacuously"

    def test_never_uses_the_british_spelling(self) -> None:
        # The British spelling is gone from every surface including the
        # callback, so it is stale in prose as well as in code.
        offenders = [
            str(p.relative_to(ROOT))
            for p in _source_files()
            if "cancelled" in p.read_text()
        ]
        assert offenders == [], 'the API uses "canceled" on every surface'

    def test_never_hardcodes_the_retired_literal(self) -> None:
        offenders = []
        for path in _source_files():
            source = path.read_text()
            # Strip docstrings and comments: a docstring may legitimately
            # explain the rename, and the constant naming the legacy wire
            # value is the one place the literal belongs.
            code = re.sub(r'"""[\s\S]*?"""', "", source)
            code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)
            code = re.sub(r'_LEGACY_SUCCESS = "[^"]*"', "", code)
            # The face-2FA CHALLENGE lifecycle legitimately uses "completed"
            # on the wire -- there it is a lifecycle state, not a verdict
            # (the verdict is the separate `passed` field), which is exactly
            # the design the session rename moved toward. The named constant
            # is the one place that literal belongs.
            code = re.sub(r'FACE_2FA_STATUS_COMPLETED = "[^"]*"', "", code)
            if re.search(r"""['"]completed['"]""", code):
                offenders.append(str(path.relative_to(ROOT)))
        assert offenders == [], 'the pass verdict is "success"'

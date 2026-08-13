"""Every request must carry the dated API version this SDK was built against.

Pinning in the SDK rather than relying on the project's dashboard setting is what
guarantees this release's response types match the payload the server sends: a
customer pinned to an older version still receives the shape these dataclasses
parse. Without the header, a newer SDK reading an older shape would silently leave
fields empty -- the same failure class as the three fields this SDK dropped for a
week in August.
"""

from __future__ import annotations

import re

from xident._config import API_VERSION, PINNED_API_VERSION, SDK_VERSION, Config


def test_defaults_to_the_pinned_version() -> None:
    assert Config(api_key="sk_test_x").api_version == PINNED_API_VERSION


def test_can_be_overridden_to_trial_a_newer_version() -> None:
    assert Config(api_key="sk_test_x", api_version="2027-01-01").api_version == "2027-01-01"


def test_pinned_version_is_a_date() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", PINNED_API_VERSION)


def test_pinned_version_is_not_the_path_prefix_or_the_sdk_version() -> None:
    # API_VERSION is the URL path segment ("verify/v1"). Naming these alike is how
    # the verification_mode / verification_type confusion started.
    assert PINNED_API_VERSION != API_VERSION
    # And it must not track the SDK version: they move on different clocks, and an
    # SDK patch release must never change which API shape a customer receives.
    assert PINNED_API_VERSION != SDK_VERSION


def test_the_header_is_sent_on_both_the_sync_and_async_clients() -> None:
    """Both header dicts must carry it.

    The sync and async HTTP clients build their headers separately, so adding the
    version to only one is the obvious way to half-ship this.
    """
    from pathlib import Path

    source = Path(__file__).parent.parent / "src" / "xident" / "_http_client.py"
    occurrences = source.read_text(encoding="utf-8").count('"X-API-Version"')
    assert occurrences == 2, (
        f"expected X-API-Version in both the sync and async header dicts, found "
        f"{occurrences} occurrence(s)"
    )

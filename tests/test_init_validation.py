"""Local validation of verification.init() (sync and async).

From the 2026-10 release the API takes every setting of a session from the
init token, so it refuses an init it cannot enforce: no ``user_id``
(``MISSING_USER_ID``), a ``min_age`` outside 12 to 25 for an age verification
or any ``min_age`` for an ID verification (``INVALID_MIN_AGE``), and an ID
verification with ``verification_mode="facial"`` (``INVALID_VERIFICATION_MODE``).
The SDK refuses the same settings before any request, with the API's codes and
messages, and sends a valid ``min_age`` exactly as given: the rounding up to
the band (19 enforced as 21) happens only in the API.

Every refusal test asserts that no request reached the transport. Without that
assertion a test would still pass if the SDK sent the request first and only
then raised.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

import xident

from .conftest import AsyncMockTransport, MockTransport

API_MIN_AGE_MESSAGE = (
    "min_age must be between 12 and 25; it is rounded up to the next of 12, 15, 18, "
    "21 or 25 (19 is enforced as 21). An id_verification takes no min_age."
)
API_MISSING_USER_ID_MESSAGE = (
    "user_id is required: pass your own identifier for the person being verified"
)
API_INVALID_PURPOSE_MESSAGE = "purpose must be 'age_verification' or 'id_verification'"
API_ID_FACIAL_MESSAGE = (
    "verification_mode facial cannot be combined with purpose id_verification, "
    "which always requires a document"
)

MODES = ["sync", "async"]
INIT_PATH = "/verify/v1/init"


def _init(mode: str, **kwargs: Any) -> tuple[int, dict[str, Any] | None]:
    """Run verification.init on a sync or async client with a mock transport.

    Returns the number of requests the transport saw and the JSON body of the
    last one (None when no request was sent). Exceptions propagate.
    """
    if mode == "sync":
        transport = MockTransport()
        transport.queue_success({"token": "xit_v", "verify_url": "https://v.io?t=xit_v"})
        client = xident.Xident(api_key="sk_test_123", transport=transport)
        try:
            client.verification.init(**kwargs)
        finally:
            sent = transport.request_count
            last = transport.last_request
    else:
        async_transport = AsyncMockTransport()
        async_transport.queue_success({"token": "xit_v", "verify_url": "https://v.io?t=xit_v"})
        async_client = xident.AsyncXident(api_key="sk_test_123", transport=async_transport)
        try:
            asyncio.run(async_client.verification.init(**kwargs))
        finally:
            sent = async_transport.request_count
            last = async_transport.last_request
    if last is not None:
        # Every request init sends goes to POST /verify/v1/init. Checked here so
        # that every passing case also fails if the path or method changes.
        assert last.method == "POST"
        assert last.url.path == INIT_PATH
    body = json.loads(last.content) if last is not None else None
    return sent, body


def _refused(mode: str, code: str, message: str, **kwargs: Any) -> None:
    """Assert init raises the API's ValidationError and sends nothing."""
    if mode == "sync":
        transport = MockTransport()
        client = xident.Xident(api_key="sk_test_123", transport=transport)
        with pytest.raises(xident.ValidationError) as excinfo:
            client.verification.init(**kwargs)
        sent = transport.request_count
    else:
        async_transport = AsyncMockTransport()
        async_client = xident.AsyncXident(api_key="sk_test_123", transport=async_transport)
        with pytest.raises(xident.ValidationError) as excinfo:
            asyncio.run(async_client.verification.init(**kwargs))
        sent = async_transport.request_count

    err = excinfo.value
    assert err.error_code == code
    assert err.message == message
    assert err.status_code == 400
    assert err.request_id is None  # no request was made
    assert sent == 0


CB = "https://example.com/cb"


@pytest.mark.parametrize("mode", MODES)
class TestUserIdRequired:
    def test_missing_argument_is_a_type_error_and_sends_nothing(self, mode: str) -> None:
        # user_id is a required keyword argument, so leaving it out is
        # Python's own "missing argument" error, raised before the SDK runs.
        with pytest.raises(TypeError, match="user_id"):
            _init(mode, callback_url=CB, min_age=18)

    @pytest.mark.parametrize("user_id", [None, "", "   ", "\t\n"])
    def test_empty_user_id_is_refused(self, mode: str, user_id: str | None) -> None:
        _refused(
            mode,
            "MISSING_USER_ID",
            API_MISSING_USER_ID_MESSAGE,
            callback_url=CB,
            user_id=user_id,
            min_age=18,
        )

    def test_user_id_is_sent_exactly_as_given(self, mode: str) -> None:
        # The API stores user_id as sent and echoes it back; the SDK must not
        # trim it either, or the echoed value would not match the caller's.
        sent, body = _init(mode, callback_url=CB, user_id=" user 42 ", min_age=18)
        assert sent == 1
        assert body is not None
        assert body["user_id"] == " user 42 "


@pytest.mark.parametrize("mode", MODES)
class TestAgeVerificationMinAge:
    @pytest.mark.parametrize("min_age", [None, 0, 11, 26, 99, -1, True, 18.0, "18"])
    def test_out_of_range_or_missing_is_refused(self, mode: str, min_age: Any) -> None:
        _refused(
            mode,
            "INVALID_MIN_AGE",
            API_MIN_AGE_MESSAGE,
            callback_url=CB,
            user_id="user_42",
            min_age=min_age,
        )

    def test_explicit_age_purpose_without_min_age_is_refused(self, mode: str) -> None:
        _refused(
            mode,
            "INVALID_MIN_AGE",
            API_MIN_AGE_MESSAGE,
            callback_url=CB,
            user_id="user_42",
            purpose="age_verification",
        )

    @pytest.mark.parametrize("min_age", [12, 15, 18, 19, 21, 25])
    def test_in_range_is_sent_as_given(self, mode: str, min_age: int) -> None:
        # 19 goes on the wire as 19. Only the API rounds it up to 21, so a
        # change to the band table never needs an SDK release.
        sent, body = _init(mode, callback_url=CB, user_id="user_42", min_age=min_age)
        assert sent == 1
        assert body is not None
        assert body["min_age"] == min_age

    def test_facial_is_allowed_for_an_age_verification(self, mode: str) -> None:
        sent, body = _init(
            mode, callback_url=CB, user_id="user_42", min_age=18, verification_mode="facial"
        )
        assert sent == 1
        assert body == {
            "callback_url": CB,
            "user_id": "user_42",
            "min_age": 18,
            "verification_mode": "facial",
        }


@pytest.mark.parametrize("mode", MODES)
class TestIdVerification:
    @pytest.mark.parametrize("min_age", [18, 12, 1, -1, True, False, 0.5, 0.0])
    def test_any_min_age_is_refused(self, mode: str, min_age: Any) -> None:
        _refused(
            mode,
            "INVALID_MIN_AGE",
            API_MIN_AGE_MESSAGE,
            callback_url=CB,
            user_id="user_42",
            purpose="id_verification",
            min_age=min_age,
        )

    def test_facial_is_refused(self, mode: str) -> None:
        _refused(
            mode,
            "INVALID_VERIFICATION_MODE",
            API_ID_FACIAL_MESSAGE,
            callback_url=CB,
            user_id="user_42",
            purpose="id_verification",
            verification_mode="facial",
        )

    def test_without_min_age_is_sent_without_it(self, mode: str) -> None:
        sent, body = _init(mode, callback_url=CB, user_id="user_42", purpose="id_verification")
        assert sent == 1
        assert body == {"callback_url": CB, "user_id": "user_42", "purpose": "id_verification"}

    def test_min_age_zero_is_accepted(self, mode: str) -> None:
        sent, body = _init(
            mode, callback_url=CB, user_id="user_42", purpose="id_verification", min_age=0
        )
        assert sent == 1
        assert body == {
            "callback_url": CB,
            "user_id": "user_42",
            "purpose": "id_verification",
            "min_age": 0,
        }

    @pytest.mark.parametrize("verification_mode", ["document", "auto"])
    def test_document_and_auto_are_accepted(self, mode: str, verification_mode: str) -> None:
        sent, body = _init(
            mode,
            callback_url=CB,
            user_id="user_42",
            purpose="id_verification",
            verification_mode=verification_mode,
        )
        assert sent == 1
        # The whole body: purpose and mode must both survive, and no age may
        # be added after validation (the API would refuse an ID session with one).
        assert body == {
            "callback_url": CB,
            "user_id": "user_42",
            "purpose": "id_verification",
            "verification_mode": verification_mode,
        }


@pytest.mark.parametrize("mode", MODES)
class TestPurpose:
    @pytest.mark.parametrize("purpose", ["age", "ID_VERIFICATION", "kyc", " age_verification"])
    def test_an_unknown_purpose_is_refused(self, mode: str, purpose: str) -> None:
        _refused(
            mode,
            "INVALID_PURPOSE",
            API_INVALID_PURPOSE_MESSAGE,
            callback_url=CB,
            user_id="user_42",
            min_age=18,
            purpose=purpose,
        )

    def test_the_purpose_is_checked_before_the_age(self, mode: str) -> None:
        # The API checks purpose first, so an unknown purpose with an
        # out-of-range age answers INVALID_PURPOSE, not INVALID_MIN_AGE.
        _refused(
            mode,
            "INVALID_PURPOSE",
            API_INVALID_PURPOSE_MESSAGE,
            callback_url=CB,
            user_id="user_42",
            min_age=99,
            purpose="adult",
        )

    def test_the_user_id_is_checked_before_the_purpose(self, mode: str) -> None:
        _refused(
            mode,
            "MISSING_USER_ID",
            API_MISSING_USER_ID_MESSAGE,
            callback_url=CB,
            user_id="",
            min_age=18,
            purpose="adult",
        )

    @pytest.mark.parametrize("purpose", ["", "age_verification"])
    def test_the_default_purpose_is_accepted_and_sent_as_given(
        self, mode: str, purpose: str
    ) -> None:
        sent, body = _init(mode, callback_url=CB, user_id="user_42", min_age=18, purpose=purpose)
        assert sent == 1
        assert body is not None
        assert body["min_age"] == 18


def test_api_refusal_still_surfaces_as_validation_error() -> None:
    """A rule only the API knows (here a credential-shaped user_id) still
    reaches the caller as a ValidationError with the API's code."""
    transport = MockTransport()
    transport.queue_error(400, "INVALID_USER_ID", "user_id must not be a Xident credential")
    client = xident.Xident(api_key="sk_test_123", transport=transport)

    with pytest.raises(xident.ValidationError) as excinfo:
        client.verification.init(callback_url=CB, user_id="sk_live_oops", min_age=18)

    assert excinfo.value.error_code == "INVALID_USER_ID"
    assert transport.request_count == 1

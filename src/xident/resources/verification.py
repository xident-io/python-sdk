"""Verification resource -- create init tokens and retrieve session results.

Provides both synchronous and asynchronous interfaces.
Mirrors the PHP SDK's Verification resource exactly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from .._http_client import AsyncHttpClient, SyncHttpClient
from ..errors import ValidationError
from ..responses.init_result import InitResult
from ..responses.session_result import SessionResult

#: The minimum age an age verification may ask for, in years. The browser age
#: models decide only five ages (12, 15, 18, 21 and 25), so the API refuses
#: anything outside 12 to 25 and rounds a value inside it UP to the next of
#: those bands (19 is enforced as 21). The SDK checks the range only; the
#: rounding happens in one place, the API.
_MIN_AGE_FLOOR = 12
_MIN_AGE_CEILING = 25

#: The same messages the API answers with, so a caller sees one text per code
#: whether the SDK or the API caught the mistake.
_MISSING_USER_ID_MESSAGE = (
    "user_id is required: pass your own identifier for the person being verified"
)
_INVALID_MIN_AGE_MESSAGE = (
    "min_age must be between 12 and 25; it is rounded up to the next of 12, 15, 18, "
    "21 or 25 (19 is enforced as 21). An id_verification takes no min_age."
)
_ID_FACIAL_MESSAGE = (
    "verification_mode facial cannot be combined with purpose id_verification, "
    "which always requires a document"
)


def _local_validation_error(message: str, error_code: str) -> ValidationError:
    """A ValidationError raised by the SDK itself, before any request.

    It carries the status code and error code the API would answer with, so
    one ``except ValidationError`` handles both. ``request_id`` stays None:
    no request was sent.
    """
    return ValidationError(message, status_code=400, error_code=error_code)


def _is_whole_number(value: object) -> bool:
    """True for an int that is not a bool (``True`` is an int in Python)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_init(
    *,
    user_id: str | None,
    min_age: int | None,
    purpose: str | None,
    verification_mode: str | None,
) -> None:
    """Refuse, before any request, the init settings the API would refuse.

    The API is the authority and checks the same rules again. Checking here
    first gives the caller the API's error code without a network round trip,
    and keeps a request that can only fail from leaving the process.

    Raises:
        ValidationError: ``MISSING_USER_ID``, ``INVALID_MIN_AGE`` or
            ``INVALID_VERIFICATION_MODE``.
    """
    if user_id is None or (isinstance(user_id, str) and not user_id.strip()):
        raise _local_validation_error(_MISSING_USER_ID_MESSAGE, "MISSING_USER_ID")

    if purpose == "id_verification":
        # An ID verification has no age threshold: min_age absent or 0.
        if min_age is not None and not (_is_whole_number(min_age) and min_age == 0):
            raise _local_validation_error(_INVALID_MIN_AGE_MESSAGE, "INVALID_MIN_AGE")
        if verification_mode == "facial":
            raise _local_validation_error(_ID_FACIAL_MESSAGE, "INVALID_VERIFICATION_MODE")
        return

    # Any other purpose (age_verification, the default) needs an age the
    # browser models can decide. An unknown purpose is checked the strict way
    # too; the API then answers INVALID_PURPOSE for it.
    if (
        min_age is None
        or not _is_whole_number(min_age)
        or not _MIN_AGE_FLOOR <= min_age <= _MIN_AGE_CEILING
    ):
        raise _local_validation_error(_INVALID_MIN_AGE_MESSAGE, "INVALID_MIN_AGE")


class Verification:
    """Synchronous verification resource.

    Usage::

        client = Xident(api_key="sk_test_...")
        result = client.verification.init(
            callback_url="https://example.com/cb", user_id="user_42", min_age=18
        )
        session = client.verification.get_result("xtk_abc123")
    """

    def __init__(self, http: SyncHttpClient) -> None:
        self._http = http

    def init(
        self,
        *,
        callback_url: str,
        user_id: str,
        min_age: int | None = None,
        success_url: str | None = None,
        failed_url: str | None = None,
        theme: str | None = None,
        locale: str | None = None,
        metadata: str | None = None,
        purpose: str | None = None,
        verification_mode: str | None = None,
        liveness_difficulty: str | None = None,
        expected: Mapping[str, str] | None = None,
        mismatch_policy: str | None = None,
    ) -> InitResult:
        """Create an init token for starting a verification session.

        Returns a token and the full URL to redirect the user to.
        The token is valid for 10 minutes.

        Args:
            callback_url: URL where user is redirected after verification.
            user_id: Required. Your own identifier for the person being
                verified. It comes back on the callback and in the result.
            min_age: Required for "age_verification": a whole number from 12
                to 25. Xident rounds it up to the next of 12, 15, 18, 21 or 25
                and enforces that band, so 19 is enforced as 21. The SDK sends
                the value as given. An "id_verification" takes no min_age
                (leave it out, or pass 0).
            success_url: Override redirect URL on success.
            failed_url: Override redirect URL on failure.
            theme: Widget theme ("light", "dark", "system").
            locale: Widget locale (e.g. "en", "de", "fr").
            metadata: Opaque string stored with the session.
            purpose: Verification purpose ("age_verification" or "id_verification").
            verification_mode: Overrides the rule engine's choice of methods
                for this session: "auto" (default), "document" to force
                document + face match, or "facial" to force on-device age
                estimation. Composes with ``min_age`` rather than replacing
                it -- "document" with ``min_age=21`` still enforces 21, it
                just insists the proof be a document. "facial" cannot be
                combined with purpose "id_verification", which always needs a
                document.
            liveness_difficulty: Overrides the number of liveness actions the
                widget requires: "easy", "medium", or "hard".
            expected: Identity data you already hold about the user, to be
                checked against the document they present (data match, since
                2026-09-05). Any subset of ``first_name``, ``last_name``,
                ``date_of_birth`` (YYYY-MM-DD), ``document_number``,
                ``nationality`` (ISO alpha-2). Needs a document: pair it with
                ``purpose="id_verification"`` or ``verification_mode="document"``.
                The values never reach the browser; the result carries only
                verdicts, per field, in ``checks.data_match``.
            mismatch_policy: What a mismatch does. "report" (default):
                reported in the result, outcome unchanged. "review": any
                mismatch sends the session to your review queue with reason
                ``data_mismatch``. Only meaningful with ``expected``.

        Returns:
            InitResult with token and verify_url.

        Raises:
            ValidationError: Before any request, when ``user_id`` is empty
                (``MISSING_USER_ID``), ``min_age`` is outside the rules above
                (``INVALID_MIN_AGE``), or "id_verification" is combined with
                "facial" (``INVALID_VERIFICATION_MODE``). Also when the API
                refuses a parameter (HTTP 400).
            AuthenticationError: If the API key is invalid. (A public key,
                ``pk_``, never gets this far: the client refuses it when it is
                built, and the API answers it with 403 ``SECRET_KEY_REQUIRED``.)
        """
        _validate_init(
            user_id=user_id,
            min_age=min_age,
            purpose=purpose,
            verification_mode=verification_mode,
        )
        body = self._build_params(
            callback_url=callback_url,
            min_age=min_age,
            success_url=success_url,
            failed_url=failed_url,
            user_id=user_id,
            theme=theme,
            locale=locale,
            metadata=metadata,
            purpose=purpose,
            verification_mode=verification_mode,
            liveness_difficulty=liveness_difficulty,
            expected=dict(expected) if expected else None,
            mismatch_policy=mismatch_policy,
        )
        data = self._http.post("/init", body=body)
        return InitResult.from_dict(data)

    def get_result(self, token: str) -> SessionResult:
        """Get the verification result for a token.

        Call this after the user returns from the verification widget.
        NEVER trust URL parameters alone -- always re-verify server-side.

        Args:
            token: The verification token from the callback URL.

        Returns:
            SessionResult with the full session state.

        Raises:
            ValueError: If token is empty.
            NotFoundError: If token does not exist.
            AuthenticationError: If API key is invalid.
        """
        if not token:
            raise ValueError("Token cannot be empty")
        data = self._http.get(f"/result/{quote(token, safe='')}")
        return SessionResult.from_dict(data)

    @staticmethod
    def _build_params(**kwargs: Any) -> dict[str, Any]:
        """Build request body, omitting None values."""
        return {k: v for k, v in kwargs.items() if v is not None}


class AsyncVerification:
    """Asynchronous verification resource.

    Usage::

        client = AsyncXident(api_key="sk_test_...")
        result = await client.verification.init(
            callback_url="https://example.com/cb", user_id="user_42", min_age=18
        )
        session = await client.verification.get_result("xtk_abc123")
    """

    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def init(
        self,
        *,
        callback_url: str,
        user_id: str,
        min_age: int | None = None,
        success_url: str | None = None,
        failed_url: str | None = None,
        theme: str | None = None,
        locale: str | None = None,
        metadata: str | None = None,
        purpose: str | None = None,
        verification_mode: str | None = None,
        liveness_difficulty: str | None = None,
        expected: Mapping[str, str] | None = None,
        mismatch_policy: str | None = None,
    ) -> InitResult:
        """Create an init token for starting a verification session (async).

        Returns a token and the full URL to redirect the user to.
        The token is valid for 10 minutes.

        Args:
            callback_url: URL where user is redirected after verification.
            user_id: Required. Your own identifier for the person being
                verified. It comes back on the callback and in the result.
            min_age: Required for "age_verification": a whole number from 12
                to 25. Xident rounds it up to the next of 12, 15, 18, 21 or 25
                and enforces that band, so 19 is enforced as 21. The SDK sends
                the value as given. An "id_verification" takes no min_age
                (leave it out, or pass 0).
            success_url: Override redirect URL on success.
            failed_url: Override redirect URL on failure.
            theme: Widget theme ("light", "dark", "system").
            locale: Widget locale (e.g. "en", "de", "fr").
            metadata: Opaque string stored with the session.
            purpose: Verification purpose ("age_verification" or "id_verification").
            verification_mode: Overrides the rule engine's choice of methods
                for this session: "auto" (default), "document" to force
                document + face match, or "facial" to force on-device age
                estimation. Composes with ``min_age`` rather than replacing
                it -- "document" with ``min_age=21`` still enforces 21, it
                just insists the proof be a document. "facial" cannot be
                combined with purpose "id_verification", which always needs a
                document.
            liveness_difficulty: Overrides the number of liveness actions the
                widget requires: "easy", "medium", or "hard".
            expected: Identity data you already hold about the user, to be
                checked against the document they present (data match, since
                2026-09-05). Any subset of ``first_name``, ``last_name``,
                ``date_of_birth`` (YYYY-MM-DD), ``document_number``,
                ``nationality`` (ISO alpha-2). Needs a document: pair it with
                ``purpose="id_verification"`` or ``verification_mode="document"``.
                The values never reach the browser; the result carries only
                verdicts, per field, in ``checks.data_match``.
            mismatch_policy: What a mismatch does. "report" (default):
                reported in the result, outcome unchanged. "review": any
                mismatch sends the session to your review queue with reason
                ``data_mismatch``. Only meaningful with ``expected``.

        Returns:
            InitResult with token and verify_url.

        Raises:
            ValidationError: Before any request, when ``user_id`` is empty
                (``MISSING_USER_ID``), ``min_age`` is outside the rules above
                (``INVALID_MIN_AGE``), or "id_verification" is combined with
                "facial" (``INVALID_VERIFICATION_MODE``). Also when the API
                refuses a parameter (HTTP 400).
            AuthenticationError: If the API key is invalid. (A public key,
                ``pk_``, never gets this far: the client refuses it when it is
                built, and the API answers it with 403 ``SECRET_KEY_REQUIRED``.)
        """
        _validate_init(
            user_id=user_id,
            min_age=min_age,
            purpose=purpose,
            verification_mode=verification_mode,
        )
        body = Verification._build_params(
            callback_url=callback_url,
            min_age=min_age,
            success_url=success_url,
            failed_url=failed_url,
            user_id=user_id,
            theme=theme,
            locale=locale,
            metadata=metadata,
            purpose=purpose,
            verification_mode=verification_mode,
            liveness_difficulty=liveness_difficulty,
            expected=dict(expected) if expected else None,
            mismatch_policy=mismatch_policy,
        )
        data = await self._http.post("/init", body=body)
        return InitResult.from_dict(data)

    async def get_result(self, token: str) -> SessionResult:
        """Get the verification result for a token (async).

        Call this after the user returns from the verification widget.
        NEVER trust URL parameters alone -- always re-verify server-side.

        Args:
            token: The verification token from the callback URL.

        Returns:
            SessionResult with the full session state.

        Raises:
            ValueError: If token is empty.
            NotFoundError: If token does not exist.
            AuthenticationError: If API key is invalid.
        """
        if not token:
            raise ValueError("Token cannot be empty")
        data = await self._http.get(f"/result/{quote(token, safe='')}")
        return SessionResult.from_dict(data)

"""Face 2FA resource -- enroll a face and verify against it (1:1).

Provides both synchronous and asynchronous interfaces.

Face 2FA is asynchronous on the server: ``register`` and ``verify`` enqueue
processing and return a challenge, which you poll with ``get_status`` until
it reaches a terminal state. The API returns pass/fail only -- never
confidence scores or biometric data.
"""

from __future__ import annotations

from urllib.parse import quote

from .._http_client import AsyncHttpClient, SyncHttpClient
from ..responses.face_2fa import Face2FAChallenge, Face2FAEnrollment, Face2FAStatus


class Face2FA:
    """Synchronous face 2FA resource.

    Usage::

        client = Xident(api_key="sk_test_...")
        challenge = client.face_2fa.register(user_id="user_42", image=b64_selfie)
        status = client.face_2fa.get_status(challenge.challenge_id)
    """

    def __init__(self, http: SyncHttpClient) -> None:
        self._http = http

    def register(self, *, user_id: str, image: str) -> Face2FAChallenge:
        """Register (or replace) the face enrolled for one of your users.

        Asynchronous: poll ``get_status()`` with the returned challenge id
        for the outcome. Registration is free of charge.

        Args:
            user_id: Your application's user identifier (max 255 chars).
            image: Base64-encoded face image (max ~10MB of base64).

        Returns:
            Face2FAChallenge with challenge_id and status ("processing").

        Raises:
            ValidationError: If user_id or image is missing/invalid.
            AuthenticationError: If API key is invalid.
        """
        data = self._http.post("/2fa/register", body={"user_id": user_id, "image": image})
        return Face2FAChallenge.from_dict(data)

    def verify(self, *, user_id: str, image: str) -> Face2FAChallenge:
        """Verify a face against the user's enrolled 2FA embedding (1:1).

        Asynchronous: poll ``get_status()`` with the returned challenge id
        for the pass/fail verdict.

        Args:
            user_id: Your application's user identifier (max 255 chars).
            image: Base64-encoded face image (max ~10MB of base64).

        Returns:
            Face2FAChallenge with challenge_id and status ("processing").

        Raises:
            ValidationError: If user_id or image is missing/invalid.
            AuthenticationError: If API key is invalid.
        """
        data = self._http.post("/2fa/verify", body={"user_id": user_id, "image": image})
        return Face2FAChallenge.from_dict(data)

    def get_status(self, challenge_id: str) -> Face2FAStatus:
        """Poll the outcome of a register or verify challenge.

        Args:
            challenge_id: The challenge id returned by register/verify.

        Returns:
            Face2FAStatus with the pass/fail verdict and failure reason.

        Raises:
            ValueError: If challenge_id is empty.
            NotFoundError: If the challenge does not exist.
            AuthenticationError: If API key is invalid.
        """
        if not challenge_id:
            raise ValueError("Challenge ID cannot be empty")
        data = self._http.get(f"/2fa/status/{quote(challenge_id, safe='')}")
        return Face2FAStatus.from_dict(data)

    def get_user(self, user_id: str) -> Face2FAEnrollment:
        """Check whether one of your users has a 2FA face enrolled.

        Args:
            user_id: Your application's user identifier.

        Returns:
            Face2FAEnrollment with enrolled flag and enrollment timestamp.

        Raises:
            ValueError: If user_id is empty.
            AuthenticationError: If API key is invalid.
        """
        if not user_id:
            raise ValueError("User ID cannot be empty")
        data = self._http.get(f"/2fa/users/{quote(user_id, safe='')}")
        return Face2FAEnrollment.from_dict(data)

    def delete_user(self, user_id: str) -> bool:
        """Delete a user's 2FA face enrollment (GDPR hard delete).

        Idempotent -- succeeds whether or not an enrollment existed.

        Args:
            user_id: Your application's user identifier.

        Returns:
            True when the deletion was processed.

        Raises:
            ValueError: If user_id is empty.
            AuthenticationError: If API key is invalid.
        """
        if not user_id:
            raise ValueError("User ID cannot be empty")
        data = self._http.delete(f"/2fa/users/{quote(user_id, safe='')}")
        return bool(data.get("deleted", False))


class AsyncFace2FA:
    """Asynchronous face 2FA resource.

    Usage::

        client = AsyncXident(api_key="sk_test_...")
        challenge = await client.face_2fa.register(user_id="user_42", image=b64_selfie)
        status = await client.face_2fa.get_status(challenge.challenge_id)
    """

    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def register(self, *, user_id: str, image: str) -> Face2FAChallenge:
        """Register (or replace) the face enrolled for one of your users (async).

        Asynchronous: poll ``get_status()`` with the returned challenge id
        for the outcome. Registration is free of charge.

        Args:
            user_id: Your application's user identifier (max 255 chars).
            image: Base64-encoded face image (max ~10MB of base64).

        Returns:
            Face2FAChallenge with challenge_id and status ("processing").

        Raises:
            ValidationError: If user_id or image is missing/invalid.
            AuthenticationError: If API key is invalid.
        """
        data = await self._http.post("/2fa/register", body={"user_id": user_id, "image": image})
        return Face2FAChallenge.from_dict(data)

    async def verify(self, *, user_id: str, image: str) -> Face2FAChallenge:
        """Verify a face against the user's enrolled 2FA embedding (async).

        Asynchronous: poll ``get_status()`` with the returned challenge id
        for the pass/fail verdict.

        Args:
            user_id: Your application's user identifier (max 255 chars).
            image: Base64-encoded face image (max ~10MB of base64).

        Returns:
            Face2FAChallenge with challenge_id and status ("processing").

        Raises:
            ValidationError: If user_id or image is missing/invalid.
            AuthenticationError: If API key is invalid.
        """
        data = await self._http.post("/2fa/verify", body={"user_id": user_id, "image": image})
        return Face2FAChallenge.from_dict(data)

    async def get_status(self, challenge_id: str) -> Face2FAStatus:
        """Poll the outcome of a register or verify challenge (async).

        Args:
            challenge_id: The challenge id returned by register/verify.

        Returns:
            Face2FAStatus with the pass/fail verdict and failure reason.

        Raises:
            ValueError: If challenge_id is empty.
            NotFoundError: If the challenge does not exist.
            AuthenticationError: If API key is invalid.
        """
        if not challenge_id:
            raise ValueError("Challenge ID cannot be empty")
        data = await self._http.get(f"/2fa/status/{quote(challenge_id, safe='')}")
        return Face2FAStatus.from_dict(data)

    async def get_user(self, user_id: str) -> Face2FAEnrollment:
        """Check whether one of your users has a 2FA face enrolled (async).

        Args:
            user_id: Your application's user identifier.

        Returns:
            Face2FAEnrollment with enrolled flag and enrollment timestamp.

        Raises:
            ValueError: If user_id is empty.
            AuthenticationError: If API key is invalid.
        """
        if not user_id:
            raise ValueError("User ID cannot be empty")
        data = await self._http.get(f"/2fa/users/{quote(user_id, safe='')}")
        return Face2FAEnrollment.from_dict(data)

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user's 2FA face enrollment (GDPR hard delete, async).

        Idempotent -- succeeds whether or not an enrollment existed.

        Args:
            user_id: Your application's user identifier.

        Returns:
            True when the deletion was processed.

        Raises:
            ValueError: If user_id is empty.
            AuthenticationError: If API key is invalid.
        """
        if not user_id:
            raise ValueError("User ID cannot be empty")
        data = await self._http.delete(f"/2fa/users/{quote(user_id, safe='')}")
        return bool(data.get("deleted", False))

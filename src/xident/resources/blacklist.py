"""Blacklist resource -- manage your tenant's face blacklist.

Provides both synchronous and asynchronous interfaces.

Entries are added by SESSION or IMAGE -- the face embedding is derived
server-side and never returned by the API. Adding is asynchronous: both
add calls return immediately with status "processing" and the entry
appears in ``list()`` once processed.
"""

from __future__ import annotations

from typing import Any

from .._http_client import AsyncHttpClient, SyncHttpClient
from ..responses.blacklist import BlacklistPage


class Blacklist:
    """Synchronous blacklist resource.

    Usage::

        client = Xident(api_key="sk_test_...")
        page = client.blacklist.list(page=1, per_page=20)
        client.blacklist.add_by_session(session_token="xtk_abc", reason="fraud")
        client.blacklist.remove(page.entries[0].id)
    """

    def __init__(self, http: SyncHttpClient) -> None:
        self._http = http

    def list(self, *, page: int | None = None, per_page: int | None = None) -> BlacklistPage:
        """List your active blacklist entries (paginated).

        Embeddings are never returned -- only reason, source and timestamps.

        Args:
            page: Page number, 1-based (server default: 1).
            per_page: Page size, max 100 (server default: 20).

        Returns:
            BlacklistPage with entries and pagination metadata.

        Raises:
            AuthenticationError: If API key is invalid.
        """
        envelope = self._http.get_envelope("/blacklist", params=_page_params(page, per_page))
        return BlacklistPage.from_envelope(envelope)

    def add_by_session(self, *, session_token: str, reason: str) -> str:
        """Blacklist the person from one of YOUR verification sessions.

        The server lifts the session's selfie and blacklists that face.
        Works within the 24h document-retention window for terminal
        sessions that captured a selfie. Asynchronous -- the entry appears
        in ``list()`` once processed.

        Args:
            session_token: The verification session token (xtk_...).
            reason: Why the face is being blacklisted (max 500 chars).

        Returns:
            The processing status string ("processing").

        Raises:
            ValidationError: If params are invalid, or the session is
                still in progress (HTTP 409).
            NotFoundError: If the session does not exist or is not yours.
            AuthenticationError: If API key is invalid.
        """
        data = self._http.post(
            "/blacklist/session", body={"session_token": session_token, "reason": reason}
        )
        return str(data.get("status", ""))

    def add_by_image(self, *, image: str, reason: str) -> str:
        """Blacklist the face in an image.

        The server extracts the face embedding from the image and
        blacklists it. Asynchronous -- the entry appears in ``list()``
        once processed.

        Args:
            image: Base64-encoded image containing the face (max ~10MB).
            reason: Why the face is being blacklisted (max 500 chars).

        Returns:
            The processing status string ("processing").

        Raises:
            ValidationError: If image or reason is missing/invalid.
            AuthenticationError: If API key is invalid.
        """
        data = self._http.post("/blacklist/image", body={"image": image, "reason": reason})
        return str(data.get("status", ""))

    def remove(self, entry_id: int) -> None:
        """Remove (deactivate) one of your blacklist entries (un-ban).

        Args:
            entry_id: The blacklist entry id (from ``list()``).

        Raises:
            ValueError: If entry_id is not a positive integer.
            NotFoundError: If the entry does not exist or is not yours.
            AuthenticationError: If API key is invalid.
        """
        if entry_id <= 0:
            raise ValueError("Entry ID must be a positive integer")
        self._http.delete(f"/blacklist/{entry_id}")


class AsyncBlacklist:
    """Asynchronous blacklist resource.

    Usage::

        client = AsyncXident(api_key="sk_test_...")
        page = await client.blacklist.list(page=1, per_page=20)
        await client.blacklist.add_by_image(image=b64_image, reason="fraud")
        await client.blacklist.remove(page.entries[0].id)
    """

    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def list(
        self, *, page: int | None = None, per_page: int | None = None
    ) -> BlacklistPage:
        """List your active blacklist entries (paginated, async).

        Embeddings are never returned -- only reason, source and timestamps.

        Args:
            page: Page number, 1-based (server default: 1).
            per_page: Page size, max 100 (server default: 20).

        Returns:
            BlacklistPage with entries and pagination metadata.

        Raises:
            AuthenticationError: If API key is invalid.
        """
        envelope = await self._http.get_envelope(
            "/blacklist", params=_page_params(page, per_page)
        )
        return BlacklistPage.from_envelope(envelope)

    async def add_by_session(self, *, session_token: str, reason: str) -> str:
        """Blacklist the person from one of YOUR verification sessions (async).

        The server lifts the session's selfie and blacklists that face.
        Works within the 24h document-retention window for terminal
        sessions that captured a selfie. Asynchronous -- the entry appears
        in ``list()`` once processed.

        Args:
            session_token: The verification session token (xtk_...).
            reason: Why the face is being blacklisted (max 500 chars).

        Returns:
            The processing status string ("processing").

        Raises:
            ValidationError: If params are invalid, or the session is
                still in progress (HTTP 409).
            NotFoundError: If the session does not exist or is not yours.
            AuthenticationError: If API key is invalid.
        """
        data = await self._http.post(
            "/blacklist/session", body={"session_token": session_token, "reason": reason}
        )
        return str(data.get("status", ""))

    async def add_by_image(self, *, image: str, reason: str) -> str:
        """Blacklist the face in an image (async).

        The server extracts the face embedding from the image and
        blacklists it. Asynchronous -- the entry appears in ``list()``
        once processed.

        Args:
            image: Base64-encoded image containing the face (max ~10MB).
            reason: Why the face is being blacklisted (max 500 chars).

        Returns:
            The processing status string ("processing").

        Raises:
            ValidationError: If image or reason is missing/invalid.
            AuthenticationError: If API key is invalid.
        """
        data = await self._http.post("/blacklist/image", body={"image": image, "reason": reason})
        return str(data.get("status", ""))

    async def remove(self, entry_id: int) -> None:
        """Remove (deactivate) one of your blacklist entries (un-ban, async).

        Args:
            entry_id: The blacklist entry id (from ``list()``).

        Raises:
            ValueError: If entry_id is not a positive integer.
            NotFoundError: If the entry does not exist or is not yours.
            AuthenticationError: If API key is invalid.
        """
        if entry_id <= 0:
            raise ValueError("Entry ID must be a positive integer")
        await self._http.delete(f"/blacklist/{entry_id}")


def _page_params(page: int | None, per_page: int | None) -> dict[str, Any]:
    """Build pagination query params, omitting None values."""
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page
    return params

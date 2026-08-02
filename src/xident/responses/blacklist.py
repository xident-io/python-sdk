"""Blacklist response value objects.

Blacklist entries are managed by SESSION or IMAGE -- the face embedding is
derived server-side and NEVER returned by the API. Adding is asynchronous:
the entry appears in the list once processed.

Frozen dataclasses -- immutable after construction (value object semantics).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BlacklistEntry:
    """One active blacklist entry, as visible to the tenant.

    Attributes:
        id: Entry identifier (use with ``client.blacklist.remove()``).
        reason: Why the face was blacklisted (supplied when adding).
        source: How the entry was created (e.g. "session", "image").
        session_id: Originating verification session id, or None.
        created_at: ISO 8601 timestamp of entry creation.
    """

    id: int
    reason: str
    source: str
    session_id: int | None = None
    created_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlacklistEntry:
        """Create a BlacklistEntry from an API response row dict."""
        session_id_raw = data.get("session_id")
        return cls(
            id=int(data.get("id", 0)),
            reason=str(data.get("reason", "")),
            source=str(data.get("source", "")),
            session_id=int(session_id_raw) if session_id_raw is not None else None,
            created_at=str(data.get("created_at", "")),
        )


@dataclass(frozen=True)
class BlacklistPage:
    """One page of blacklist entries plus pagination metadata.

    Attributes:
        entries: The entries on this page.
        page: Current page number (1-based).
        per_page: Page size.
        total: Total number of entries across all pages.
        total_pages: Total number of pages.
    """

    entries: list[BlacklistEntry] = field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Any:
        return iter(self.entries)

    @property
    def has_more(self) -> bool:
        """Whether pages beyond this one exist."""
        return self.page < self.total_pages

    @classmethod
    def from_envelope(cls, envelope: dict[str, Any]) -> BlacklistPage:
        """Create a BlacklistPage from a FULL API response envelope.

        List endpoints return rows in ``data`` and pagination in
        ``meta.pagination`` -- so unlike the other value objects this one
        parses the whole envelope, not just ``data``.
        """
        rows = envelope.get("data") or []
        if not isinstance(rows, list):
            rows = []
        meta = envelope.get("meta") or {}
        pagination = meta.get("pagination") or {}
        return cls(
            entries=[BlacklistEntry.from_dict(row) for row in rows],
            page=int(pagination.get("page", 1)),
            per_page=int(pagination.get("per_page", len(rows))),
            total=int(pagination.get("total", len(rows))),
            total_pages=int(pagination.get("total_pages", 1 if rows else 0)),
        )

"""Result of creating an init token.

Contains the token and the full URL to redirect the user to for verification.
Frozen dataclass — immutable after construction (value object semantics).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InitResult:
    """Result of creating an init token.

    Attributes:
        token: Short-lived init token (xit_ prefixed, 10-minute TTL).
        verify_url: Full verification URL -- redirect the user here.
    """

    token: str
    verify_url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InitResult:
        """Create an InitResult from an API response data dict."""
        return cls(
            token=str(data.get("token", "")),
            verify_url=str(data.get("verify_url", "")),
        )

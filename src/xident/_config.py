"""SDK configuration — immutable after construction.

Mirrors the PHP SDK's Config class: readonly properties, sensible defaults,
validation on construction.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.xident.io"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
API_VERSION = "verify/v1"
"""The API version path PREFIX. Not the dated response contract -- see
PINNED_API_VERSION. Naming these alike is how the verification_mode /
verification_type confusion started."""

PINNED_API_VERSION = "2026-08-13"
"""The dated API version this SDK release was built against, sent as
X-API-Version on every request.

Pinned in the SDK rather than relying on the project's dashboard setting so that
this release's response types always match the payload the server sends: a
customer pinned to an older version still receives the shape these dataclasses
parse. Sending nothing instead would let a newer SDK read an older shape and
silently leave fields empty.

Upgrading the MAJOR version of this SDK is therefore an explicit opt-in to a new
API version. Pass ``api_version=`` to the client to override, e.g. to trial a
newer version before changing the dashboard pin.

Deliberately NOT derived from SDK_VERSION: they move on different clocks, and an
SDK patch release must never change which API shape a customer receives.
"""
#: The ONE place the SDK version is declared.
#:
#: ``pyproject.toml`` does not carry its own copy -- it declares the version
#: dynamic and reads this literal at build time (``[tool.hatch.version]``), so
#: the packaged version and the version this module reports cannot drift apart.
#: Bump it here and nowhere else.
#:
#: Deliberately a literal rather than ``importlib.metadata.version("xident")``:
#: metadata only exists for an *installed* distribution, so a source checkout,
#: a vendored copy or a zipapp would raise ``PackageNotFoundError`` and need a
#: hardcoded fallback -- which is the second number this change exists to
#: remove. Installed metadata also goes stale against an editable checkout
#: until the next reinstall.
SDK_VERSION = "3.1.1"


@dataclass(frozen=True)
class Config:
    """Immutable SDK configuration.

    Attributes:
        api_key: Your Xident secret API key (sk_live_xxx or sk_test_xxx).
        base_url: API base URL (default: https://api.xident.io).
        timeout: Request timeout in seconds (default: 30).
        max_retries: Max retries on 5xx errors (default: 3).
        headers: Extra headers to send with every request.
        api_version: Override the dated API version sent as X-API-Version.
            Defaults to PINNED_API_VERSION, the version this SDK release was
            built against, which is the right choice for almost everyone: it
            guarantees the response types match the payload. Override it to trial
            a NEWER version before changing your project's dashboard pin.
    """

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    headers: dict[str, str] | None = None
    api_version: str = PINNED_API_VERSION

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("API key cannot be empty")
        if self.api_key.startswith("pk_"):
            raise ValueError(
                "Public keys (pk_*) cannot be used with the server SDK. "
                "Use your secret key (sk_live_* or sk_test_*)."
            )
        if not self.api_key.startswith("sk_live_") and not self.api_key.startswith("sk_test_"):
            raise ValueError(
                'Invalid API key format. Must start with "sk_live_" or "sk_test_".'
            )
        # Strip trailing slash from base_url
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))
        # Clamp timeout to at least 1
        object.__setattr__(self, "timeout", max(1, self.timeout))
        # Clamp max_retries to at least 0
        object.__setattr__(self, "max_retries", max(0, self.max_retries))

    @property
    def api_url(self) -> str:
        """Full API URL (base + version prefix)."""
        return f"{self.base_url}/{API_VERSION}"

    @property
    def user_agent(self) -> str:
        """User-Agent header value."""
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return (
            f"Xident-Python/{SDK_VERSION} Python/{py_version} "
            f"{platform.system()}/{platform.release()}"
        )

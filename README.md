# Xident Python SDK

Official Python SDK for [Xident](https://xident.io) age and identity verification. Try it live at [demo.xident.io](https://demo.xident.io).

[![PyPI version](https://img.shields.io/pypi/v/xident.svg)](https://pypi.org/project/xident/)
[![Python versions](https://img.shields.io/pypi/pyversions/xident.svg)](https://pypi.org/project/xident/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Installation

```bash
pip install xident
```

Requires Python 3.9+.

## Quick Start

```python
from xident import Xident

client = Xident(api_key="sk_live_...")

# Create an init token
result = client.verification.init(
    callback_url="https://example.com/callback",
    min_age=18,
)
print(result.verify_url)  # Redirect user here

# After callback, verify result server-side
session = client.verification.get_result("xtk_abc123")
if session.is_verified():
    print(f"Verified! Age: {session.age_bracket()}+")
```

> **v2.0.0 changed the shape of the verification result.** See
> [v2 breaking changes](#v2-breaking-changes) below before upgrading.

## Async Support

```python
from xident import AsyncXident

client = AsyncXident(api_key="sk_live_...")

result = await client.verification.init(
    callback_url="https://example.com/callback",
    min_age=18,
)

session = await client.verification.get_result("xtk_abc123")
```

## Configuration

```python
client = Xident(
    api_key="sk_live_...",       # Required: secret API key
    base_url="https://...",      # Override API URL
    timeout=30,                  # Request timeout (seconds)
    max_retries=3,               # Retry on 5xx errors
    headers={"X-Custom": "..."},  # Extra headers
)
```

## Verification

### Create Init Token

```python
result = client.verification.init(
    callback_url="https://example.com/callback",  # Required
    min_age=18,              # Age threshold 1-99 (0-99 when purpose="id_verification")
    success_url="...",       # Override redirect on success
    failed_url="...",        # Override redirect on failure
    user_id="user_42",       # Your user identifier
    theme="dark",            # Widget theme (light, dark, system)
    locale="de",             # Widget locale
    metadata="custom_data",  # Opaque metadata string
    purpose="age_verification",  # "age_verification" (default) or "id_verification"
    verification_mode="document",  # Force document + face match, skip on-device age estimation
    liveness_difficulty="hard",    # "easy", "medium", or "hard" -- more liveness actions
)

print(result.token)       # "xit_abc123" (init token, 10-minute TTL)
print(result.verify_url)  # Full URL to redirect user to
```

`verification_mode` composes with `min_age` rather than replacing it --
`verification_mode="document"` with `min_age=21` still enforces 21, it just
insists the proof be a document instead of letting the rule engine pick
on-device age estimation.

After verification the widget redirects the browser back to `callback_url` with
query parameters: `status` (`success` | `failed` | `canceled` — the same three
words the result endpoint uses), `token` (the **result** token `xtk_...`, which
is different from the init token `xit_...`), and `user_id` (if you supplied one).
Always re-verify the result server-side with `get_result()` — never trust the
callback query parameters alone.

### Get Verification Result

```python
session = client.verification.get_result("xtk_abc123")

session.is_verified()    # True if completed successfully
session.is_failed()      # True if verification failed
session.is_pending()     # True if still in progress
session.is_terminal()    # True if no more changes possible

session.age_bracket()    # 18 (verified age threshold) or None
session.method()         # "full" | "age_check" | "xident_id" | "eu_wallet"
session.status           # SessionStatus.SUCCESS
session.reason           # "" on success; e.g. "age_below_threshold" on failure
session.token            # "xtk_abc123" -- the result token, primary identifier

# Full detail on what ran and what passed:
session.checks.liveness.performed   # bool
session.checks.liveness.passed      # bool
session.checks.age.performed        # bool
session.checks.age.passed           # bool
session.checks.age.gate             # 12 / 15 / 18 / 21 / 25, or None
session.checks.document.performed   # bool
session.checks.document.passed      # bool
session.checks.document.document_type  # "passport", "drivers_license", or None
session.checks.document.country     # ISO 3166-1 alpha-2, or None
session.checks.face_match.performed  # bool
session.checks.face_match.passed     # bool
```

## Webhooks

```python
# Verify and parse a webhook event
event = client.webhooks.construct_event(
    payload=request_body,        # Raw JSON string or bytes
    signature=x_xident_signature,  # X-Xident-Signature header
    secret="whsec_...",          # Webhook secret from dashboard
    tolerance=300,               # Max age in seconds (default: 5 min)
)

print(event["type"])  # "session.success"
print(event["data"])  # Event payload dict

# Or verify signature only
client.webhooks.verify_signature(payload, signature, secret)
```

## Face 2FA

Enroll a face for one of your users, then verify a new selfie against it
(1:1 comparison). Processing is asynchronous — both calls return a challenge
you poll for the pass/fail verdict. The API never returns confidence scores
or biometric data.

```python
# Enroll (or replace) a user's face — free of charge
challenge = client.face_2fa.register(user_id="user_42", image=base64_selfie)

# Verify a new selfie against the enrolled face
challenge = client.face_2fa.verify(user_id="user_42", image=base64_selfie)

# Poll the outcome
status = client.face_2fa.get_status(challenge.challenge_id)
if status.is_processing():
    ...  # poll again shortly
elif status.is_passed():
    ...  # 2FA passed
else:
    print(status.failure_reason)  # "face_mismatch", "no_face_detected", ...

# Check enrollment
enrollment = client.face_2fa.get_user("user_42")
print(enrollment.enrolled, enrollment.enrolled_at)

# Delete the enrollment (GDPR hard delete, idempotent)
client.face_2fa.delete_user("user_42")
```

All methods are also available on `AsyncXident` (`await client.face_2fa...`).

## Blacklist

Manage your tenant's face blacklist. Entries are added by **session** or by
**image** — the face embedding is derived server-side and never returned.
Adding is asynchronous: the entry appears in `list()` once processed.

```python
# Blacklist the person from one of YOUR completed verification sessions
client.blacklist.add_by_session(session_token="xtk_abc123", reason="chargeback fraud")

# Or blacklist the face in an image
client.blacklist.add_by_image(image=base64_image, reason="fake document")

# List entries (paginated)
page = client.blacklist.list(page=1, per_page=20)
for entry in page:
    print(entry.id, entry.reason, entry.source, entry.created_at)
print(page.total, page.has_more)

# Remove an entry (un-ban)
client.blacklist.remove(entry_id=42)
```

All methods are also available on `AsyncXident` (`await client.blacklist...`).

## Error Handling

```python
from xident import (
    XidentError,          # Base for all errors
    AuthenticationError,  # 401/403
    ValidationError,      # 400
    NotFoundError,        # 404
    RateLimitError,       # 429 (has retry_after)
    ServerError,          # 5xx
    NetworkError,         # Connection failed
)

try:
    result = client.verification.init(callback_url="...")
except AuthenticationError as e:
    print(f"Bad API key: {e.error_code}")
except RateLimitError as e:
    print(f"Rate limited, retry in {e.retry_after}s")
except NetworkError as e:
    print(f"Connection failed: {e}")
except XidentError as e:
    print(f"SDK error: {e}")
```

## Context Manager

```python
# Auto-close HTTP client
with Xident(api_key="sk_live_...") as client:
    result = client.verification.init(callback_url="...")

# Async
async with AsyncXident(api_key="sk_live_...") as client:
    result = await client.verification.init(callback_url="...")
```

## Framework Examples

See the `examples/` directory for complete integrations:

- **[basic.py](examples/basic.py)** -- Pure Python
- **[flask_app.py](examples/flask_app.py)** -- Flask
- **[django_view.py](examples/django_view.py)** -- Django
- **[fastapi_app.py](examples/fastapi_app.py)** -- FastAPI (async)

## v2 breaking changes

`2.0.0` migrates `SessionResult` (what `get_result()` returns) onto the
**frozen v1 tenant result contract** -- the same shape the Go API, and every
other Xident SDK, now return. It replaces the old loose "blob" fields with
typed, always-present `checks`.

**What changed:**

- `session.id` -> `session.token`. `.id` still works as a **deprecated**
  read-only alias -- it is not removed, just superseded.
- `session.liveness_result`, `session.age_result`, `session.ocr_result`,
  `session.face_match_result` (untyped dicts) -> `session.checks.liveness`,
  `session.checks.age`, `session.checks.document`, `session.checks.face_match`
  (typed, always present, `performed`/`passed` on every one).
- `session.age_bracket()` now reads `checks.age.gate` -- and only when
  `checks.age.passed` is True. Previously it read `age_result["verified_bracket"]`
  or `age_result["estimated_age"]`.
- `session.method()` now returns `verification_mode` directly (`"full"`, `"age_check"`, `"xident_id"`, `"eu_wallet"`,
  `"document"`, `"facial"`) instead of the old `age_result["method"]` values
  (`"ml_fast"`, `"ocr"`, `"self_declaration"`).
- `session.country_code`, `session.regime`, `session.min_age`,
  `session.required_methods`, `session.remaining_attempts`,
  `session.ocr_task_id`, `session.started_at` are **removed** -- they were
  never part of the tenant-facing result contract. Document country is now
  `session.checks.document.country`.
- `client.verification.init()` gained two new optional keyword arguments:
  `verification_mode` and `liveness_difficulty` (see
  [Create Init Token](#create-init-token) above). This closes a gap where the
  SDK accepted `verification_mode` in name only -- 1.x parsed it but never sent
  it to the API.

**What did not change:** `session.is_verified()`, `session.is_failed()`,
`session.is_pending()`, `session.is_terminal()`, `session.status`,
`session.reason`, `session.external_user_id`, `session.created_at`,
`session.completed_at`, `session.expires_at`. `session.is_completed()` remains
as a deprecated alias of `is_verified()`.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=xident

# Type checking
mypy src/xident

# Linting
ruff check src/ tests/
```

## License

MIT

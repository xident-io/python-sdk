# Xident Python SDK

Official Python SDK for [Xident](https://xident.io) age and identity verification. Try it live at [demo.xident.io](https://demo.xident.io).

[![PyPI version](https://img.shields.io/pypi/v/xident.svg)](https://pypi.org/project/xident/)
[![Python versions](https://img.shields.io/pypi/pyversions/xident.svg)](https://pypi.org/project/xident/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Installation

```bash
pip install xident
```

Requires Python 3.10+.

## Quick Start

```python
from xident import Xident

client = Xident(api_key="sk_live_...")

REQUIRED_MIN_AGE = 18  # the age YOUR site requires, decided on the server

# Create an init token (server side only, with your secret key)
result = client.verification.init(
    callback_url="https://example.com/callback",
    user_id=str(current_user.id),  # required, a string: your own id for the signed-in person
    min_age=REQUIRED_MIN_AGE,   # 12 to 25, rounded up to the next band
)
print(result.verify_url)  # Redirect user here

# On your callback: read the xtk_ token from the URL, then decide server-side
session = client.verification.get_result(token_from_callback)
if (
    session.external_user_id == str(current_user.id)  # the result is this user's
    and session.proves_age(REQUIRED_MIN_AGE)         # and proves the age you need
):
    print(f"Verified! Age band: {session.checks.age.gate}+")
```

Check both: a success can belong to somebody else (a token copied from
another person's callback), and a success can prove a lower age (an 18+
result at a 21+ site) or no age at all (an ID verification).

`user_id` is a string on the wire. If your user ids are numbers, convert them
with `str()` both when you send them and when you compare
`external_user_id`, or the comparison `"42" == 42` refuses a real
verification.

> **v2.0.0 changed the shape of the verification result.** See
> [v2 breaking changes](#v2-breaking-changes) below before upgrading.

## Async Support

```python
from xident import AsyncXident

client = AsyncXident(api_key="sk_live_...")

result = await client.verification.init(
    callback_url="https://example.com/callback",
    user_id="user_42",
    min_age=18,
)

session = await client.verification.get_result("xtk_abc123")
```

## Configuration

```python
client = Xident(
    api_key="sk_live_...",       # Required: sk_live_, sk_test_, ak_live_ or ak_test_
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
    user_id="user_42",       # Required: your own identifier for the person
    min_age=18,              # Required for age_verification: 12 to 25 (see below)
    theme="dark",            # Widget theme (light, dark, system)
    locale="de",             # Widget locale
    metadata="custom_data",  # Opaque metadata string
    purpose="age_verification",  # "age_verification" (default) or "id_verification"
    verification_mode="document",  # Force document + face match, skip on-device age estimation
    liveness_difficulty="hard",    # "easy", "medium", or "hard" -- more liveness actions
    expected={"first_name": "Jane", "date_of_birth": "1990-05-14"},  # data match, see below
    mismatch_policy="report",      # or "review"
)

print(result.token)       # "xit_abc123" (init token, 10-minute TTL)
print(result.verify_url)  # Full URL to redirect user to
```

`verification_mode` composes with `min_age` rather than replacing it --
`verification_mode="document"` with `min_age=21` still enforces 21, it just
insists the proof be a document instead of letting the rule engine pick
on-device age estimation.

**Rules for `init()`.** Every setting of the session comes from this call,
which only your backend can make:

- **Server key only.** `init` needs a server key: a secret key (`sk_live_`,
  `sk_test_`) or an agent key (`ak_live_`, `ak_test_`). A public key (`pk_`)
  gets 403 `SECRET_KEY_REQUIRED`, and this client refuses one when it is built.
  Never put a server key in a browser or a mobile app.
- **`user_id`** is required. Your own identifier for the person being
  verified. It comes back on the callback and in the result.
- **`min_age`** is required for `age_verification`: a whole number from 12 to
  25. Xident rounds it up to the next of 12, 15, 18, 21 or 25 and enforces that
  band, so 19 is enforced as 21. The SDK sends the value as given.
- **`id_verification`** takes no `min_age` (leave it out, or pass 0). It always
  needs a document and a face match, so `verification_mode="facial"` cannot be
  combined with it.

The SDK checks these rules before it sends anything and raises
`ValidationError` with the same error code and message the API would answer
with (`request_id` is then `None`):

| `error_code` | When |
|---|---|
| `MISSING_USER_ID` | `user_id` is `None`, empty or only spaces |
| `INVALID_MIN_AGE` | `min_age` is missing or outside 12 to 25 for an age verification, or not 0 for an ID verification |
| `INVALID_VERIFICATION_MODE` | `purpose="id_verification"` with `verification_mode="facial"` |

The API checks the same rules again and has a few of its own, which reach you
as `ValidationError` (400) too: `INVALID_LIVENESS_DIFFICULTY` (not `easy`,
`medium` or `hard`) and `INVALID_USER_ID` (a `user_id` that looks like a
Xident key). Reusing an `Idempotency-Key` with a different body gets 422
`IDEMPOTENCY_KEY_MISMATCH`.

To make a test session fail on purpose, use a test key and a `user_id` that
ends in `+fail`.

After verification the widget redirects the browser back to `callback_url` with
query parameters: `status` (`success` | `failed` | `canceled`, the same three
words the result endpoint uses), `token` (the **result** token `xtk_...`, which
is different from the init token `xit_...`), and `user_id`.
Always re-verify the result server-side with `get_result()` — never trust the
callback query parameters, and never take the user from the `user_id` in the
URL: anyone can edit a URL. Grant access only when both hold:

- `session.external_user_id` is the user your backend started the
  verification for (from your own session or login);
- `session.proves_age(REQUIRED_MIN_AGE)`: `verified` is true and the age band
  (`checks.age.gate`) is present and at least the age your backend requires.
  An ID verification result has no band and proves no age. It does not need
  `checks.age.passed`: a returning user who reuses an age proven earlier on
  their Xident ID (`verification_type` `xident_id`) gets a verified result
  with the band, but no new age check ran in that session.

A result from a test key carries `test: true` (`session.test`): the session
settled at once with no real check, yet it is verified and carries the band.
`proves_age()` refuses it. In local development with a test key you can opt in
with `session.proves_age(REQUIRED_MIN_AGE, allow_test=True)`; never do that in
production code.

### Get Verification Result

```python
session = client.verification.get_result("xtk_abc123")

session.is_verified()    # True if completed successfully
session.is_failed()      # True if verification failed
session.is_pending()     # True if still in progress
session.is_terminal()    # True if no more changes possible

session.proves_age(21)   # True only if verified, not a test-key result, AND checks.age.gate >= 21
session.test             # True for a test-key result: it grants nothing
session.external_user_id # the user_id your backend sent to init: compare it with your user
session.age_bracket()    # the band proved (e.g. 21), by the same rule as proves_age(): verified, not a
                         # test-key result, checks.age.gate present; None for id_verification
session.method()         # "full" | "age_check" | "xident_id" | "eu_wallet"
session.status           # SessionStatus.SUCCESS
session.reason           # "" on success; e.g. "age_below_threshold" on failure
session.token            # "xtk_abc123" -- the result token, primary identifier

# Full detail on what ran and what passed:
session.checks.liveness.performed   # bool
session.checks.liveness.passed      # bool
session.checks.age.performed        # bool
session.checks.age.passed           # bool
session.checks.age.gate             # 12 / 15 / 18 / 21 / 25, or None (None for id_verification)
session.checks.document.performed   # bool
session.checks.document.passed      # bool
session.checks.document.document_type  # "passport", "drivers_license", or None
session.checks.document.country     # ISO 3166-1 alpha-2, or None
session.checks.face_match.performed  # bool
session.checks.face_match.passed     # bool
session.checks.data_match            # DataMatchCheck or None unless you sent expected=
```

### Data Match

Send what you already know about the user and let the document confirm it.
The values travel server to server and never reach the browser; the result
carries only verdicts, one per field you asked about.

```python
result = client.verification.init(
    callback_url="https://example.com/callback",
    user_id="user_42",
    purpose="id_verification",  # a data match needs a document
    expected={
        "first_name": "Jane",
        "last_name": "Smith",
        "date_of_birth": "1990-05-14",  # YYYY-MM-DD
        "nationality": "GB",            # ISO 3166-1 alpha-2
    },
    mismatch_policy="review",  # "report" (default): reported, outcome unchanged
                               # "review": any mismatch goes to your review queue (reason data_mismatch)
)

# Later, on the result:
dm = session.checks.data_match
if dm is not None and dm.passed:
    ...  # every field you sent matched the document
# dm.fields.date_of_birth is "match", "mismatch", "not_on_document" or None
```

`checks.data_match` is `None` when the check was not performed (no
`expected`, no document read). Gate on `dm is not None and dm.passed`; that
fails closed.

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
print(event["data"])  # the same result get_result() returns, as a dict

# Apply the callback's rules to it before you grant anything:
from xident import SessionResult
result = SessionResult.from_dict(event["data"])
if result.external_user_id == str(your_user_id) and result.proves_age(REQUIRED_MIN_AGE):
    ...

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
    result = client.verification.init(callback_url="...", user_id="user_42", min_age=18)
except ValidationError as e:
    print(f"Bad parameter: {e.error_code}")  # e.g. INVALID_MIN_AGE
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
    result = client.verification.init(callback_url="...", user_id="user_42", min_age=18)

# Async
async with AsyncXident(api_key="sk_live_...") as client:
    result = await client.verification.init(callback_url="...", user_id="user_42", min_age=18)
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

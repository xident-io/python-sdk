# Xident Python SDK

Official Python SDK for [Xident](https://xident.io) age and identity verification.

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
    min_age=18,              # Age threshold (12, 15, 18, 21, 25)
    success_url="...",       # Override redirect on success
    failed_url="...",        # Override redirect on failure
    user_id="user_42",       # Your user identifier
    theme="dark",            # Widget theme (light, dark, auto)
    locale="de",             # Widget locale
    metadata="custom_data",  # Opaque metadata string
)

print(result.token)       # "xit_abc123"
print(result.verify_url)  # Full URL to redirect user to
```

### Get Verification Result

```python
session = client.verification.get_result("xtk_abc123")

session.is_verified()    # True if completed successfully
session.is_failed()      # True if verification failed
session.is_pending()     # True if still in progress
session.is_terminal()    # True if no more changes possible

session.age_bracket()    # 18 (verified age threshold)
session.method()         # "ml_fast", "ocr", etc.
session.country_code     # "US", "DE", etc.
session.status           # SessionStatus.COMPLETED
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

print(event["type"])  # "session.completed"
print(event["data"])  # Event payload dict

# Or verify signature only
client.webhooks.verify_signature(payload, signature, secret)
```

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

"""
Xident Python SDK -- Basic Integration Example

This shows the full verification flow:
1. Create init token using your SECRET key (server-side only)
2. Redirect user to verification widget
3. Handle callback and verify result using your SECRET key

IMPORTANT: Use your SECRET key (sk_live_... or sk_test_...) for server-side SDK calls.
Only your backend may create a verification: the API refuses a public key (pk_...)
with 403 SECRET_KEY_REQUIRED. Never put the secret key in a browser or a mobile
app; the browser only opens the verify_url your backend gets back.

Usage:
    XIDENT_SECRET_KEY=sk_test_xxx python examples/basic.py
"""

import os
import sys

from xident import Xident, XidentError

# Get the secret key from environment
secret_key = os.environ.get("XIDENT_SECRET_KEY")
if not secret_key:
    print("ERROR: Set XIDENT_SECRET_KEY environment variable")
    print("Example: XIDENT_SECRET_KEY=sk_test_xxx python examples/basic.py")
    sys.exit(1)

# Initialize the client
client = Xident(api_key=secret_key)

# A test key's result carries test: true and proves nothing, so proves_age()
# refuses it. This local script may accept it when you ask for that
# explicitly, and never with a live key.
ALLOW_TEST_RESULTS = os.environ.get("XIDENT_ALLOW_TEST_RESULTS") == "1"
if ALLOW_TEST_RESULTS and secret_key.startswith(("sk_live_", "ak_live_")):
    print("ERROR: XIDENT_ALLOW_TEST_RESULTS=1 is for test keys only")
    sys.exit(1)

# The age YOUR site requires, decided here on the server and never taken from
# the browser. 12 to 25; Xident rounds it up to the next of 12, 15, 18, 21 or
# 25 (19 is enforced as 21).
REQUIRED_MIN_AGE = 18

# Your own identifier for the person, from your session or login. It must be
# the same value when the person comes back to the callback.
USER_ID = "demo_user_1"

# ---- Step 1: Create Init Token ----
try:
    result = client.verification.init(
        callback_url="https://example.com/callback",
        user_id=USER_ID,  # required
        min_age=REQUIRED_MIN_AGE,
    )
    print(f"Init token: {result.token}")
    print(f"Verify URL: {result.verify_url}")
    print("Redirect the user to the verify URL to start verification.")
except XidentError as e:
    print(f"Error creating init token: {e}")
    sys.exit(1)

# ---- Step 2: After user returns, verify result ----
# The user will be redirected back to your callback_url with ?token=xtk_xxx
# ALWAYS verify server-side -- never trust URL params alone, and never take the
# user id from the callback URL: anyone can edit it.

demo_token = "xtk_demo_token"  # Replace with actual token from callback
try:
    session = client.verification.get_result(demo_token)

    if session.is_pending():
        print("Verification still in progress...")
    elif session.external_user_id != USER_ID:
        # A real success for somebody else: a token copied from another
        # person's callback. Never grant anything on it.
        print("This result belongs to another user")
    elif session.proves_age(REQUIRED_MIN_AGE, allow_test=ALLOW_TEST_RESULTS):
        # Verified, and its age band covers your age. An ID
        # verification (no age band) or an 18+ result at a 21+ site is False.
        print(f"Verified! Age band: {session.checks.age.gate}+")
        print(f"Method: {session.method()}")  # "full", "age_check", "xident_id", ...
        if session.checks.document.performed:
            print(f"Document country: {session.checks.document.country}")
    else:
        print(f"Not verified for {REQUIRED_MIN_AGE}+ (status {session.status.value})")
except XidentError as e:
    print(f"Error checking result: {e}")

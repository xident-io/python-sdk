"""
Xident Python SDK -- Basic Integration Example

This shows the full verification flow:
1. Create init token using your SECRET key (server-side only)
2. Redirect user to verification widget
3. Handle callback and verify result using your SECRET key

IMPORTANT: Use your SECRET key (sk_live_... or sk_test_...) for server-side SDK calls.
The public key (pk_live_...) is for the JS SDK embedded in your frontend only.

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

# ---- Step 1: Create Init Token ----
try:
    result = client.verification.init(
        callback_url="https://example.com/callback",
        min_age=18,
        user_id="demo_user_1",
    )
    print(f"Init token: {result.token}")
    print(f"Verify URL: {result.verify_url}")
    print("Redirect the user to the verify URL to start verification.")
except XidentError as e:
    print(f"Error creating init token: {e}")
    sys.exit(1)

# ---- Step 2: After user returns, verify result ----
# The user will be redirected back to your callback_url with ?token=xtk_xxx
# ALWAYS verify server-side -- never trust URL params alone.

demo_token = "xtk_demo_token"  # Replace with actual token from callback
try:
    session = client.verification.get_result(demo_token)

    if session.is_verified():
        print(f"Verified! Age bracket: {session.age_bracket()}+")
        print(f"Method: {session.method()}")
        print(f"Country: {session.country_code}")
    elif session.is_failed():
        print("Verification failed")
    elif session.is_pending():
        print("Verification still in progress...")
except XidentError as e:
    print(f"Error checking result: {e}")

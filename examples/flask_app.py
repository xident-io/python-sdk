"""
Xident Python SDK -- Flask Integration Example

Usage:
    pip install flask xident
    XIDENT_SECRET_KEY=sk_test_xxx FLASK_SECRET_KEY=change-me flask run --app examples/flask_app
"""

import os
import secrets

from flask import Flask, jsonify, redirect, request, session

from xident import Xident, XidentError

app = Flask(__name__)
# Flask signs its session cookie with this key, so a visitor cannot forge the
# user id kept in it.
app.secret_key = os.environ["FLASK_SECRET_KEY"]

xident_client = Xident(api_key=os.environ["XIDENT_SECRET_KEY"])

# The age YOUR site requires, decided here on the server and never taken from
# the request. 12 to 25; Xident rounds it up to the next of 12, 15, 18, 21 or
# 25 (19 is enforced as 21).
REQUIRED_MIN_AGE = 18


def current_user_id() -> str:
    """Your own identifier for the signed-in person.

    Replace this with your login. The example has no login, so it gives each
    visitor a random id in Flask's signed session. Xident requires a user_id
    on every init and returns it in the result as external_user_id.
    """
    if "user_id" not in session:
        session["user_id"] = "user-" + secrets.token_hex(8)
    return str(session["user_id"])


@app.route("/verify")
def start_verification():
    """Start verification -- redirect user to Xident widget."""
    try:
        result = xident_client.verification.init(
            callback_url=request.url_root.rstrip("/") + "/verify/callback",
            user_id=current_user_id(),
            min_age=REQUIRED_MIN_AGE,
            theme="system",
        )
        return redirect(result.verify_url)
    except XidentError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/verify/callback")
def verification_callback():
    """Handle callback -- verify result server-side.

    Decide only from the result the secret key reads, never from the
    ``status`` or ``user_id`` in the URL: anyone can edit a URL.
    """
    token = request.args.get("token")
    if not token:
        return jsonify({"error": "Missing token"}), 400

    try:
        result = xident_client.verification.get_result(token)
    except XidentError as e:
        return jsonify({"error": str(e)}), 500

    if result.is_pending():
        return jsonify({"status": "in_progress"}), 202

    # A success that belongs to somebody else (a token copied from another
    # person's callback) must not verify this visitor.
    if result.external_user_id != current_user_id():
        return jsonify({"error": "This verification belongs to another user"}), 403

    # Success, the age check passed, and its band covers REQUIRED_MIN_AGE. An
    # ID verification result (no age band) or an 18+ result at a 21+ site is
    # not enough.
    if result.proves_age(REQUIRED_MIN_AGE):
        return jsonify({"status": "verified", "age_bracket": result.age_bracket()})
    return jsonify({"status": "failed"}), 403


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle Xident webhook events."""
    payload = request.get_data(as_text=True)
    signature = request.headers.get("X-Xident-Signature", "")
    webhook_secret = os.environ.get("XIDENT_WEBHOOK_SECRET", "")

    try:
        event = xident_client.webhooks.construct_event(payload, signature, webhook_secret)
        print(f"Webhook event: {event['type']}")
        # Handle event...
        return jsonify({"status": "ok"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

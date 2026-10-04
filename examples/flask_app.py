"""
Xident Python SDK -- Flask Integration Example

Usage:
    pip install flask xident
    XIDENT_SECRET_KEY=sk_test_xxx flask run --app examples/flask_app
"""

import os

from flask import Flask, jsonify, redirect, request

from xident import Xident, XidentError

app = Flask(__name__)

xident_client = Xident(api_key=os.environ["XIDENT_SECRET_KEY"])


def current_user_id() -> str:
    """Your own identifier for the signed-in person.

    Replace this with your session or auth lookup. Xident requires a user_id
    on every init and returns it on the callback and in the result.
    """
    return "user_42"


@app.route("/verify")
def start_verification():
    """Start verification -- redirect user to Xident widget."""
    try:
        result = xident_client.verification.init(
            callback_url=request.url_root.rstrip("/") + "/verify/callback",
            user_id=current_user_id(),
            min_age=18,  # 12 to 25, rounded up to the next band (19 is enforced as 21)
            theme="system",
        )
        return redirect(result.verify_url)
    except XidentError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/verify/callback")
def verification_callback():
    """Handle callback -- verify result server-side."""
    token = request.args.get("token")
    if not token:
        return jsonify({"error": "Missing token"}), 400

    try:
        session = xident_client.verification.get_result(token)

        if session.is_verified():
            return jsonify({
                "status": "verified",
                "age_bracket": session.age_bracket(),
            })
        elif session.is_failed():
            return jsonify({"status": "failed"}), 403
        else:
            return jsonify({"status": "in_progress"}), 202
    except XidentError as e:
        return jsonify({"error": str(e)}), 500


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

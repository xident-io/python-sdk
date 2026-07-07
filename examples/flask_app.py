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


@app.route("/verify")
def start_verification():
    """Start verification -- redirect user to Xident widget."""
    try:
        result = xident_client.verification.init(
            callback_url=request.url_root.rstrip("/") + "/verify/callback",
            min_age=18,
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

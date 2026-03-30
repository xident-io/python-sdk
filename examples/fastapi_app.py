"""
Xident Python SDK -- FastAPI Integration Example (Async)

Usage:
    pip install fastapi uvicorn xident
    XIDENT_SECRET_KEY=sk_test_xxx uvicorn examples.fastapi_app:app
"""

import os

from fastapi import FastAPI, Header, Request
from fastapi.responses import RedirectResponse

from xident import AsyncXident, XidentError

app = FastAPI(title="Xident FastAPI Example")

# Use AsyncXident for non-blocking I/O
xident_client = AsyncXident(api_key=os.environ["XIDENT_SECRET_KEY"])


@app.on_event("shutdown")
async def shutdown():
    """Clean up the async client on app shutdown."""
    await xident_client.aclose()


@app.get("/verify")
async def start_verification(request: Request):
    """Start verification -- redirect user to Xident widget."""
    try:
        result = await xident_client.verification.init(
            callback_url=str(request.url_for("verification_callback")),
            min_age=18,
            theme="auto",
        )
        return RedirectResponse(url=result.verify_url)
    except XidentError as e:
        return {"error": str(e)}


@app.get("/verify/callback")
async def verification_callback(token: str):
    """Handle callback -- verify result server-side."""
    try:
        session = await xident_client.verification.get_result(token)

        if session.is_verified():
            return {
                "status": "verified",
                "age_bracket": session.age_bracket(),
                "method": session.method(),
                "country": session.country_code,
            }
        elif session.is_failed():
            return {"status": "failed"}
        else:
            return {"status": "pending"}
    except XidentError as e:
        return {"error": str(e)}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_xident_signature: str = Header(""),
):
    """Handle Xident webhook events (async)."""
    payload = await request.body()
    webhook_secret = os.environ.get("XIDENT_WEBHOOK_SECRET", "")

    try:
        event = xident_client.webhooks.construct_event(
            payload, x_xident_signature, webhook_secret
        )

        match event["type"]:
            case "session.completed":
                # Process completed verification
                pass
            case "session.failed":
                # Handle failed verification
                pass

        return {"status": "ok"}
    except ValueError as e:
        return {"error": f"Invalid signature: {e}"}

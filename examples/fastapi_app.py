"""
Xident Python SDK -- FastAPI Integration Example (Async)

Usage:
    pip install fastapi uvicorn itsdangerous xident
    XIDENT_SECRET_KEY=sk_test_xxx SESSION_SECRET=change-me uvicorn examples.fastapi_app:app
"""

import os
import secrets

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from xident import AsyncXident, XidentError

app = FastAPI(title="Xident FastAPI Example")
# Starlette signs the session cookie with this key, so a visitor cannot forge
# the user id kept in it.
app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET"])

# Use AsyncXident for non-blocking I/O
xident_client = AsyncXident(api_key=os.environ["XIDENT_SECRET_KEY"])

# The age YOUR site requires, decided here on the server and never taken from
# the request. 12 to 25; Xident rounds it up to the next of 12, 15, 18, 21 or
# 25 (19 is enforced as 21).
REQUIRED_MIN_AGE = 18


@app.on_event("shutdown")
async def shutdown():
    """Clean up the async client on app shutdown."""
    await xident_client.aclose()


def current_user_id(request: Request) -> str:
    """Your own identifier for the signed-in person.

    Replace this with your login. The example has no login, so it gives each
    visitor a random id in the signed session. Xident requires a user_id on
    every init and returns it in the result as external_user_id.
    """
    if "user_id" not in request.session:
        request.session["user_id"] = "user-" + secrets.token_hex(8)
    return str(request.session["user_id"])


@app.get("/verify")
async def start_verification(request: Request):
    """Start verification -- redirect user to Xident widget.

    This pilot integration forces the document path: `verification_mode=
    "document"` skips the rule engine's on-device age-estimation option and
    always requires document + face match. Drop the argument (or pass
    "auto") to let the rule engine choose.
    """
    try:
        result = await xident_client.verification.init(
            callback_url=str(request.url_for("verification_callback")),
            user_id=current_user_id(request),
            min_age=REQUIRED_MIN_AGE,
            theme="system",
            verification_mode="document",
        )
        return RedirectResponse(url=result.verify_url)
    except XidentError as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/verify/callback")
async def verification_callback(request: Request, token: str):
    """Handle callback -- verify result server-side.

    Decide only from the result the secret key reads, never from the
    ``status`` or ``user_id`` in the URL: anyone can edit a URL.
    """
    try:
        result = await xident_client.verification.get_result(token)
    except XidentError as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    if result.is_pending():
        return JSONResponse({"status": "pending"}, status_code=202)

    # A success that belongs to somebody else (a token copied from another
    # person's callback) must not verify this visitor.
    if result.external_user_id != current_user_id(request):
        return JSONResponse({"error": "This verification belongs to another user"}, status_code=403)

    # Verified, and its age band covers REQUIRED_MIN_AGE. An
    # ID verification result (no age band) or an 18+ result at a 21+ site is
    # not enough.
    if result.proves_age(REQUIRED_MIN_AGE):
        return {
            "status": "verified",
            "age_bracket": result.checks.age.gate,
            "method": result.method(),  # "full", "age_check", "xident_id", ...
            "document_country": result.checks.document.country,
        }
    return JSONResponse({"status": "failed"}, status_code=403)


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
            # "session.completed" is the pre-July-2026 name; an endpoint
            # registered before then still receives it.
            case "session.success" | "session.completed":
                # event["data"] is the same result get_result() returns.
                # Apply the callback's rules: match data["external_user_id"]
                # to your user, and use SessionResult.from_dict(
                # event["data"]).proves_age(REQUIRED_MIN_AGE) for the age.
                pass
            case "session.failed":
                # Handle failed verification
                pass

        return {"status": "ok"}
    except ValueError as e:
        return {"error": f"Invalid signature: {e}"}

"""
Xident Python SDK -- Django Integration Example

Add these views to your Django project:
1. Add URL patterns to urls.py
2. Configure XIDENT_SECRET_KEY in settings.py
3. Use Django REST Framework or a dedicated webhook URL with signature verification

Usage in urls.py:
    from . import views
    urlpatterns = [
        path("verify/", views.start_verification, name="verify"),
        path("verify/callback/", views.verification_callback, name="verify_callback"),
        path("webhook/", views.webhook, name="xident_webhook"),
    ]
"""

import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

from xident import Xident, XidentError

# Initialize once -- reuse across requests
xident_client = Xident(
    api_key=getattr(settings, "XIDENT_SECRET_KEY", os.environ["XIDENT_SECRET_KEY"])
)

# The age YOUR site requires, decided here on the server and never taken from
# the request. 12 to 25; Xident rounds it up to the next of 12, 15, 18, 21 or
# 25 (19 is enforced as 21).
REQUIRED_MIN_AGE = 18


@login_required
@require_GET
def start_verification(request: HttpRequest) -> HttpResponse:
    """Start verification -- redirect user to Xident widget.

    user_id is required on every init, so this view needs a signed-in user.
    """
    try:
        callback_url = request.build_absolute_uri("/verify/callback/")
        result = xident_client.verification.init(
            callback_url=callback_url,
            user_id=str(request.user.pk),
            min_age=REQUIRED_MIN_AGE,
            theme="system",
        )
        return redirect(result.verify_url)
    except XidentError:
        return JsonResponse({"error": "Failed to start verification"}, status=500)


@login_required
@require_GET
def verification_callback(request: HttpRequest) -> HttpResponse:
    """Handle callback -- verify result server-side.

    Decide only from the result the secret key reads, never from the
    ``status`` or ``user_id`` in the URL: anyone can edit a URL. The result
    must belong to the signed-in user, and must prove REQUIRED_MIN_AGE.
    """
    token = request.GET.get("token")
    if not token:
        return JsonResponse({"error": "Missing token"}, status=400)

    try:
        session = xident_client.verification.get_result(token)
    except XidentError:
        return JsonResponse({"error": "Verification check failed"}, status=500)

    if session.is_pending():
        return JsonResponse({"status": "in_progress"}, status=202)

    # A success that belongs to somebody else (a token copied from another
    # person's callback) must not verify this account.
    if session.external_user_id != str(request.user.pk):
        return JsonResponse({"error": "This verification belongs to another user"}, status=403)

    # Success, the age check passed, and its band covers REQUIRED_MIN_AGE. An
    # ID verification result (no age band) or an 18+ result at a 21+ site is
    # not enough.
    if session.proves_age(REQUIRED_MIN_AGE):
        request.user.age_verified = True  # type: ignore[attr-defined]
        request.user.age_bracket = session.age_bracket()  # type: ignore[attr-defined]
        request.user.save()  # type: ignore[attr-defined]
        return redirect("/verify/success/")
    return redirect("/verify/failed/")


@require_POST
def webhook(request: HttpRequest) -> HttpResponse:
    """Handle Xident webhook events.

    NOTE: Webhooks are authenticated via HMAC signature, not CSRF tokens.
    In production, configure your web server or middleware to skip CSRF
    for this endpoint, or use Django REST Framework with authentication classes.
    The HMAC signature verification in construct_event() provides the
    authentication guarantee.
    """
    payload = request.body.decode("utf-8")
    signature = request.META.get("HTTP_X_XIDENT_SIGNATURE", "")
    webhook_secret = getattr(settings, "XIDENT_WEBHOOK_SECRET", "")

    try:
        event = xident_client.webhooks.construct_event(payload, signature, webhook_secret)

        # "session.completed" is the pre-July-2026 name; an endpoint
        # registered before then still receives it.
        if event["type"] in ("session.success", "session.completed"):
            # event["data"] is the same result get_result() returns. Apply
            # the callback's rules: match data["external_user_id"] to your
            # user, and use SessionResult.from_dict(event["data"]).proves_age(
            # REQUIRED_MIN_AGE) for the age.
            pass
        elif event["type"] == "session.failed":
            # Handle failed verification
            pass

        return JsonResponse({"status": "ok"})
    except ValueError:
        return JsonResponse({"error": "Invalid signature"}, status=400)

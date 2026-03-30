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
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

from xident import Xident, XidentError

# Initialize once -- reuse across requests
xident_client = Xident(api_key=getattr(settings, "XIDENT_SECRET_KEY", os.environ["XIDENT_SECRET_KEY"]))


@require_GET
def start_verification(request: HttpRequest) -> HttpResponse:
    """Start verification -- redirect user to Xident widget."""
    try:
        callback_url = request.build_absolute_uri("/verify/callback/")
        result = xident_client.verification.init(
            callback_url=callback_url,
            min_age=18,
            user_id=str(request.user.pk) if request.user.is_authenticated else None,
            theme="auto",
        )
        return redirect(result.verify_url)
    except XidentError:
        return JsonResponse({"error": "Failed to start verification"}, status=500)


@require_GET
def verification_callback(request: HttpRequest) -> HttpResponse:
    """Handle callback -- verify result server-side."""
    token = request.GET.get("token")
    if not token:
        return JsonResponse({"error": "Missing token"}, status=400)

    try:
        session = xident_client.verification.get_result(token)

        if session.is_verified():
            # Store verification in your database
            if request.user.is_authenticated:
                request.user.age_verified = True  # type: ignore[attr-defined]
                request.user.age_bracket = session.age_bracket()  # type: ignore[attr-defined]
                request.user.save()  # type: ignore[attr-defined]
            return redirect("/verify/success/")
        elif session.is_failed():
            return redirect("/verify/failed/")
        else:
            return JsonResponse({"status": "in_progress"}, status=202)
    except XidentError:
        return JsonResponse({"error": "Verification check failed"}, status=500)


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

        if event["type"] == "session.completed":
            # Process completed verification
            pass
        elif event["type"] == "session.failed":
            # Handle failed verification
            pass

        return JsonResponse({"status": "ok"})
    except ValueError:
        return JsonResponse({"error": "Invalid signature"}, status=400)

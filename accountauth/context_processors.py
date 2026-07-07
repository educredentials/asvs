from django.conf import settings


def oidc_enabled(request):
    """Expose whether SURFconext OIDC login is configured, for templates."""
    return {"OIDC_ENABLED": settings.OIDC_ENABLED}

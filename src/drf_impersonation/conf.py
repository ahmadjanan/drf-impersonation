from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

DEFAULTS: dict[str, Any] = {
    "READ_ONLY": True,
    "SIGNALS": True,
    "OPENAPI": True,
}


def get_setting(name: str) -> Any:
    """Read a key from ``settings.DRF_IMPERSONATION``, falling back to ``DEFAULTS``.

    Read on every call, so ``override_settings`` works in tests."""
    configured = getattr(settings, "DRF_IMPERSONATION", {})
    unknown = set(configured) - set(DEFAULTS)
    if unknown:
        raise ImproperlyConfigured(f"Unknown DRF_IMPERSONATION keys: {', '.join(sorted(unknown))}")
    return configured.get(name, DEFAULTS[name])

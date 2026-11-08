from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

DEFAULTS: dict[str, Any] = {
    "READ_ONLY": True,
    "SIGNALS": True,
    "OPENAPI": True,
}


def unknown_keys() -> list[str]:
    configured = getattr(settings, "DRF_IMPERSONATION", {})
    return sorted(set(configured) - set(DEFAULTS))


def get_setting(name: str) -> Any:
    """Read a key from ``settings.DRF_IMPERSONATION``, falling back to ``DEFAULTS``.

    Read on every call, so ``override_settings`` works in tests."""
    unknown = unknown_keys()
    if unknown:
        raise ImproperlyConfigured(f"Unknown DRF_IMPERSONATION keys: {', '.join(unknown)}")
    return getattr(settings, "DRF_IMPERSONATION", {}).get(name, DEFAULTS[name])

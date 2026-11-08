from typing import Any

from django.core.checks import Error, register

from .conf import DEFAULTS, unknown_keys


@register()
def check_settings(app_configs: Any, **kwargs: Any) -> list[Error]:
    unknown = unknown_keys()
    if not unknown:
        return []
    return [
        Error(
            f"Unknown DRF_IMPERSONATION keys: {', '.join(unknown)}",
            hint=f"Valid keys: {', '.join(DEFAULTS)}.",
            id="drf_impersonation.E001",
        )
    ]

from typing import Any

from django.core.checks import Error, register

from .conf import unknown_keys


@register()
def check_settings(app_configs: Any, **kwargs: Any) -> list[Error]:
    unknown = unknown_keys()
    if not unknown:
        return []
    return [
        Error(
            f"Unknown DRF_IMPERSONATION keys: {', '.join(unknown)}",
            hint="Valid keys are READ_ONLY, SIGNALS and OPENAPI.",
            id="drf_impersonation.E001",
        )
    ]

from django.apps import AppConfig


class DrfImpersonationConfig(AppConfig):
    name = "drf_impersonation"
    verbose_name = "DRF Impersonation"

    def ready(self) -> None:
        try:
            import drf_spectacular  # noqa: F401
        except ImportError:  # pragma: no cover
            return
        # Importing registers the extension. It can't live in authentication.py, because DRF
        # imports auth classes while rest_framework.views is still loading.
        from . import openapi  # noqa: F401

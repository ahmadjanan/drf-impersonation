import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework.request import Request

from .conf import get_setting
from .signals import user_impersonated

logger = logging.getLogger("drf_impersonation")


class ImpersonationMixin:
    """Let a permitted user act as another user by sending a header.

    Mix in before any DRF authentication class. The base class authenticates the
    actor as usual. If the request carries the impersonation header and the actor
    may impersonate, the target becomes ``request.user`` and the actor is kept on
    ``request.impersonator``.
    """

    impersonation_header: str = "X-Impersonate-User"
    impersonation_lookup_fields: tuple[str, ...] = ("pk",)

    def authenticate(self, request: Request) -> tuple[Any, Any] | None:
        result = super().authenticate(request)  # type: ignore[misc]
        if result is None:
            return None

        actor, auth = result
        request.impersonator = None
        target = self.get_impersonation_target(request, actor)
        if target is None:
            return actor, auth

        request.impersonator = actor
        self.on_impersonate(request, actor, target)
        if get_setting("SIGNALS"):
            user_impersonated.send(sender=type(self), request=request, actor=actor, target=target)
        return target, auth

    def get_impersonation_target(self, request: Request, actor: Any) -> Any | None:
        """Return the user to impersonate, or None when there is no header or the
        actor may not impersonate. Raise NotFound when no permitted user matches."""
        directive = request.headers.get(self.impersonation_header)
        if not directive or not self.can_impersonate(request, actor):
            return None

        # Checked before the lookup, so the response is the same whether or not the target exists.
        if get_setting("READ_ONLY") and request.method not in SAFE_METHODS:
            raise PermissionDenied("Impersonated requests are read-only")

        query = self.build_lookup(directive)
        target = None
        if query:
            target = get_user_model()._default_manager.filter(query).exclude(pk=actor.pk).first()

        # Same error for missing and forbidden targets, so the header can't probe for users.
        if target is None or not self.can_impersonate_target(request, actor, target):
            raise NotFound("Impersonation target not found")
        return target

    def build_lookup(self, value: str) -> Q:
        """OR together every lookup field the value is valid for, so one header can
        carry e.g. either a UUID or an email."""
        model = get_user_model()
        query = Q()
        for lookup in self.impersonation_lookup_fields:
            name = lookup.split("__")[0]
            field = model._meta.pk if name == "pk" else model._meta.get_field(name)
            try:
                query |= Q(**{lookup: field.to_python(value)})
            except ValidationError:
                continue
        return query

    def can_impersonate(self, request: Request, actor: Any) -> bool:
        return getattr(actor, "is_superuser", False)

    def can_impersonate_target(self, request: Request, actor: Any, target: Any) -> bool:
        # Base auth classes refuse inactive users; impersonation must not bypass that.
        if not getattr(target, "is_active", True):
            return False
        # A non-superuser must never gain superuser rights by impersonating one.
        return getattr(actor, "is_superuser", False) or not getattr(target, "is_superuser", False)

    def on_impersonate(self, request: Request, actor: Any, target: Any) -> None:
        logger.warning(
            "IMPERSONATION actor=%s target=%s %s %s",
            actor.pk,
            target.pk,
            request.method,
            request.path,
        )


class ImpersonationTokenAuthentication(ImpersonationMixin, TokenAuthentication):
    """DRF's TokenAuthentication with impersonation."""

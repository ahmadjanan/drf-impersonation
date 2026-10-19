from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension

from .conf import get_setting

SCHEME_NAME = "impersonation"


class ImpersonationScheme(OpenApiAuthenticationExtension):
    """Document the impersonation header as an optional addition to the base class's scheme.

    Each base requirement is offered twice, alone and together with the header, so clients see
    that the header is optional.
    """

    target_class = "drf_impersonation.authentication.ImpersonationMixin"
    match_subclasses = True
    priority = 1

    @classmethod
    def _matches(cls, target: Any) -> bool:
        return bool(get_setting("OPENAPI")) and super()._matches(target)

    def __init__(self, target: Any) -> None:
        super().__init__(target)
        # The extension the base class (Token, JWT, ...) would get without the mixin.
        self.base = next(
            (
                extension(target)
                for extension in sorted(self._registry, key=lambda e: e.priority, reverse=True)
                if not issubclass(extension, ImpersonationScheme) and extension._matches(target)
            ),
            None,
        )
        if self.base is None:
            self.name = []
        else:
            base_names = [self.base.name] if isinstance(self.base.name, str) else self.base.name
            self.name = [*base_names, SCHEME_NAME]

    def get_security_requirement(self, auto_schema: Any) -> Any:
        # Without a base scheme, drf-spectacular can't describe the actor's credentials either.
        if self.base is None:
            return None
        requirement = self.base.get_security_requirement(auto_schema)
        if requirement is None:
            return None
        alternatives = [requirement] if isinstance(requirement, dict) else requirement
        return [*alternatives, *({**alt, SCHEME_NAME: []} for alt in alternatives)]

    def get_security_definition(self, auto_schema: Any) -> Any:
        if self.base is None:
            return []
        definition = self.base.get_security_definition(auto_schema)
        definitions = [definition] if isinstance(self.base.name, str) else definition
        description = (
            "Optional. Run the request as the user this value identifies. Only callers allowed "
            "to impersonate can use it."
        )
        if get_setting("READ_ONLY"):
            description += (
                " Only safe methods (GET, HEAD, OPTIONS) are allowed while impersonating."
            )
        header = {
            "type": "apiKey",
            "in": "header",
            "name": self.target.impersonation_header,
            "description": description,
        }
        return [*definitions, header]

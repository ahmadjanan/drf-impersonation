from django.urls import path
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.utils import extend_schema
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_impersonation.authentication import ImpersonationMixin, ImpersonationTokenAuthentication


class Unknown(ImpersonationMixin):
    """A base class drf-spectacular has no scheme for."""


class Silent(TokenAuthentication):
    """A base class whose scheme declares no security requirement."""


class SilentScheme(OpenApiAuthenticationExtension):
    target_class = Silent
    name = "silent"
    match_subclasses = True

    def get_security_requirement(self, auto_schema):
        return None

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer"}


class ImpersonationSilent(ImpersonationMixin, Silent):
    pass


def make_schema(*classes):
    class View(APIView):
        authentication_classes = classes
        permission_classes = [IsAuthenticated]

        @extend_schema(responses={204: None})
        def get(self, request):
            return Response()  # pragma: no cover

    return SchemaGenerator(patterns=[path("me/", View.as_view())]).get_schema(public=True)


def test_header_documented_as_optional():
    schema = make_schema(ImpersonationTokenAuthentication)
    assert schema["paths"]["/me/"]["get"]["security"] == [
        {"tokenAuth": []},
        {"tokenAuth": [], "impersonation": []},
    ]
    schemes = schema["components"]["securitySchemes"]
    assert schemes["tokenAuth"]["type"] == "apiKey"
    assert schemes["impersonation"]["name"] == "X-Impersonate-User"
    assert "Only safe methods" in schemes["impersonation"]["description"]


def test_custom_header_and_writes_allowed(settings):
    settings.DRF_IMPERSONATION = {"READ_ONLY": False}

    class ActAs(ImpersonationTokenAuthentication):
        impersonation_header = "X-Act-As"

    impersonation = make_schema(ActAs)["components"]["securitySchemes"]["impersonation"]
    assert impersonation["name"] == "X-Act-As"
    assert "Only safe methods" not in impersonation["description"]


def test_disabled_falls_back_to_base_scheme(settings):
    settings.DRF_IMPERSONATION = {"OPENAPI": False}
    schema = make_schema(ImpersonationTokenAuthentication)
    assert schema["paths"]["/me/"]["get"]["security"] == [{"tokenAuth": []}]
    assert "impersonation" not in schema["components"]["securitySchemes"]


def test_unknown_base_class_documents_nothing():
    schema = make_schema(Unknown, TokenAuthentication)
    assert schema["paths"]["/me/"]["get"]["security"] == [{"tokenAuth": []}]
    assert "impersonation" not in schema["components"]["securitySchemes"]


def test_base_without_requirement_adds_none():
    schema = make_schema(ImpersonationSilent, TokenAuthentication)
    assert schema["paths"]["/me/"]["get"]["security"] == [{"tokenAuth": []}]

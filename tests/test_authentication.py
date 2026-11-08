import uuid

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from rest_framework.authentication import SessionAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from drf_impersonation.authentication import ImpersonationMixin, ImpersonationTokenAuthentication
from drf_impersonation.checks import check_settings
from drf_impersonation.signals import user_impersonated
from tests.models import Profile

pytestmark = pytest.mark.django_db


class StaffEmailAuthentication(ImpersonationTokenAuthentication):
    impersonation_lookup_fields = ("pk", "email__iexact")

    def can_impersonate(self, request, actor):
        return actor.is_staff


class ProfileUUIDAuthentication(ImpersonationTokenAuthentication):
    impersonation_lookup_fields = ("profile__uuid",)


class TokenAuthentication(ImpersonationTokenAuthentication):
    impersonation_lookup_fields = ("auth_token",)  # Ends on a reverse relation.


class UsernameAuthentication(ImpersonationTokenAuthentication):
    impersonation_lookup_fields = ("pk", "username")


class ImpersonationSessionAuthentication(ImpersonationMixin, SessionAuthentication):
    pass


def make_user(username, **extra):
    user = User.objects.create(username=username, email=f"{username}@example.com", **extra)
    Token.objects.create(user=user)
    return user


def authenticate(actor, directive=None, backend=ImpersonationTokenAuthentication, method="get"):
    headers = {"HTTP_AUTHORIZATION": f"Token {actor.auth_token.key}"}
    if directive is not None:
        headers["HTTP_X_IMPERSONATE_USER"] = directive
    request = getattr(APIRequestFactory(), method)("/", **headers)
    return request, backend().authenticate(request)


@pytest.fixture
def admin():
    return make_user("admin", is_superuser=True, is_staff=True)


@pytest.fixture
def target():
    return make_user("target")


def test_superuser_impersonates_by_pk(admin, target, caplog):
    request, (user, token) = authenticate(admin, str(target.pk))
    assert user == target
    assert token == admin.auth_token
    assert request.impersonator == admin
    assert f"actor={admin.pk} target={target.pk}" in caplog.text


def test_no_header_is_noop(admin):
    request, (user, _) = authenticate(admin)
    assert user == admin
    assert request.impersonator is None


def test_unauthenticated_request_is_untouched(target):
    request = APIRequestFactory().get("/", HTTP_X_IMPERSONATE_USER=str(target.pk))
    assert ImpersonationTokenAuthentication().authenticate(request) is None


def test_header_ignored_for_unpermitted_actor(target):
    plain = make_user("plain", is_staff=True)
    request, (user, _) = authenticate(plain, str(target.pk))
    assert user == plain
    assert request.impersonator is None


@pytest.mark.parametrize("directive", ["9999", "not-a-pk"])
def test_unknown_target_not_found(admin, directive):
    with pytest.raises(NotFound, match="Impersonation target not found"):
        authenticate(admin, directive)


def test_self_not_found(admin):
    with pytest.raises(NotFound):
        authenticate(admin, str(admin.pk))


def test_inactive_target_not_found(admin):
    inactive = make_user("inactive", is_active=False)
    with pytest.raises(NotFound):
        authenticate(admin, str(inactive.pk))


def test_custom_lookup_and_permission(target):
    staff = make_user("staff", is_staff=True)
    _, (user, _) = authenticate(staff, "TARGET@example.com", StaffEmailAuthentication)
    assert user == target
    _, (user, _) = authenticate(staff, str(target.pk), StaffEmailAuthentication)
    assert user == target


def test_non_superuser_cannot_impersonate_superuser(admin):
    staff = make_user("staff", is_staff=True)
    with pytest.raises(NotFound):
        authenticate(staff, admin.email, StaffEmailAuthentication)


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_unsafe_methods_refused_by_default(admin, target, method):
    with pytest.raises(PermissionDenied, match="read-only"):
        authenticate(admin, str(target.pk), method=method)


@pytest.mark.parametrize("method", ["head", "options"])
def test_safe_methods_allowed_by_default(admin, target, method):
    _, (user, _) = authenticate(admin, str(target.pk), method=method)
    assert user == target


def test_read_only_refuses_without_looking_up_target(admin):
    # 403, not 404: an unknown target must not change the answer.
    with pytest.raises(PermissionDenied):
        authenticate(admin, "9999", method="post")


def test_unsafe_methods_allowed_when_read_only_disabled(admin, target, settings):
    settings.DRF_IMPERSONATION = {"READ_ONLY": False}
    _, (user, _) = authenticate(admin, str(target.pk), method="post")
    assert user == target


def test_unsafe_method_without_header_is_untouched(admin):
    _, (user, _) = authenticate(admin, method="post")
    assert user == admin


def test_signal_sent(admin, target):
    received = []

    def receiver(sender, **kwargs):
        received.append((sender, kwargs))

    user_impersonated.connect(receiver)
    try:
        request, _ = authenticate(admin, str(target.pk))
    finally:
        user_impersonated.disconnect(receiver)
    [(sender, kwargs)] = received
    assert sender is ImpersonationTokenAuthentication
    assert kwargs["request"] is request
    assert kwargs["actor"] == admin
    assert kwargs["target"] == target


def test_signal_not_sent_when_disabled(admin, target, settings):
    settings.DRF_IMPERSONATION = {"SIGNALS": False}
    received = []
    user_impersonated.connect(lambda **kwargs: received.append(kwargs), weak=False)
    try:
        authenticate(admin, str(target.pk))
    finally:
        user_impersonated.receivers.clear()
    assert received == []


def test_unknown_setting_rejected(admin, target, settings):
    settings.DRF_IMPERSONATION = {"READONLY": False}
    with pytest.raises(ImproperlyConfigured, match="READONLY"):
        authenticate(admin, str(target.pk))


def test_impersonator_is_none_when_base_auth_returns_none(target):
    request = APIRequestFactory().get("/", HTTP_X_IMPERSONATE_USER=str(target.pk))
    assert ImpersonationTokenAuthentication().authenticate(request) is None
    assert request.impersonator is None


def test_session_base_class(admin, target):
    request = Request(APIRequestFactory().get("/", HTTP_X_IMPERSONATE_USER=str(target.pk)))
    request._request.user = admin
    user, auth = ImpersonationSessionAuthentication().authenticate(request)
    assert (user, auth) == (target, None)
    assert request.impersonator == admin
    assert request._request.impersonator == admin


def test_ambiguous_target_not_found(admin, target):
    make_user(str(target.pk))  # username equal to another user's pk
    with pytest.raises(NotFound):
        authenticate(admin, str(target.pk), UsernameAuthentication)
    _, (user, _) = authenticate(admin, "target", UsernameAuthentication)
    assert user == target


def test_lookup_across_reverse_relation_with_uuid(admin, target):
    profile = Profile.objects.create(user=target)
    _, (user, _) = authenticate(admin, str(profile.uuid), ProfileUUIDAuthentication)
    assert user == target
    for directive in ["not-a-uuid", str(uuid.uuid4())]:
        with pytest.raises(NotFound):
            authenticate(admin, directive, ProfileUUIDAuthentication)


def test_lookup_ending_on_relation(admin, target):
    _, (user, _) = authenticate(admin, target.auth_token.key, TokenAuthentication)
    assert user == target


def test_misspelled_lookup_raises(admin, target):
    class Typo(ImpersonationTokenAuthentication):
        impersonation_lookup_fields = ("emial__iexact",)

    with pytest.raises(FieldDoesNotExist):
        authenticate(admin, target.email, Typo)


def test_end_to_end(admin, target):
    client = APIClient()
    assert client.get("/me/").json() == {
        "user": None,
        "impersonator": None,
        "django_impersonator": None,
    }
    client.credentials(HTTP_AUTHORIZATION=f"Token {admin.auth_token.key}")
    assert client.get("/me/", HTTP_X_IMPERSONATE_USER=str(target.pk)).json() == {
        "user": target.pk,
        "impersonator": admin.pk,
        "django_impersonator": admin.pk,
    }
    response = client.post("/me/", HTTP_X_IMPERSONATE_USER=str(target.pk))
    assert (response.status_code, response.json()) == (
        403,
        {"detail": "Impersonated requests are read-only"},
    )
    response = client.get("/me/", HTTP_X_IMPERSONATE_USER="9999")
    assert (response.status_code, response.json()) == (
        404,
        {"detail": "Impersonation target not found"},
    )


def test_system_check(settings):
    assert check_settings(None) == []
    settings.DRF_IMPERSONATION = {"READONLY": False, "SIGNAL": True}
    [error] = check_settings(None)
    assert error.id == "drf_impersonation.E001"
    assert "READONLY, SIGNAL" in error.msg

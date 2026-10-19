# drf-impersonation

[![PyPI version](https://img.shields.io/pypi/v/drf-impersonation.svg)](https://pypi.org/project/drf-impersonation/)
[![Python versions](https://img.shields.io/pypi/pyversions/drf-impersonation.svg)](https://pypi.org/project/drf-impersonation/)
[![Django versions](https://img.shields.io/pypi/frameworkversions/django/drf-impersonation.svg)](https://pypi.org/project/drf-impersonation/)
[![CI](https://github.com/ahmadjanan/drf-impersonation/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmadjanan/drf-impersonation/actions/workflows/ci.yml)
[![Coverage: 100%](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/ahmadjanan/drf-impersonation/blob/main/pyproject.toml)
[![Typed](https://img.shields.io/badge/typing-typed-blue.svg)](https://peps.python.org/pep-0561/)
[![License: MIT](https://img.shields.io/pypi/l/drf-impersonation.svg)](https://github.com/ahmadjanan/drf-impersonation/blob/main/LICENSE)

**Header-based user impersonation for Django REST Framework.** A permitted user sends one extra
header and the request runs as someone else. This works with every DRF authentication class:
Token, Session, JWT and OAuth.

```http
GET /api/orders/ HTTP/1.1
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
X-Impersonate-User: 42
```

The view sees `request.user` as user `42`. The real caller is still available on
`request.impersonator`.

## Contents

- [Why](#why)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Behaviour](#behaviour)
- [Settings](#settings)
- [Customising the authentication class](#customising-the-authentication-class)
- [Signals](#signals)
- [OpenAPI](#openapi)
- [Type checking](#type-checking)
- [Recipes](#recipes)
- [Security considerations](#security-considerations)
- [Contributing](#contributing)
- [License](#license)

## Why

Support staff often need to see what a customer sees. Packages like `django-impersonate` and
`django-hijack` do this by changing the session, so they don't fit token-authenticated APIs that
have no session to change.

`drf-impersonation` runs inside the DRF authentication class. The base class authenticates the
real caller as normal. Then the mixin decides whether to swap in the target user. Impersonation
lasts for one request only, and the server keeps no state.

## Features

- **Any auth backend.** Mix it into Token, Session, SimpleJWT, OAuth or a custom class.
- **Stateless.** One header on one request. Nothing to start, stop or clean up.
- **Read-only by default.** While impersonating, write requests are refused unless you turn this off.
- **Safe defaults.** Only superusers can impersonate. Inactive users and privilege escalation are
  refused.
- **No user enumeration.** A target that doesn't exist and a target you may not impersonate give
  the same `404`.
- **Flexible lookups.** Find the target by primary key, UUID, email or any other field.
- **Audit hooks.** Each impersonated request is logged and sends a Django signal.
- **OpenAPI support.** The header appears in drf-spectacular schemas and Swagger UI.
- **Typed.** Ships `py.typed`.

## Requirements

| Dependency | Supported versions |
| --- | --- |
| Python | 3.10 – 3.15 |
| Django | 4.2, 5.2, 6.0, 6.1 |
| Django REST Framework | 3.14+ |
| drf-spectacular (optional) | 0.27+ |

CI runs the tests across the supported Python, Django and DRF versions.

## Installation

```bash
pip install drf-impersonation
```

To include OpenAPI support:

```bash
pip install "drf-impersonation[openapi]"
```

## Quick start

1. Add the app. This is only needed for [OpenAPI](#openapi) support, but adding it is harmless:

   ```python
   INSTALLED_APPS = [
       # ...
       "rest_framework",
       "drf_impersonation",
   ]
   ```

2. Use the ready-made token class:

   ```python
   REST_FRAMEWORK = {
       "DEFAULT_AUTHENTICATION_CLASSES": [
           "drf_impersonation.authentication.ImpersonationTokenAuthentication",
       ],
   }
   ```

   For any other auth class, put `ImpersonationMixin` **before** it:

   ```python
   # myproject/authentication.py
   from drf_impersonation.authentication import ImpersonationMixin
   from rest_framework_simplejwt.authentication import JWTAuthentication


   class ImpersonationJWTAuthentication(ImpersonationMixin, JWTAuthentication):
       pass
   ```

3. Send the header as a superuser:

   ```bash
   curl https://api.example.com/api/me/ \
     -H "Authorization: Token <superuser token>" \
     -H "X-Impersonate-User: 42"
   ```

In a view, `request.user` is the target and `request.impersonator` is the real caller. When
there is no impersonation, `request.impersonator` is `None`:

```python
@api_view(["GET"])
def me(request):
    impersonator = request.impersonator
    return Response(
        {
            "user": request.user.pk,
            "impersonated_by": impersonator.pk if impersonator else None,
        }
    )
```

## How it works

```
Base auth class (Token / JWT / Session / ...)
  │  no credentials ─────────────────────────▶ None. Bad credentials raise as usual.
  ▼  actor authenticated
X-Impersonate-User header?
  │  no ─────────────────────────────────────▶ actor, request.impersonator = None
  ▼  yes
can_impersonate(actor)?
  │  no ─────────────────────────────────────▶ header ignored, actor
  ▼  yes
READ_ONLY and method is not GET/HEAD/OPTIONS?
  │  yes ────────────────────────────────────▶ 403 Impersonated requests are read-only
  ▼  no
target found and can_impersonate_target(actor, target)?
  │  no ─────────────────────────────────────▶ 404 Impersonation target not found
  ▼  yes
on_impersonate() logs, user_impersonated signal ─▶ target, request.impersonator = actor
```

`request.auth` (the token, JWT payload and so on) still belongs to the **actor**.

## Behaviour

| Situation | Result |
| --- | --- |
| No header | No change. `request.impersonator` is `None`. |
| Caller may not impersonate | Header ignored. The request runs as the caller. |
| Write method (POST, PUT, PATCH, DELETE) while `READ_ONLY` is on | `403 Impersonated requests are read-only` |
| No user matches the header value | `404 Impersonation target not found` |
| Target is the caller, is inactive, or is a superuser while the caller is not | `404` |
| Success | `request.user` is the target, `request.impersonator` is the caller, a warning is logged and the signal is sent. |

The read-only check happens before the target lookup. A write request gets `403` whether or not
the target exists.

## Settings

All settings are optional. Put them in a `DRF_IMPERSONATION` dict:

```python
DRF_IMPERSONATION = {
    "READ_ONLY": True,
    "SIGNALS": True,
    "OPENAPI": True,
}
```

| Key | Default | Effect |
| --- | --- | --- |
| `READ_ONLY` | `True` | Refuse POST, PUT, PATCH and DELETE with `403` while impersonating. |
| `SIGNALS` | `True` | Send [`user_impersonated`](#signals) for each impersonated request. |
| `OPENAPI` | `True` | Document the header in [drf-spectacular](#openapi) schemas. |

Settings are read on every request, so `override_settings` works in tests. An unknown key raises
`ImproperlyConfigured`, which catches typos.

## Customising the authentication class

For behaviour that differs per class, subclass and override any of these:

| Attribute / method | Default | Purpose |
| --- | --- | --- |
| `impersonation_header` | `"X-Impersonate-User"` | Header that names the target. |
| `impersonation_lookup_fields` | `("pk",)` | Fields to match the header value against. All valid fields are tried together with OR, for example `("uuid", "email__iexact")`. |
| `can_impersonate(request, actor)` | `actor.is_superuser` | Whether the caller may impersonate anyone. |
| `can_impersonate_target(request, actor, target)` | Target is active, and no escalation to superuser | Whether the caller may impersonate this specific target. |
| `on_impersonate(request, actor, target)` | Logs a warning on the `drf_impersonation` logger | Runs for each impersonated request, before the signal. |

```python
from drf_impersonation.authentication import ImpersonationTokenAuthentication


class SupportImpersonation(ImpersonationTokenAuthentication):
    impersonation_lookup_fields = ("pk", "email__iexact")

    def can_impersonate(self, request, actor):
        return actor.has_perm("accounts.impersonate_user")
```

## Signals

`drf_impersonation.signals.user_impersonated` is sent after each impersonated request is
authenticated. The sender is the authentication class. The keyword arguments are `request`,
`actor` and `target`.

```python
from django.dispatch import receiver
from drf_impersonation.signals import user_impersonated


@receiver(user_impersonated)
def record_impersonation(sender, request, actor, target, **kwargs):
    AuditEvent.objects.create(actor=actor, target=target, path=request.path)
```

Set `"SIGNALS": False` to stop sending it.

## OpenAPI

With [drf-spectacular](https://drf-spectacular.readthedocs.io/) installed and `drf_impersonation`
in `INSTALLED_APPS`, every endpoint that uses an impersonation class documents the header. The
header is a security scheme called `impersonation`, and it is optional. Each operation lists the
base scheme alone and the base scheme together with the header:

```yaml
security:
  - tokenAuth: []
  - tokenAuth: []
    impersonation: []
```

Swagger UI then shows an `X-Impersonate-User` field under **Authorize**. If `READ_ONLY` is on,
the scheme description says that only safe methods are allowed.

The extension wraps whatever scheme drf-spectacular already uses for the base class, such as
Token, SimpleJWT or Session. If the base class has no scheme, nothing is added. Set
`"OPENAPI": False` to turn the extension off.

## Type checking

The package ships `py.typed`, so mypy and pyright check calls to its hooks. `request.impersonator`
is set at runtime on DRF's `Request`, which type checkers don't know about. Use
`getattr(request, "impersonator", None)` if your checker complains.

## Recipes

### Allow writes for some callers only

Turn off `READ_ONLY` and make the decision in a permission class:

```python
from rest_framework.permissions import SAFE_METHODS, BasePermission


class ImpersonationWritesForSuperusers(BasePermission):
    def has_permission(self, request, view):
        impersonator = getattr(request, "impersonator", None)
        if impersonator is None or request.method in SAFE_METHODS:
            return True
        return impersonator.is_superuser
```

### Protect staff accounts from support agents

```python
def can_impersonate_target(self, request, actor, target):
    if not super().can_impersonate_target(request, actor, target):
        return False
    return actor.is_superuser or not target.is_staff
```

### Route the default log

```python
LOGGING = {
    "version": 1,
    "handlers": {"audit": {"class": "logging.FileHandler", "filename": "impersonation.log"}},
    "loggers": {"drf_impersonation": {"handlers": ["audit"], "level": "WARNING"}},
}
```

### Allow the header through CORS

Browsers only send custom headers that the server allows. With `django-cors-headers`:

```python
from corsheaders.defaults import default_headers

CORS_ALLOW_HEADERS = (*default_headers, "x-impersonate-user")
```

## Security considerations

- **Keep `can_impersonate` narrow.** Anyone it allows can act as almost any user.
- **Leave `READ_ONLY` on** unless support staff really need to make changes on a user's behalf.
- **Keep the escalation check.** If you override `can_impersonate_target`, call `super()` so that
  inactive users and superusers stay protected.
- **Keep a durable audit record.** The default log line is a minimum. Use the signal to store
  each event.
- **`request.auth` is the actor's.** Token scopes and claims belong to the real caller, not the
  target.

To report a vulnerability, see [SECURITY.md](https://github.com/ahmadjanan/drf-impersonation/blob/main/SECURITY.md).

## Contributing

Bug reports and pull requests are welcome. See
[CONTRIBUTING.md](https://github.com/ahmadjanan/drf-impersonation/blob/main/CONTRIBUTING.md) for
the development setup and the release process, and
[CHANGELOG.md](https://github.com/ahmadjanan/drf-impersonation/blob/main/CHANGELOG.md) for the
history.

## License

[MIT](https://github.com/ahmadjanan/drf-impersonation/blob/main/LICENSE) © Ahmad Ali

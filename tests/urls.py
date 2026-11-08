from django.urls import path
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from drf_impersonation.authentication import ImpersonationTokenAuthentication


@api_view(["GET", "POST"])
@authentication_classes([ImpersonationTokenAuthentication])
@permission_classes([AllowAny])
def me(request):
    # No getattr: the attribute must always exist here, on both the DRF and the Django request.
    drf_impersonator = request.impersonator
    django_impersonator = request._request.impersonator
    return Response(
        {
            "user": request.user.pk,
            "impersonator": drf_impersonator.pk if drf_impersonator else None,
            "django_impersonator": django_impersonator.pk if django_impersonator else None,
        }
    )


urlpatterns = [path("me/", me)]

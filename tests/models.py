import uuid

from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4)

    def __str__(self):
        return str(self.uuid)  # pragma: no cover

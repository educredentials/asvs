from django.db import models

# Create your models here.

from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    is_superuser = models.BooleanField(default=False)
    is_two_factor_enabled = models.BooleanField(default=False)
    secret= models.CharField(max_length=400, blank=True, default="")

    # SURFconext / OIDC federated login support.
    AUTH_SOURCE_LOCAL = "local"
    AUTH_SOURCE_OIDC = "oidc"
    AUTH_SOURCE_CHOICES = [
        (AUTH_SOURCE_LOCAL, "Local"),
        (AUTH_SOURCE_OIDC, "SURFconext (OIDC)"),
    ]

    # Stable OIDC subject identifier (the `sub` claim). Used to look up and link
    # accounts instead of username, because username is mutable (see
    # accountauth.views.modify_username) and must not be relied on for identity.
    oidc_sub = models.CharField(max_length=255, blank=True, null=True, unique=True)
    auth_source = models.CharField(
        max_length=16, choices=AUTH_SOURCE_CHOICES, default=AUTH_SOURCE_LOCAL
    )

"""SURFconext OpenID Connect authentication backend.

Institutional users authenticate against SURFconext (which brokers the
actual login with the user's home organisation). We link the resulting
local ``CustomUser`` account to the federated identity via the stable
OIDC ``sub`` claim, rather than the (mutable) ``username`` field.

Because SURFconext's institutional SSO is treated as the authentication
assurance for these accounts, they are marked with ``auth_source="oidc"``
and ``is_two_factor_enabled=True`` so the app's local TOTP 2FA gate
(see ``accountauth.views.request_has_verified_2fa``,
``projects.views.request_has_verified_2fa`` and ``home.views.home_page``)
is bypassed for them.
"""

from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from accountauth.models import CustomUser


class SurfConextOIDCBackend(OIDCAuthenticationBackend):
    """Authenticate CustomUser accounts against SURFconext claims."""

    def filter_users_by_claims(self, claims):
        sub = claims.get("sub")
        if not sub:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(oidc_sub=sub)

    def _unique_username(self, base_username):
        base_username = base_username or "surfconext-user"
        username = base_username
        suffix = 1
        while CustomUser.objects.filter(username=username).exists():
            suffix += 1
            username = f"{base_username}-{suffix}"
        return username

    def _username_from_claims(self, claims):
        candidate = (
            claims.get("eduperson_principal_name")
            or claims.get("email")
            or claims.get("sub")
        )
        return candidate

    def create_user(self, claims):
        sub = claims["sub"]
        username = self._unique_username(self._username_from_claims(claims))

        user = CustomUser(
            username=username,
            email=claims.get("email", "") or "",
            first_name=claims.get("given_name", "") or "",
            last_name=claims.get("family_name", "") or "",
            oidc_sub=sub,
            auth_source=CustomUser.AUTH_SOURCE_OIDC,
            is_superuser=False,
            is_staff=False,
            # SURFconext SSO is the trusted authentication factor for these
            # accounts; they are exempt from the local TOTP 2FA gate.
            is_two_factor_enabled=True,
        )
        # OIDC-only accounts must not be usable via the local password login form.
        user.set_unusable_password()
        user.save()
        return user

    def update_user(self, user, claims):
        # Refresh display-only fields; never touch username/oidc_sub/auth_source
        # so that a later local username change never breaks the SURFconext link.
        user.email = claims.get("email", "") or user.email
        user.first_name = claims.get("given_name", "") or user.first_name
        user.last_name = claims.get("family_name", "") or user.last_name
        user.save()
        return user

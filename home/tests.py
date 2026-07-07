from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class HomePageOidcExemptionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(
            username='surfconext-user',
            auth_source='oidc',
            oidc_sub='surf-sub-home-1',
            is_two_factor_enabled=True,
        )
        self.user.set_unusable_password()
        self.user.save()

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_oidc_user_is_not_redirected_to_authenticate_2fa(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_oidc_user_is_two_factor_enabled_flag_is_not_reset(self):
        self.client.force_login(self.user)

        self.client.get(reverse('home'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_two_factor_enabled)

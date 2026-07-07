from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from accountauth.models import CustomUser
from accountauth.oidc import SurfConextOIDCBackend
from accountauth.views import UserCreateForm, request_has_verified_2fa


class UserCreateFormTests(TestCase):
    def test_signup_form_ignores_client_supplied_privilege_flags(self):
        form = UserCreateForm(data={
            'username': 'mallory',
            'password1': 'Long passphrase 123!',
            'password2': 'Long passphrase 123!',
            'is_superuser': 'on',
            'is_staff': 'on',
            'is_two_factor_enabled': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)

        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_two_factor_enabled)


class SurfConextOIDCBackendTests(TestCase):
    def setUp(self):
        self.backend = SurfConextOIDCBackend()

    def test_create_user_sets_expected_defaults(self):
        claims = {
            'sub': 'surf-sub-123',
            'email': 'alice@example.edu',
            'given_name': 'Alice',
            'family_name': 'Example',
            'eduperson_principal_name': 'alice@example.edu',
        }

        user = self.backend.create_user(claims)

        self.assertEqual(user.oidc_sub, 'surf-sub-123')
        self.assertEqual(user.auth_source, CustomUser.AUTH_SOURCE_OIDC)
        self.assertTrue(user.is_two_factor_enabled)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.username, 'alice@example.edu')

    def test_create_user_deduplicates_username_collisions(self):
        CustomUser.objects.create_user(username='alice@example.edu', password='irrelevant12345')
        claims = {'sub': 'surf-sub-456', 'eduperson_principal_name': 'alice@example.edu'}

        user = self.backend.create_user(claims)

        self.assertNotEqual(user.username, 'alice@example.edu')
        self.assertTrue(user.username.startswith('alice@example.edu'))

    def test_filter_users_by_claims_matches_on_oidc_sub_even_after_username_change(self):
        claims = {'sub': 'surf-sub-789', 'eduperson_principal_name': 'bob@example.edu'}
        user = self.backend.create_user(claims)
        user.username = 'renamed-bob'
        user.save()

        found = self.backend.filter_users_by_claims({'sub': 'surf-sub-789'})

        self.assertEqual(list(found), [user])

    def test_request_has_verified_2fa_true_for_oidc_user_without_totp_device(self):
        claims = {'sub': 'surf-sub-999', 'eduperson_principal_name': 'carol@example.edu'}
        user = self.backend.create_user(claims)

        request = RequestFactory().get('/auth/profile')
        request.user = user

        self.assertTrue(request_has_verified_2fa(request))

    def test_request_has_verified_2fa_false_for_local_user_without_totp_device(self):
        User = get_user_model()
        user = User.objects.create_user(username='dave', password='password12345')

        request = RequestFactory().get('/auth/profile')
        request.user = user

        self.assertFalse(request_has_verified_2fa(request))

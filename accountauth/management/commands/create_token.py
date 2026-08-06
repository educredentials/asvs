from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Create or reset an API token for a user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to create token for')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.error_style(f'User "{username}" does not exist.'))
            return

        token, created = Token.objects.get_or_create(user=user)
        if created:
            self.stdout.write(f'Token created for user "{username}".')
        else:
            self.stdout.write(f'Token reset for user "{username}".')
        self.stdout.write(f'Token key: {token.key}')

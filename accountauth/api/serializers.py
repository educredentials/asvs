from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_active', 'is_two_factor_enabled',
                   'auth_source', 'date_joined']
        read_only_fields = ['id', 'date_joined', 'auth_source']

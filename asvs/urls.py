
from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from mcp.app import mcp_endpoint

urlpatterns = [
    path('admin/', admin.site.urls),
    path(r'', include('home.urls')),
    path('home/', include('home.urls')),
    path('levels/', include('levels.urls')),
    path('help/', include('help.urls')),
    path('auth/', include('accountauth.urls')),
    path('projects/', include('projects.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-docs'),
    path('api/', include('projects.api.urls')),
    path('api/', include('accountauth.api.urls')),
    path('api/mcp/', mcp_endpoint, name='mcp-endpoint'),
]

if settings.OIDC_ENABLED:
    urlpatterns.append(path('auth/oidc/', include('mozilla_django_oidc.urls')))

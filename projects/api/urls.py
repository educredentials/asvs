from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    ProjectViewSet, ProjectMemberViewSet,
    ProjectRequirementViewSet, RequirementEvidenceViewSet,
    RequirementCommentViewSet,
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'requirements', ProjectRequirementViewSet, basename='requirement')
router.register(r'evidence', RequirementEvidenceViewSet, basename='evidence')
router.register(r'comments', RequirementCommentViewSet, basename='comment')

urlpatterns = [
    path('', include(router.urls)),
]

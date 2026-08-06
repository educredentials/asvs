import csv
import io
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from projects.models import Projects, ProjectMember, ProjectRequirement, RequirementEvidence, RequirementComment, AuditEvent
from .serializers import (
    ProjectSerializer, ProjectMemberSerializer,
    ProjectRequirementSerializer,
    RequirementEvidenceSerializer,
    RequirementCommentSerializer,
    AuditEventSerializer
)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Projects.objects.none()

    def get_queryset(self):
        user = self.request.user
        qs = Projects.objects.all()
        level = self.request.query_params.get('level')
        owner = self.request.query_params.get('owner')
        if level:
            qs = qs.filter(project_level=level)
        if owner:
            qs = qs.filter(project_owner=owner)
        return qs.order_by('-project_created')

    @action(detail=True, methods=['get'])
    def requirements(self, pk=None):
        project = self.get_object()
        qs = project.requirements.all()
        serializer = ProjectRequirementSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def audit_events(self, pk=None):
        project = self.get_object()
        qs = project.audit_events.all()
        serializer = AuditEventSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def export_csv(self, pk=None):
        project = self.get_object()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['req_id', 'chapter_id', 'section_id', 'section_name',
                         'req_description', 'status', 'note', 'level1', 'level2', 'level3'])
        for req in project.requirements.all():
            writer.writerow([
                req.req_id, req.chapter_id, req.section_id, req.section_name,
                req.req_description, req.status, req.note,
                req.level1, req.level2, req.level3
            ])
        response = Response(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{project.project_name}.csv"'
        return response


class ProjectMemberViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectMemberSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ProjectMember.objects.none()

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return ProjectMember.objects.filter(project_id=project_id)

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        serializer.save(project_id=project_id)


class ProjectRequirementViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectRequirementSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ProjectRequirement.objects.none()

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return ProjectRequirement.objects.filter(project_id=project_id)

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        serializer.save(project_id=project_id)


class RequirementEvidenceViewSet(viewsets.ModelViewSet):
    serializer_class = RequirementEvidenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = RequirementEvidence.objects.none()

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        req_id = self.kwargs.get('req_pk')
        return RequirementEvidence.objects.filter(
            requirement__project_id=project_id,
            requirement_id=req_id
        )

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        req_id = self.kwargs.get('req_pk')
        req = ProjectRequirement.objects.get(project_id=project_id, id=req_id)
        serializer.save(requirement=req)


class RequirementCommentViewSet(viewsets.ModelViewSet):
    serializer_class = RequirementCommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = RequirementComment.objects.none()

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        req_id = self.kwargs.get('req_pk')
        return RequirementComment.objects.filter(
            requirement__project_id=project_id,
            requirement_id=req_id
        )

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        req_id = self.kwargs.get('req_pk')
        req = ProjectRequirement.objects.get(project_id=project_id, id=req_id)
        serializer.save(requirement=req)

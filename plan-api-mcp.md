# OpenAPI API + MCP Server Implementation Plan

## 1. Background

The project currently uses Django with function-based views and renders. DRF (`djangorestframework==3.16.1`) is in `requirements.txt` but **not in `INSTALLED_APPS`**, has no configuration, no serializers, no ViewSets, and no OpenAPI generator. There are two `APIView` classes for TOTP that work but aren't part of any structured API.

This plan covers:
1. Building a full OpenAPI-compatible Django REST API (DRF + drf-spectacular)
2. Building an MCP server endpoint that sits on top of the API, exposing tools to agents

---

## 2. Stack Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| REST framework | Django REST Framework 3.16 (already installed) | Already a dependency, mature, Django-native |
| OpenAPI generator | `drf-spectacular` | Auto-generates OpenAPI 3.0 from ViewSets, Swagger UI built in, better maintained than drf-yasg |
| Serializers | DRF serializers (manual) | Full control over nested relationships (evidence, comments, members under requirements) |
| MCP server | Inline Django app (`mcp/`) | Lightweight JSON-RPC handler, no extra process needed |
| Wire protocol | JSON-RPC 2.0 per MCP spec | `application/json` content type |

---

## 3. Data Model Recap

The app has 7 models. Here are their relationships:

```
CustomUser
  ├── ProjectMember ──────┐──► Projects
  │                        │    ├── ProjectRequirement (related_name=requirements)
  │                        │         ├── RequirementEvidence (related_name=evidence)
  │                        │         └── RequirementComment (related_name=comments)
  │                        │    ├── ProjectMember (related_name=members) [reverse]
  │                        │    └── AuditEvent (related_name=audit_events) [reverse]
  └── AuditEvent ─────────┘
```

**Key relationship notes:**
- `ProjectMember` belongs to a `Projects` instance
- `RequirementEvidence` and `RequirementComment` are children of `ProjectRequirement`
- `AuditEvent` can reference either a project or a requirement

---

## 4. Phase 1 — DRF + OpenAPI Setup

### 4.1 Add `drf-spectacular`

**File: `requirements.txt`**
```
drf-spectacular==0.28.0
```

### 4.2 Configure `INSTALLED_APPS` and `REST_FRAMEWORK`

**File: `asvs/settings.py`**

Add to `INSTALLED_APPS`:
```python
INSTALLED_APPS = [
    # ... existing apps ...
    'rest_framework',
    'drf_spectacular',
]
```

Add to `settings.py`:
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'ASVS API',
    'DESCRIPTION': 'OWASP ASVS 5.0 management API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': '/api/',
    'SCHEMA_PATH_PREFIX_TRIM': True,
}
```

### 4.3 Add API URLs to Main `urls.py`

**File: `asvs/urls.py`**
```python
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# ... existing imports ...

path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
path('api/docs/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-docs'),
path('api/', include('projects.api.urls')),
path('api/', include('accountauth.api.urls')),
path('api/mcp/', MCPView.as_view(), name='mcp-endpoint'),
```

This replaces the orphaned `re_path(r'^api/', include('accountauth.urls'))`.

---

## 5. Phase 2 — Serializers

### 5.1 Files

```
projects/api/serializers.py
accountauth/api/serializers.py
```

### 5.2 User Serializer

```python
# accountauth/api/serializers.py

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_active', 'is_two_factor_enabled',
                   'auth_source', 'date_joined']
        read_only_fields = ['id', 'date_joined', 'auth_source']
```

### 5.3 Project Serializer

```python
# projects/api/serializers.py

from rest_framework import serializers
from .models import Projects, ProjectMember

class ProjectMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectMember
        fields = ['id', 'username', 'role', 'created_at']
        read_only_fields = ['created_at']

    def validate_username(self, value):
        if not User.objects.filter(username=value).exists():
            raise serializers.ValidationError(f"User '{value}' does not exist.")
        return value

class ProjectSerializer(serializers.ModelSerializer):
    members = ProjectMemberSerializer(many=True, read_only=True)
    member_set = ProjectMemberSerializer(many=True, required=False)
    _member_count = serializers.SerializerMethodField()

    class Meta:
        model = Projects
        fields = ['id', 'project_name', 'project_owner', 'project_description',
                   'project_level', 'asvs_version', 'project_created',
                   'project_allowed_viewers', 'members', 'member_set']
        read_only_fields = ['id', 'project_owner', 'project_created']

    def create(self, validated_data):
        members = validated_data.pop('member_set', [])
        instance = super().create(validated_data)
        for m in members:
            ProjectMember.objects.create(project=instance, **m)
        return instance

    def update(self, instance, validated_data):
        members = validated_data.pop('member_set', None)
        instance = super().update(instance, validated_data)
        if members is not None:
            instance.members.all().delete()
            for m in members:
                ProjectMember.objects.create(project=instance, **m)
        return instance

    def get__member_count(self, obj):
        return obj.members.count()
```

### 5.4 Requirement Serializer (with nested evidence + comments)

```python
# projects/api/serializers.py

from rest_framework import serializers
from .models import ProjectRequirement, RequirementEvidence, RequirementComment

class RequirementEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementEvidence
        fields = ['id', 'title', 'url', 'notes', 'created_by', 'created_at']
        read_only_fields = ['created_at']

class RequirementCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequirementComment
        fields = ['id', 'body', 'created_by', 'created_at']
        read_only_fields = ['created_at']

class ProjectRequirementSerializer(serializers.ModelSerializer):
    evidence = RequirementEvidenceSerializer(many=True, read_only=True)
    comments = RequirementCommentSerializer(many=True, read_only=True)
    evidence_set = RequirementEvidenceSerializer(many=True, required=False)
    comments_set = RequirementCommentSerializer(many=True, required=False)

    STATUS_CHOICES = [
        ('na', 'Not Applicable'),
        ('incomplete', 'Incomplete'),
        ('complete', 'Complete'),
        ('review', 'Needs Review'),
        ('risk_accepted', 'Risk Accepted'),
    ]

    class Meta:
        model = ProjectRequirement
        fields = '__all__'

    def create(self, validated_data):
        evidence = validated_data.pop('evidence_set', [])
        comments = validated_data.pop('comments_set', [])
        inst = super().create(validated_data)
        for e in evidence:
            RequirementEvidence.objects.create(requirement=inst, **e)
        for c in comments:
            RequirementComment.objects.create(requirement=inst, **c)
        return inst

    def update(self, instance, validated_data):
        evidence = validated_data.pop('evidence_set', None)
        comments = validated_data.pop('comments_set', None)
        instance = super().update(instance, validated_data)
        if evidence is not None:
            instance.evidence.all().delete()
            for e in evidence:
                RequirementEvidence.objects.create(requirement=instance, **e)
        if comments is not None:
            instance.comments.all().delete()
            for c in comments:
                RequirementComment.objects.create(requirement=instance, **c)
        return instance
```

### 5.5 Audit Event Serializer

```python
# projects/api/serializers.py

from rest_framework import serializers
from .models import AuditEvent

class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = '__all__'
        read_only_fields = ['created_at']
```

---

## 6. Phase 3 — ViewSets

### 6.1 Files

```
projects/api/viewsets.py
accountauth/api/viewsets.py
```

### 6.2 Project ViewSets

```python
# projects/api/viewsets.py

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Projects, ProjectMember, ProjectRequirement, RequirementEvidence, RequirementComment, AuditEvent
from .serializers import (ProjectSerializer, ProjectMemberSerializer,
                           ProjectRequirementSerializer,
                           RequirementEvidenceSerializer,
                           RequirementCommentSerializer, AuditEventSerializer)

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

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
        # ... export logic (reuse existing view logic)
        return Response({'status': 'exported'})

class ProjectMemberViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return ProjectMember.objects.filter(project_id=project_id)

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        serializer.save(project_id=project_id)

class ProjectRequirementViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectRequirementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        return ProjectRequirement.objects.filter(project_id=project_id)

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        serializer.save(project_id=project_id)

class RequirementEvidenceViewSet(viewsets.ModelViewSet):
    serializer_class = RequirementEvidenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        req_id = self.kwargs.get('req_pk')
        return RequirementEvidence.objects.filter(requirement__project_id=project_id, requirement__id=req_id)

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        req_id = self.kwargs.get('req_pk')
        req = ProjectRequirement.objects.get(project_id=project_id, id=req_id)
        serializer.save(requirement=req)

class RequirementCommentViewSet(viewsets.ModelViewSet):
    serializer_class = RequirementCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        req_id = self.kwargs.get('req_pk')
        return RequirementComment.objects.filter(requirement__project_id=project_id, requirement__id=req_id)

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        req_id = self.kwargs.get('req_pk')
        req = ProjectRequirement.objects.get(project_id=project_id, id=req_id)
        serializer.save(requirement=req)
```

### 6.3 User ViewSet

```python
# accountauth/api/viewsets.py

from rest_framework import viewsets, permissions
from django.contrib.auth import get_user_model
from .serializers import UserSerializer

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.all().order_by('date_joined')

    def get_object(self):
        return self.request.user
```

### 6.4 URL Configuration

**File: `projects/api/urls.py`**
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    ProjectViewSet, ProjectMemberViewSet,
    ProjectRequirementViewSet, RequirementEvidenceViewSet,
    RequirementCommentViewSet,
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)

router.register(r'requirements', ProjectRequirementViewSet, basename='requirement')
router.register(r'evidence', RequirementEvidenceViewSet, basename='evidence')
router.register(r'comments', RequirementCommentViewSet, basename='comment')

urlpatterns = [
    path('', include(router.urls)),
]
```

Nested URLs:
- `GET /api/projects/` — list projects
- `POST /api/projects/` — create project
- `GET /api/projects/{id}/` — get project
- `PUT /api/projects/{id}/` — update project
- `DELETE /api/projects/{id}/` — delete project
- `GET /api/projects/{id}/requirements/` — list requirements
- `GET /api/projects/{id}/audit_events/` — list audit events
- `GET /api/requirements/?project=1` — list requirements filtered by project
- `GET /api/requirements/{id}/evidence/` — list evidence for a requirement
- etc.

**File: `accountauth/api/urls.py`**
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import UserViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('totp/create/', ...),  # keep TOTP views
    path('totp/verify/', ...),
]
```

---

## 7. Phase 4 — MCP Server

### 7.1 Concept

The MCP (Model Context Protocol) is a JSON-RPC 2.0 wire protocol. An agent talks to it via HTTP POST. The server exposes:
1. **Tools** — named functions with a description and JSON Schema (what the agent calls)
2. **Resources** — optional, for reading data
3. **Prompts** — optional, for templated queries

This server exposes the ASVS domain entities as tools. Each tool calls logic internally (no HTTP calls to itself — it uses the Django ORM directly).

### 7.2 Architecture

```
Agent ◄──HTTP POST /api/mcp/──► MCP JSON-RPC Handler
                                        │
                                        ├── list_tools ──► return JSON schema of all tools
                                        ├── tool_call     ──► route to handler function
                                        │                  - list_projects()
                                        │                  - get_requirement(project, req_id)
                                        │                  - update_status(project, req_id, status, note)
                                        │                  - add_evidence(project, req_id, title, url, notes)
                                        │                  - add_comment(project, req_id, body)
                                        │                  - list_members(project)
                                        │                  - list_audit_events(project)
                                        └── resources       ──► optional: export project data
```

### 7.3 Files

```
mcp/
├── __init__.py
├── app.py          # Django view (entry point)
├── tools.py        # Tool registry + handler functions
├── schema.py       # Tool descriptions + JSON Schema (for auto-registration)
└── middleware.py   # Auth + request validation
```

### 7.4 `mcp/schema.py` — Tool Registry

```python
TOOLS = [
    {
        "name": "list_projects",
        "description": "List all ASVS projects, optionally filtered by level or owner.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "level": {"type": "integer", "description": "Filter by ASVS level"},
                "owner": {"type": "string", "description": "Filter by project owner username"},
            },
            "required": [],
        },
    },
    {
        "name": "get_project",
        "description": "Get a single project by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "Project ID"}},
            "required": ["id"],
        },
    },
    {
        "name": "create_project",
        "description": "Create a new ASVS project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "project_description": {"type": "string"},
                "project_level": {"type": "integer", "default": 0},
            },
            "required": ["project_name", "project_description"],
        },
    },
    {
        "name": "update_project",
        "description": "Update a project by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "project_name": {"type": "string"},
                "project_description": {"type": "string"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "delete_project",
        "description": "Delete a project by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    },
    {
        "name": "get_requirements",
        "description": "List all requirements for a project, optionally filtered by status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["na", "incomplete", "complete", "review", "risk_accepted"]},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_requirement",
        "description": "Get a single requirement by ID (includes evidence and comments).",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    },
    {
        "name": "update_requirement_status",
        "description": "Update the status of a requirement.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "status": {"type": "string", "enum": ["na", "incomplete", "complete", "review", "risk_accepted"]},
                "note": {"type": "string"},
            },
            "required": ["id", "status"],
        },
    },
    {
        "name": "add_evidence",
        "description": "Add evidence to a requirement.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "requirement_id": {"type": "integer"},
                "title": {"type": "string"},
                "url": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["requirement_id", "title"],
        },
    },
    {
        "name": "add_comment",
        "description": "Add a comment to a requirement.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "requirement_id": {"type": "integer"},
                "body": {"type": "string"},
            },
            "required": ["requirement_id", "body"],
        },
    },
    {
        "name": "list_members",
        "description": "List members of a project.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "integer"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "add_member",
        "description": "Add a member to a project with a role.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "username": {"type": "string"},
                "role": {"type": "string", "enum": ["owner", "editor", "reviewer", "viewer"]},
            },
            "required": ["project_id", "username", "role"],
        },
    },
    {
        "name": "list_audit_events",
        "description": "List audit events for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["project_id"],
        },
    },
]
```

### 7.5 `mcp/tools.py` — Handler Functions

```python
from .models import Projects, ProjectMember, ProjectRequirement, RequirementEvidence, RequirementComment, AuditEvent
from asvs.settings import AUTH_USER_MODEL

def _get_project(id) -> Projects:
    try:
        return Projects.objects.get(id=id)
    except Projects.DoesNotExist:
        raise ValueError(f"Project {id} does not exist")

def _get_requirement(id) -> ProjectRequirement:
    try:
        return ProjectRequirement.objects.get(id=id)
    except ProjectRequirement.DoesNotExist:
        raise ValueError(f"Requirement {id} does not exist")

def _project_dict(p):
    return {
        'id': p.id,
        'project_name': p.project_name,
        'project_owner': p.project_owner,
        'project_description': p.project_description,
        'project_level': p.project_level,
        'asvs_version': p.asvs_version,
        'project_created': p.project_created.isoformat(),
        'project_allowed_viewers': p.project_allowed_viewers,
    }

def _requirement_dict(r):
    return {
        'id': r.id, 'project_id': r.project_id, 'req_id': r.req_id,
        'status': r.status, 'note': r.note, 'chapter_id': r.chapter_id,
        'section_id': r.section_id, 'level1': r.level1, 'level2': r.level2,
        'level3': r.level3,
    }

def list_projects(request, params):
    qs = Projects.objects.all()
    level = params.get('level')
    owner = params.get('owner')
    if level:
        qs = qs.filter(project_level=level)
    if owner:
        qs = qs.filter(project_owner=owner)
    return [
        {
            'id': p.id,
            'project_name': p.project_name,
            'project_owner': p.project_owner,
            'project_description': p.project_description,
            'project_level': p.project_level,
            'asvs_version': p.asvs_version,
            'project_created': p.project_created.isoformat(),
            'project_allowed_viewers': p.project_allowed_viewers,
        }
        for p in qs
    ]

def get_project(request, params):
    p = _get_project(params['id'])
    return _project_dict(p)

def create_project(request, params):
    p = Projects.objects.create(
        project_name=params['project_name'],
        project_description=params['project_description'],
        project_level=params.get('project_level', 0),
        project_owner=request.user.username,
        asvs_version=params.get('asvs_version', '5.0'),
    )
    return _project_dict(p)

def update_project(request, params):
    p = _get_project(params['id'])
    for field in ('project_name', 'project_description', 'project_level', 'asvs_version', 'project_allowed_viewers'):
        if field in params:
            setattr(p, field, params[field])
    p.save()
    return _project_dict(p)

def delete_project(request, params):
    _get_project(params['id']).delete()
    return {'status': 'deleted'}

def get_requirements(request, params):
    qs = ProjectRequirement.objects.filter(project_id=params['project_id'])
    status = params.get('status')
    if status:
        qs = qs.filter(status=status)
    return [
        {**_requirement_dict(r)}
        for r in qs
    ]

def get_requirement(request, params):
    r = _get_requirement(params['id'])
    return {
        **_requirement_dict(r),
        'evidence': [{'id': e.id, 'title': e.title, 'url': e.url, 'notes': e.notes} for e in r.evidence.all()],
        'comments': [{'id': c.id, 'body': c.body, 'created_by': c.created_by} for c in r.comments.all()],
    }

def update_requirement_status(request, params):
    r = _get_requirement(params['id'])
    r.status = params['status']
    r.note = params.get('note', '')
    r.save()
    return _requirement_dict(r)

def add_evidence(request, params):
    req = _get_requirement(params['requirement_id'])
    e = RequirementEvidence.objects.create(
        requirement=req, title=params['title'], url=params.get('url', ''), notes=params.get('notes', ''),
        created_by=request.user.username,
    )
    return {'id': e.id, 'title': e.title, 'url': e.url, 'notes': e.notes}

def add_comment(request, params):
    req = _get_requirement(params['requirement_id'])
    c = RequirementComment.objects.create(
        requirement=req, body=params['body'], created_by=request.user.username,
    )
    return {'id': c.id, 'body': c.body, 'created_by': c.created_by}

def list_members(request, params):
    members = ProjectMember.objects.filter(project_id=params['project_id'])
    return [{'id': m.id, 'username': m.username, 'role': m.role} for m in members]

def add_member(request, params):
    p = _get_project(params['project_id'])
    m, _ = ProjectMember.objects.get_or_create(project=p, username=params['username'], defaults={'role': params['role']})
    return {'id': m.id, 'username': m.username, 'role': m.role}

def list_audit_events(request, params):
    ...
```

### 7.6 `mcp/app.py` — JSON-RPC View

```python
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .schema import TOOLS
from . import tools

def dispatch_tool(request, tool_name, params):
    fn = getattr(tools, tool_name, None)
    if not fn:
        raise ValueError(f"Unknown tool: {tool_name}")
    return fn(request, params or {})

@require_POST
@csrf_exempt
def mcp_endpoint(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    method = body.get('method')
    params = body.get('params', {})
    id_ = body.get('id', 0)

    if method == 'listTools':
        tools_list = [{"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]} for t in TOOLS]
        return JsonResponse({"jsonrpc": "2.0", "result": {"tools": tools_list}, "id": id_})

    elif method == 'callTool':
        tool_name = params.get('name')
        tool_params = params.get('arguments', {})
        try:
            result = dispatch_tool(request, tool_name, tool_params)
            return JsonResponse({"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}, "id": id_})
        except Exception as e:
            return JsonResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": id_,
            }, status=500)

    elif method == 'ping':
        return JsonResponse({"jsonrpc": "2.0", "result": "ok", "id": id_})

    return JsonResponse({"error": f"Unknown method: {method}"}, status=400)
```

### 7.7 Add `mcp/` to Django

```
# mcp/__init__.py
default_app_config = 'mcp.apps.McpConfig'

# mcp/apps.py
from django.apps import AppConfig

class McpConfig(AppConfig):
    name = 'mcp'
    default = True
```

Add `'mcp'` to `INSTALLED_APPS`.

### 7.8 Wire MCP into `asvs/urls.py`

```python
from mcp.app import mcp_endpoint

path('api/mcp/', mcp_endpoint, name='mcp-endpoint'),
```

---

## 8. Endpoint Summary

### OpenAPI API (`/api/`)

| Verb | Path | Description |
|------|------|-------------|
| GET | `/api/projects/` | List projects |
| POST | `/api/projects/` | Create project |
| GET | `/api/projects/{id}/` | Get project |
| PUT | `/api/projects/{id}/` | Update project |
| DELETE | `/api/projects/{id}/` | Delete project |
| GET | `/api/projects/{id}/requirements/` | List project requirements |
| GET | `/api/projects/{id}/audit_events/` | List project audit events |
| POST | `/api/projects/{id}/export_csv/` | Export project as CSV |
| PATCH | `/api/requirements/{id}/` | Update requirement (status, notes) |
| POST | `/api/requirements/{id}/evidence/` | Add evidence |
| POST | `/api/requirements/{id}/comments/` | Add comment |
| GET | `/api/users/me/` | Get current user |
| GET | `/api/schema/` | OpenAPI 3.0 JSON spec |
| GET | `/api/docs/` | Swagger UI |

### MCP Endpoint (`/api/mcp/`)

| Method | Description |
|--------|-------------|
| `listTools` | Returns all available tools with JSON Schema |
| `callTool` | Calls a tool by name with arguments |
| `ping` | Health check |

Example request:
```json
POST /api/mcp/
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "listTools"
}
```

Example response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {"name": "list_projects", "description": "...", "inputSchema": {...}},
      {"name": "update_requirement_status", "description": "...", "inputSchema": {...}}
    ]
  }
}
```

---

## 9. File Structure After Implementation

```
asvs/
├── asvs/
│   ├── settings.py          # add rest_framework, drf_spectacular, mcp
│   ├── urls.py               # add api/ routes
│   └── ...
├── accountauth/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── serializers.py    # UserSerializer
│   │   ├── viewsets.py       # UserViewSet
│   │   └── urls.py           # Router for users, keep TOTP
├── projects/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── serializers.py    # Project, Member, Requirement, Evidence, Comment serializers
│   │   ├── viewsets.py       # All ViewSets + nested actions
│   │   └── urls.py           # DefaultRouter
├── mcp/
│   ├── __init__.py
│   ├── apps.py               # McpConfig
│   ├── app.py                # MCP JSON-RPC view (entry point)
│   ├── tools.py              # Tool handler functions
│   └── schema.py             # Tool registry with descriptions + JSON Schema
├── requirements.txt          # add drf-spectacular
└── ...
```

---

## 10. Implementation Order

1. **Setup** — add `drf-spectacular` to `requirements.txt`, update `settings.py`
2. **Serializers** — write all serializers
3. **ViewSets** — write all ViewSets, wire up routes
4. **Verify API** — confirm `/api/docs/` loads OpenAPI + Swagger
5. **MCP server** — implement JSON-RPC endpoint + tool handlers
6. **Test** — verify MCP endpoint with curl or agent

---

## 11. Risks & Considerations

| Risk | Mitigation |
|------|----------|
| Existing function-based views still work | New API is under `/api/` prefix — no conflict with existing views |
| Auth model fields (`project_owner` is a string `CharField`) | Serializers handle string fields; consider migrating to `ForeignKey(User)` later |
| TOTP views currently use `accountauth.urls` — no `/api/` prefix | Move TOTP views to `accountauth/api/urls.py` or keep as-is alongside API under different URL config |
| MCP has no auth layer initially | Use DRF token auth or session auth on the MCP endpoint; add JWT later for API |
| `request.user` not available in JSON-RPC handler | Use session auth with cookie, or pass `Authorization: Bearer <token>` in MCP calls |
| Nested serializers create N+1 queries | Add `.select_related('project__project_owner')` and `.prefetch_related('members', 'requirements__evidence')` in ViewSet querysets |

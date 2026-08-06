from projects.models import Projects, ProjectMember, ProjectRequirement, RequirementEvidence, RequirementComment


def _get_project(id):
    try:
        return Projects.objects.get(id=id)
    except Projects.DoesNotExist:
        raise ValueError(f"Project {id} does not exist")


def _get_requirement(id):
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
    project_id = params['project_id']
    limit = params.get('limit', 50)
    events = Projects.objects.get(id=project_id).audit_events.all()[:limit]
    return [
        {
            'id': e.id,
            'actor': e.actor,
            'action': e.action,
            'detail': e.detail,
            'created_at': e.created_at.isoformat(),
        }
        for e in events
    ]

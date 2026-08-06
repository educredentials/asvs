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
                "status": {"type": "string", "enum": ["na", "incomplete", "complete", "review"]},
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
                "status": {"type": "string", "enum": ["na", "incomplete", "complete", "review"]},
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

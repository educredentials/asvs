---
name: asvs-updater
description: Update ASVS requirements with notes and evidence via the ASVS MCP server. Use when the user wants to update OWASP ASVS requirement statuses, add evidence links, or mark requirements as complete/incomplete/review/na for a project. Supports per-section mode (interactive per-requirement) and full-scan mode (all requirements in a section).
---

# ASVS Updater

Use this skill to update OWASP ASVS requirements in the ASVS project management system via the MCP server. Evidence links point to source code (GitHub or GitLab) for full traceability.

## Prerequisites

The ASVS MCP server must be configured in `~/.config/opencode/opencode.json` (already done — remote at `asvs.educredentials.nl`).

## MCP Tools Reference

All tools are available via MCP calls to the `asvs` server. If a call times out, retry up to 3 times with ~2s backoff before failing.

| Tool | Args | Returns | Use |
|------|------|---------|-----|
| `list_projects` | `level?`, `owner?` | Array of `{id, project_name, project_owner, project_description, project_level, asvs_version, project_created, project_allowed_viewers}` | Show available projects |
| `get_project` | `id` | Single project object | Get project details |
| `get_requirements` | `project_id`, `status?` | Array of requirement dicts (see below) | List requirements for a project |
| `get_requirement` | `id` | Requirement with `evidence[]` and `comments[]` arrays | Get single requirement with details |
| `update_requirement_status` | `id`, `status`, `note?` | Updated requirement dict | Set status + note |
| `add_evidence` | `requirement_id`, `title`, `url`, `notes?` | Evidence object `{id, title, url, notes}` | Link evidence to a requirement |

**Status values:** `na`, `incomplete`, `complete`, `review`

**Requirement dict shape:** `{id, project_id, req_id, status, note, chapter_id, section_id, level1, level2, level3, req_description}`

## Git Remote Discovery

Before gathering evidence, discover the project's git remotes:

```bash
git remote -v
```

Use the first HTTPS remote found. If multiple remotes exist, ask the user which to use.

**Remote-to-URL mapping:**

- `github.com` → `https://github.com/{owner}/{repo}/blob/{branch}/{path}:{line}`
- `gitlab.com` or self-hosted GitLab → `https://{host}/{owner}/{repo}/-/blob/{branch}/{path}:{line}`

To find the owner/repo from the remote URL:
```bash
# From origin URL like git@github.com:owner/repo.git or https://host/owner/repo.git
# owner = first path segment after / or :
# repo = second path segment, strip .git
```

To find the default branch:
```bash
git remote show origin | grep "HEAD branch" | awk '{print $NF}'
```

## Workflow A: Per-Section Update

When the user wants to update a specific ASVS section (e.g., "4.2 Validations"):

1. **Select project**
   - Call `list_projects` to show available projects
   - Display: `ID — Project Name (Level {N}) — Owner: {owner}`
   - Ask the user to pick by number or name

2. **Get requirements for the section**
   - Call `get_requirements` with `project_id`
   - Filter results by `chapter_id` matching the requested section (e.g., chapter_id=4 for "4.x" sections)
   - Show the user: `{req_id}: {req_description} [L1={level1}, L2={level2}, L3={level3}]`

3. **Process each requirement iteratively** (NOT all at once):
   For each requirement:
   a. Ask the user: "Status for {req_id} ({req_description})?"
      - Default to `review`
      - Allow: `complete`, `incomplete`, `na`, `review`
   b. Ask for a brief note (or accept empty — defaults to a short description)
   c. Ask about evidence:
      - Option 1: "Provide evidence URL(s) — or skip"
        - User provides URL(s) directly
      - Option 2: "Search codebase for evidence of {req_description}?"
        - Search codebase for relevant code (search patterns related to the requirement)
        - For each match, generate a git remote URL
        - User confirms which ones to add as evidence
   d. Call `update_requirement_status` with `id`, `status`, `note`
   e. For each evidence URL, call `add_evidence` with `requirement_id`, `title` (brief description), `url`, `notes`
   f. Continue to next requirement

4. **Report**
   Show summary + detailed diff:

   **Summary:**
   ```
   ASVS Update Complete
   Project: {name}
   Section: {chapter_id}
   Requirements updated: {count}
   Evidence links added: {count}
   ```

   **Detail:**
   ```
   ✓ {req_id}: {status} — {note}
     Evidence:
       - {title} → {url}
   ```

## Workflow B: Full Section Scan

When the user wants to scan all requirements in a section:

1. Same as Workflow A steps 1-2
2. For each requirement in the section, apply the same iterative process (step 3 from Workflow A)
3. Report the same summary + detail format

The key difference: the user explicitly requests scanning an entire section rather than a single requirement.

## Evidence Link Construction

Each evidence entry must contain:
- **title**: Brief description of what the evidence proves (1-2 sentences)
- **url**: Full source code URL (GitHub or GitLab blob link)
- **notes**: Optional additional context

Evidence URL patterns:
- **GitHub**: `https://github.com/{owner}/{repo}/blob/{branch}/{file_path}`
- **GitLab**: `https://{gitlab.host}/{owner}/{repo}/-/blob/{branch}/{file_path}`

## Important Rules

- **Per-requirement interaction is mandatory.** Do NOT batch-update multiple requirements without confirming each one. Every requirement has its own status and note.
- **Evidence must be real.** Do not fabricate URLs. If no evidence exists, skip it and note that.
- **Retry on timeout.** MCP calls can timeout — retry 3 times with 2s backoff before failing.
- **Default status is `review`.** When updating, use `review` unless the user specifies otherwise.
- **Notes should be brief.** One line summarizing the implementation or finding.
- **Use the MCP tool, not the REST API directly.** The MCP tools wrap the API — always prefer the MCP tool calls.
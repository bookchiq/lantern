from __future__ import annotations

from typing import Any, Dict, Iterable, List

import httpx

from ..config import Config
from ..documents import Document


ASANA_BASE_URL = "https://app.asana.com/api/1.0"


def _ensure_asana_config(config: Config) -> None:
    if not config.asana_pat:
        raise RuntimeError("Missing LANTERN_ASANA_PAT for Asana ingestion.")

    if not config.asana_project_gid and not config.asana_user_gid:
        raise RuntimeError(
            "Set either LANTERN_ASANA_PROJECT_GID or LANTERN_ASANA_USER_GID to fetch tasks."
        )

    if config.asana_user_gid and not config.asana_workspace_gid:
        raise RuntimeError("LANTERN_ASANA_WORKSPACE_GID is required when using user search.")


def _asana_headers(config: Config) -> Dict[str, str]:
    return {"Authorization": f"Bearer {config.asana_pat}"}


def _opt_fields() -> str:
    return ",".join(
        [
            "gid",
            "name",
            "notes",
            "completed",
            "due_on",
            "due_at",
            "assignee.name",
            "assignee.gid",
            "projects.name",
            "projects.gid",
            "permalink_url",
            "memberships.project.gid",
            "memberships.project.name",
            "memberships.section.gid",
            "memberships.section.name",
            "custom_fields.gid",
            "custom_fields.name",
            "custom_fields.type",
            "custom_fields.number_value",
            "custom_fields.text_value",
            "custom_fields.enum_value.name",
            "custom_fields.enum_value.gid",
        ]
    )


def _fetch_paginated(
    client: httpx.Client,
    url: str,
    params: Dict[str, Any],
    total_limit: int,
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    offset: str | None = None
    per_page = min(100, total_limit)

    while len(tasks) < total_limit:
        request_params = dict(params)
        request_params["limit"] = per_page
        if offset:
            request_params["offset"] = offset

        response = client.get(url, params=request_params)
        response.raise_for_status()
        payload = response.json()

        page_data = payload.get("data", [])
        tasks.extend(page_data)
        if len(tasks) >= total_limit:
            break

        next_page = payload.get("next_page")
        if not next_page:
            break
        offset = next_page.get("offset")
        if not offset:
            break

    return tasks[:total_limit]


def _task_to_document(task: Dict[str, Any], config: Config) -> Document:
    gid = task.get("gid", "")
    name = task.get("name") or "(untitled)"
    notes = task.get("notes") or ""
    completed = bool(task.get("completed") or False)
    due_on = task.get("due_on")
    due_at = task.get("due_at")
    permalink_url = task.get("permalink_url")

    assignee = task.get("assignee") or {}
    assignee_name = assignee.get("name")
    assignee_gid = assignee.get("gid")
    assignee_label = assignee_name or "Unassigned"
    if assignee_gid:
        assignee_label = f"{assignee_label} ({assignee_gid})"

    projects = task.get("projects") or []
    project_gids = [project.get("gid") for project in projects if project.get("gid")]
    project_names = [project.get("name") for project in projects if project.get("name")]

    doc_id = f"asana:task:{gid}"

    lines = [
        f"Task: {name}",
        f"Completed: {completed}",
        f"Due on: {due_on}",
        f"Due at: {due_at}",
        f"Assignee: {assignee_label}",
        f"Projects: {', '.join(project_names) if project_names else 'None'}",
        f"Permalink: {permalink_url}",
        "",
        "Notes:",
        notes,
    ]
    text = "\n".join(line for line in lines if line is not None)

    metadata = {
        "doc_id": doc_id,
        "source_type": "asana",
        "source_path": doc_id,
        "file_name": name,
        "asana_task_gid": gid,
        "asana_permalink_url": permalink_url,
        "completed": completed,
        "due_on": due_on,
        "due_at": due_at,
        "assignee_name": assignee_name,
        "assignee_gid": assignee_gid,
        "project_gids": ", ".join(project_gids),
        "project_names": ", ".join(project_names),
        "workspace_gid": config.asana_workspace_gid,
    }

    return Document(text=text, metadata=metadata)


def load_asana_tasks(config: Config) -> List[Document]:
    _ensure_asana_config(config)

    headers = _asana_headers(config)
    opt_fields = _opt_fields()
    tasks: List[Dict[str, Any]] = []

    with httpx.Client(base_url=ASANA_BASE_URL, headers=headers, timeout=30.0) as client:
        if config.asana_project_gid:
            url = f"/projects/{config.asana_project_gid}/tasks"
            params = {"opt_fields": opt_fields}
        else:
            url = f"/workspaces/{config.asana_workspace_gid}/tasks/search"
            params = {
                "assignee.any": config.asana_user_gid,
                "opt_fields": opt_fields,
            }

        tasks = _fetch_paginated(client, url, params, config.asana_limit)

    return [_task_to_document(task, config) for task in tasks]

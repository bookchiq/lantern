from __future__ import annotations

from typing import Any, Dict, Iterable, List

import httpx

from datetime import date, timedelta

from ..config import Config
from ..documents import Document


ASANA_BASE_URL = "https://app.asana.com/api/1.0"

# Custom field gid for "Estimated Time (Yoko)".
ESTIMATED_TIME_FIELD_GID = "1136060183433384"


def _ensure_asana_config(config: Config) -> None:
    if not config.asana_pat:
        raise RuntimeError("Missing LANTERN_ASANA_PAT for Asana ingestion.")

    if not config.asana_project_gid and not config.asana_user_gid:
        raise RuntimeError(
            "Set either LANTERN_ASANA_PROJECT_GID or LANTERN_ASANA_USER_GID to fetch tasks."
        )

    if not config.asana_workspace_gid:
        raise RuntimeError("LANTERN_ASANA_WORKSPACE_GID is required for Asana task search.")


def _asana_headers(config: Config) -> Dict[str, str]:
    return {"Authorization": f"Bearer {config.asana_pat}"}


def _opt_fields() -> str:
    return ",".join(
        [
            "gid",
            "name",
            "notes",
            "completed",
            "completed_on",
            "due_on",
            "due_at",
            "assignee.name",
            "assignee.gid",
            "assignee_section.gid",
            "assignee_section.name",
            "projects.name",
            "projects.gid",
            "memberships.project.gid",
            "memberships.project.name",
            "memberships.section.gid",
            "memberships.section.name",
            "custom_fields.gid",
            "custom_fields.name",
            "custom_fields.type",
            "custom_fields.number_value",
            "custom_fields.text_value",
            "custom_fields.enum_value.gid",
            "custom_fields.enum_value.name",
            "permalink_url",
        ]
    )



def _extract_estimated_time(task: Dict[str, Any]) -> float | None:
    custom_fields = task.get("custom_fields") or []
    for field in custom_fields:
        if str(field.get("gid")) != ESTIMATED_TIME_FIELD_GID:
            continue
        number_value = field.get("number_value")
        if isinstance(number_value, (int, float)):
            return float(number_value)
        text_value = field.get("text_value")
        if text_value:
            try:
                return float(str(text_value).strip())
            except ValueError:
                return None
    return None


def _extract_memberships(task: Dict[str, Any]) -> Dict[str, Any]:
    memberships = task.get("memberships") or []
    project_gids: List[str] = []
    project_names: List[str] = []
    section_gids: List[str] = []
    section_names: List[str] = []

    for mem in memberships:
        proj = mem.get("project") or {}
        sec = mem.get("section") or {}

        pgid = proj.get("gid")
        pname = proj.get("name")
        sgid = sec.get("gid")
        sname = sec.get("name")

        if pgid:
            project_gids.append(str(pgid))
        if pname:
            project_names.append(str(pname))
        if sgid:
            section_gids.append(str(sgid))
        if sname:
            section_names.append(str(sname))

    return {
        "membership_project_gids": project_gids,
        "membership_project_names": project_names,
        "membership_section_gids": section_gids,
        "membership_section_names": section_names,
    }


def _assignee_section_for_project(task: Dict[str, Any], project_gid: str | None) -> tuple[str | None, str | None]:
    if not project_gid:
        return None, None
    memberships = task.get("memberships") or []
    for mem in memberships:
        proj = mem.get("project") or {}
        if str(proj.get("gid")) != str(project_gid):
            continue
        sec = mem.get("section") or {}
        return (str(sec.get("gid")) if sec.get("gid") else None, sec.get("name"))
    return None, None




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
    completed_on = task.get("completed_on")
    due_on = task.get("due_on")
    due_at = task.get("due_at")
    permalink_url = task.get("permalink_url")

    assignee = task.get("assignee") or {}
    assignee_name = assignee.get("name")
    assignee_gid = assignee.get("gid")

    assignee_section = task.get("assignee_section") or {}
    assignee_section_gid_global = assignee_section.get("gid")
    assignee_section_name_global = assignee_section.get("name")
    assignee_label = assignee_name or "Unassigned"
    if assignee_gid:
        assignee_label = f"{assignee_label} ({assignee_gid})"

    projects = task.get("projects") or []
    project_gids = [project.get("gid") for project in projects if project.get("gid")]
    project_names = [project.get("name") for project in projects if project.get("name")]

    memberships_info = _extract_memberships(task)
    assignee_section_gid, assignee_section_name = _assignee_section_for_project(task, config.asana_project_gid)
    estimated_time_yoko = _extract_estimated_time(task)

    doc_id = f"asana:task:{gid}"

    lines = [
        f"Task: {name}",
        f"Completed: {completed}",
        f"Completed on: {completed_on}",
        f"Due on: {due_on}",
        f"Due at: {due_at}",
        f"Assignee: {assignee_label}",
        f"Projects: {', '.join(project_names) if project_names else 'None'}",
        f"Assignee section gid: {assignee_section_gid}",
        f"Assignee section: {assignee_section_name}",
        f"Assignee section (global) gid: {assignee_section_gid_global}",
        f"Assignee section (global): {assignee_section_name_global}",
        f"Estimated Time (Yoko): {estimated_time_yoko}",
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
        "task_name": name,
        "completed": completed,
        "completed_on": completed_on,
        "due_on": due_on,
        "due_at": due_at,
        "assignee_name": assignee_name,
        "assignee_gid": assignee_gid,
        "assignee_section_gid_global": assignee_section_gid_global,
        "assignee_section_name_global": assignee_section_name_global,
        "project_gids": ", ".join(project_gids),
        "project_names": ", ".join(project_names),
        "workspace_gid": config.asana_workspace_gid,
    }

    return Document(text=text, metadata=metadata)


def load_asana_tasks(config: Config) -> List[Document]:
    """Load Asana tasks.

    Strategy:
    - Use the workspace task search endpoint for both project-scoped and user-scoped pulls.
    - Fetch (A) incomplete tasks and (B) tasks completed within the last N days (default 7).
    - Merge and de-duplicate by gid.
    """
    _ensure_asana_config(config)

    headers = _asana_headers(config)
    opt_fields = _opt_fields()

    scope_params: Dict[str, Any] = {"opt_fields": opt_fields}

    if config.asana_project_gid:
        scope_params["projects.any"] = config.asana_project_gid
    if config.asana_user_gid and not config.asana_project_gid:
        scope_params["assignee.any"] = config.asana_user_gid

    today = date.today()
    lookback_days = getattr(config, "asana_completed_lookback_days", 7)
    completed_after = (today - timedelta(days=lookback_days)).isoformat()

    results_by_gid: Dict[str, Dict[str, Any]] = {}

    with httpx.Client(base_url=ASANA_BASE_URL, headers=headers, timeout=30.0) as client:
        search_url = f"/workspaces/{config.asana_workspace_gid}/tasks/search"

        params_incomplete = dict(scope_params)
        params_incomplete["completed"] = False
        tasks_incomplete = _fetch_paginated(client, search_url, params_incomplete, config.asana_limit)
        for task in tasks_incomplete:
            gid = str(task.get("gid") or "")
            if gid:
                results_by_gid[gid] = task

        params_completed = dict(scope_params)
        params_completed["completed"] = True
        params_completed["completed_on.after"] = completed_after
        tasks_completed = _fetch_paginated(client, search_url, params_completed, config.asana_limit)
        for task in tasks_completed:
            gid = str(task.get("gid") or "")
            if gid:
                results_by_gid[gid] = task

    return [_task_to_document(task, config) for task in results_by_gid.values()]
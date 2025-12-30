#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from lantern.config import load_config
from lantern.vectorstore import get_collection


PINGPONG_SECTION_DEFAULT = "1200892062747278"  # "🏓 The ball is in your court"


def _parse_iso_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.strip().lower() in {"none", "null", "nan"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_csvish(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    return [part.strip() for part in str(value).split(",") if part.strip()]


@dataclass
class TaskRow:
    gid: str
    name: str
    permalink_url: str
    completed: bool
    completed_on: Optional[date]
    due_on: Optional[date]
    estimated_time_yoko: Optional[float]
    assignee_gid: Optional[str]
    assignee_section_gid: Optional[str]
    project_gids: List[str]
    project_names: List[str]
    score: float
    reasons: List[str]
    is_in_pingpong: bool


def _fetch_all_asana_docs(config, batch_size: int = 1000) -> List[Dict[str, Any]]:
    """Fetch all Asana docs from Chroma (non-semantic)."""
    collection = get_collection(config.chroma_dir)

    docs: List[Dict[str, Any]] = []
    offset = 0

    while True:
        try:
            res = collection.get(
                where={"source_type": "asana"},
                include=["documents", "metadatas"],
                limit=batch_size,
                offset=offset,
            )
        except TypeError:
            # Older Chroma API: filter client-side.
            res = collection.get(include=["documents", "metadatas"])
            ids = res.get("ids", []) or []
            metas = res.get("metadatas", []) or []
            texts = res.get("documents", []) or []
            for tid, md, text in zip(ids, metas, texts):
                md = md or {}
                if md.get("source_type") != "asana":
                    continue
                docs.append({"id": str(tid), "metadata": md, "text": text})
            return docs

        ids = res.get("ids", []) or []
        metas = res.get("metadatas", []) or []
        texts = res.get("documents", []) or []

        if not ids:
            break

        for tid, md, text in zip(ids, metas, texts):
            docs.append({"id": str(tid), "metadata": md or {}, "text": text})

        if len(ids) < batch_size:
            break

        offset += batch_size

    return docs



def _is_effectively_empty(value: Any) -> bool:
    if value in (None, ""):
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    if isinstance(value, str) and value.strip().lower() in {"none", "null", "nan"}:
        return True
    return False


def _dedupe_by_task_gid(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse chunk-level records into one record per Asana task.

    In Chroma we store multiple chunks per task (same task metadata, different text).
    For deterministic prioritization, we want unique tasks.
    """
    by_gid: Dict[str, Dict[str, Any]] = {}

    for d in docs:
        md = d.get("metadata", {}) or {}
        gid = str(md.get("asana_task_gid") or md.get("gid") or md.get("task_gid") or d.get("id") or "")
        if not gid:
            continue

        existing = by_gid.get(gid)
        if existing is None:
            by_gid[gid] = d
            continue

        ex_md = existing.get("metadata", {}) or {}
        for k, v in md.items():
            if v is None:
                continue
            if (k not in ex_md) or _is_effectively_empty(ex_md.get(k)):
                ex_md[k] = v
        existing["metadata"] = ex_md

    return list(by_gid.values())


def _project_end_dates(docs: List[Dict[str, Any]]) -> Dict[str, date]:
    """Compute project end date as max due_on across ingested tasks per project_gid."""
    end_by_project: Dict[str, date] = {}

    for d in docs:
        md = d.get("metadata", {}) or {}
        due = _parse_iso_date(md.get("due_on"))
        if not due:
            continue

        project_gids = _split_csvish(md.get("project_gids")) or _split_csvish(md.get("membership_project_gids"))
        for pgid in project_gids:
            current = end_by_project.get(pgid)
            if current is None or due > current:
                end_by_project[pgid] = due

    return end_by_project


def _score_task(
    today: date,
    due_on: Optional[date],
    project_end_in_days: Optional[int],
    estimated_time: Optional[float],
    is_overdue: bool,
    overdue_exempt: bool,
) -> Tuple[float, List[str]]:
    """Return (score, reasons). Higher score = higher priority."""
    score = 0.0
    reasons: List[str] = []

    if is_overdue and not overdue_exempt:
        days_overdue = (today - due_on).days if due_on else 0
        score += 1000.0 + 10.0 * float(days_overdue)
        reasons.append(f"overdue ({days_overdue}d)")
    elif is_overdue and overdue_exempt:
        reasons.append("overdue but exempt (🏓 section)")

    if due_on:
        days_to_due = (due_on - today).days
        score += 100.0 / max(abs(days_to_due), 1)
        reasons.append(f"due {days_to_due:+}d")

    if estimated_time is not None:
        score += 20.0 * float(estimated_time)
        reasons.append(f"est {estimated_time:g}h")

    if project_end_in_days is not None:
        score += 200.0 / max(project_end_in_days, 1)
        reasons.append(f"proj ends in {project_end_in_days}d")

    return score, reasons


def _row_from_doc(doc: Dict[str, Any], today: date, project_end: Dict[str, date], pingpong_section_gid: str) -> TaskRow:
    md = doc.get("metadata", {}) or {}

    gid = str(md.get("asana_task_gid") or doc.get("id") or "")
    name = str(md.get("task_name") or md.get("name") or gid)
    permalink_url = str(md.get("asana_permalink_url") or md.get("permalink_url") or "")

    completed = bool(md.get("completed") is True)
    completed_on = _parse_iso_date(md.get("completed_on"))
    due_on = _parse_iso_date(md.get("due_on"))
    estimated_time = _parse_float(md.get("estimated_time_yoko"))

    assignee_gid = md.get("assignee_gid")
    if assignee_gid is not None:
        assignee_gid = str(assignee_gid)

    assignee_section_gid = md.get("assignee_section_gid")
    if assignee_section_gid is not None:
        assignee_section_gid = str(assignee_section_gid)

    assignee_section_gid_global = md.get("assignee_section_gid_global")
    if assignee_section_gid_global is not None:
        assignee_section_gid_global = str(assignee_section_gid_global)

    project_gids = _split_csvish(md.get("project_gids")) or _split_csvish(md.get("membership_project_gids"))
    project_names = _split_csvish(md.get("project_names")) or _split_csvish(md.get("membership_project_names"))

    project_end_in_days: Optional[int] = None
    if project_gids:
        ends = [project_end.get(pgid) for pgid in project_gids if pgid in project_end]
        if ends:
            soonest_end = min(ends)
            project_end_in_days = max((soonest_end - today).days, 0)

    is_overdue = bool(due_on and due_on < today and not completed)
    membership_section_gids = _split_csvish(md.get("membership_section_gids"))
    is_in_pingpong = (
        (assignee_section_gid == pingpong_section_gid)
        or (assignee_section_gid_global == pingpong_section_gid)
        or (pingpong_section_gid in membership_section_gids)
    )
    overdue_exempt = bool(is_overdue and is_in_pingpong)

    score, reasons = _score_task(
        today=today,
        due_on=due_on,
        project_end_in_days=project_end_in_days,
        estimated_time=estimated_time,
        is_overdue=is_overdue,
        overdue_exempt=overdue_exempt,
    )

    return TaskRow(
        gid=gid,
        name=name,
        permalink_url=permalink_url,
        completed=completed,
        completed_on=completed_on,
        due_on=due_on,
        estimated_time_yoko=estimated_time,
        assignee_gid=assignee_gid,
        assignee_section_gid=assignee_section_gid,
        project_gids=project_gids,
        project_names=project_names,
        score=score,
        reasons=reasons,
        is_in_pingpong=is_in_pingpong,
    )


def _format_row(idx: int, row: TaskRow) -> str:
    due = row.due_on.isoformat() if row.due_on else "-"
    est = f"{row.estimated_time_yoko:g}h" if row.estimated_time_yoko is not None else "-"
    proj = row.project_names[0] if row.project_names else (row.project_gids[0] if row.project_gids else "-")
    reasons = "; ".join(row.reasons)
    return f"{idx:>2}. {row.score:>7.1f} | due {due:<10} | est {est:<5} | {proj:<24} | {row.name} ({reasons})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministically prioritize Asana tasks from the local Chroma store.")
    parser.add_argument("--top", type=int, default=20, help="How many tasks to display (default 20).")
    parser.add_argument("--include-completed", action="store_true", help="Include completed tasks (default: exclude).")
    parser.add_argument("--include-unassigned", action="store_true", help="Include unassigned tasks (default: exclude when LANTERN_ASANA_USER_GID is set).")
    parser.add_argument("--include-not-assigned", action="store_true", help="Include tasks assigned to other people (default: exclude when LANTERN_ASANA_USER_GID is set).")
    parser.add_argument("--completed-lookback-days", type=int, default=7, help="When including completed, only include tasks completed in the last N days (default 7).")
    parser.add_argument("--today", type=str, default=None, help="Override 'today' as YYYY-MM-DD (default: system date).")
    parser.add_argument("--pingpong-section-gid", type=str, default=PINGPONG_SECTION_DEFAULT, help="Assignee section gid to treat as blocked/ping-pong.")
    parser.add_argument("--include-pingpong", action="store_true", help="Include tasks in the ping-pong section (default: excluded).")
    parser.add_argument("--csv", type=str, default=None, help="Write full ranked output to a CSV file path.")
    args = parser.parse_args()

    config = load_config()

    if args.today:
        try:
            today = date.fromisoformat(args.today)
        except ValueError:
            raise SystemExit("--today must be YYYY-MM-DD")
    else:
        today = date.today()

    docs = _fetch_all_asana_docs(config)
    docs = _dedupe_by_task_gid(docs)
    if not docs:
        print("No Asana tasks found in Chroma. Run: python scripts/ingest_asana.py")
        return 1

    project_end = _project_end_dates(docs)

    rows: List[TaskRow] = []
    for d in docs:
        row = _row_from_doc(d, today, project_end, args.pingpong_section_gid)

        # Only include tasks assigned to the configured user by default.
        configured_user_gid = getattr(config, "asana_user_gid", None)
        if configured_user_gid:
            configured_user_gid = str(configured_user_gid)
            is_unassigned = row.assignee_gid in (None, "")
            is_assigned_to_me = (row.assignee_gid == configured_user_gid)
            if (not is_assigned_to_me) and (not args.include_not_assigned):
                if not is_unassigned:
                    continue
            if is_unassigned and (not args.include_unassigned):
                continue

        if row.completed and not args.include_completed:
            continue

        if row.completed and args.include_completed:
            if row.completed_on is None:
                continue
            days_ago = (today - row.completed_on).days
            if days_ago > args.completed_lookback_days:
                continue

        # Exclude ping-pong/blocked tasks by default.
        if row.is_in_pingpong and (not args.include_pingpong):
            continue

        rows.append(row)

    rows.sort(key=lambda r: r.score, reverse=True)

    print(f"Today: {today.isoformat()} | Tasks considered: {len(rows)} | Total Asana docs: {len(docs)}")
    print("Top tasks:")
    for idx, row in enumerate(rows[: max(args.top, 0)], start=1):
        print(_format_row(idx, row))

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "rank",
                "score",
                "task_gid",
                "task_name",
                "permalink_url",
                "completed",
                "completed_on",
                "due_on",
                "estimated_time_yoko",
                "assignee_gid",
                "assignee_section_gid",
                "project_gids",
                "project_names",
                "reasons",
            ])
            for idx, row in enumerate(rows, start=1):
                writer.writerow([
                    idx,
                    f"{row.score:.2f}",
                    row.gid,
                    row.name,
                    row.permalink_url,
                    row.completed,
                    row.completed_on.isoformat() if row.completed_on else "",
                    row.due_on.isoformat() if row.due_on else "",
                    row.estimated_time_yoko if row.estimated_time_yoko is not None else "",
                    (row.assignee_gid or ""),
                    (row.assignee_section_gid or ""),
                    ",".join(row.project_gids),
                    ",".join(row.project_names),
                    "; ".join(row.reasons),
                ])
        print(f"\nWrote CSV: {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

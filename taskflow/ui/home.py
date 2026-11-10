"""Home tab: a bento overview of the workspace, plus the task and new-task pop-ups.

Tiles are Streamlit's own bordered containers (so real buttons can sit inside
them) dressed with a little CSS; the read-only pieces inside are plain HTML.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st

from ..attachments import get_attachments
from ..comments import add_comment, get_comments
from ..config import MAX_COMMENT_LENGTH
from ..permissions import can_edit_task
from ..subtasks import get_subtasks, set_subtask_done, subtask_progress
from ..tasks import get_task, set_task_status
from ..utils import escape_html, is_overdue, try_parse_due_date
from .common import flash, report
from .forms import show_create_task_form, show_edit_task_form
from .widgets import due_label, md_escape, render_task_badges

PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}
NEXT_STATUS = {"Pending": "In Progress", "In Progress": "Completed", "Completed": "Pending"}
AVATAR_COLORS = (
    ("#CECBF6", "#3C3489"),
    ("#9FE1CB", "#085041"),
    ("#F5C4B3", "#712B13"),
    ("#F4C0D1", "#72243E"),
    ("#B5D4F4", "#0C447C"),
    ("#C0DD97", "#27500A"),
)
VIOLET, AMBER, RED = "#7f77dd", "#ef9f27", "#e24b4a"
LANE_LIMIT = 4

_CSS = """
.st-key-tf_ring, .st-key-tf_focus, .st-key-tf_team, .st-key-tf_week, .st-key-tf_glance,
.st-key-tf_lanes { border-radius: 16px !important; background: var(--tm-fill); }
.st-key-tf_focus { background: rgba(127, 119, 221, 0.10); border-color: rgba(127, 119, 221, 0.55) !important; }
.tf-label { font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase; color: var(--tm-muted); }
.tf-ring-wrap { display: flex; flex-direction: column; align-items: center; gap: 10px; padding-top: 6px; }
.tf-ring-box { position: relative; width: 140px; height: 140px; }
.tf-ring { position: absolute; inset: 0; border-radius: 50%;
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 15px), #000 calc(100% - 14px));
  mask: radial-gradient(farthest-side, transparent calc(100% - 15px), #000 calc(100% - 14px)); }
.tf-ring-text { position: absolute; inset: 0; display: grid; place-items: center; text-align: center; }
.tf-ring-text b { display: block; font-size: 1.7rem; line-height: 1.1; }
.tf-ring-text span { font-size: 0.75rem; color: var(--tm-muted); }
.tf-streak { font-size: 0.82rem; color: var(--tm-muted); }
.tf-focus-title { font-size: 1.3rem; font-weight: 700; margin: 0.4rem 0 0.15rem; line-height: 1.3; }
.tf-meta { color: var(--tm-muted); font-size: 0.84rem; }
.tf-pill { display: inline-block; font-size: 0.72rem; font-weight: 600; padding: 2px 10px; border-radius: 999px; }
.tf-bar { height: 7px; border-radius: 999px; background: var(--tm-line); overflow: hidden; margin: 12px 0 4px; }
.tf-bar span { display: block; height: 100%; border-radius: 999px; background: #7f77dd; }
.tf-avatars { display: flex; margin: 14px 0 10px; }
.tf-av { width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; font-size: 0.72rem;
  font-weight: 700; margin-left: -8px; border: 2px solid rgba(128, 128, 128, 0.35); }
.tf-av:first-child { margin-left: 0; }
.tf-week { display: flex; align-items: flex-end; gap: 6px; height: 64px; margin-top: 14px; }
.tf-week div { flex: 1; border-radius: 5px; min-height: 5px; }
.tf-days { display: flex; justify-content: space-between; font-size: 0.68rem; color: var(--tm-muted); margin-top: 5px; }
.tf-days span { flex: 1; text-align: center; }
.tf-glance { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 14px; }
.tf-glance b { display: block; font-size: 1.6rem; line-height: 1.2; }
.tf-glance span { font-size: 0.75rem; color: var(--tm-muted); }
.tf-lane-head { font-size: 0.78rem; font-weight: 600; margin-bottom: 6px; }
.st-key-tf_lane_overdue button, .st-key-tf_lane_today button, .st-key-tf_lane_upcoming button {
  justify-content: flex-start; text-align: left; border-radius: 0 !important; border-width: 0 0 0 3px !important;
  background: var(--tm-fill) !important; padding: 6px 12px !important; min-height: 0; }
.st-key-tf_lane_overdue button { border-left-color: #e24b4a !important; }
.st-key-tf_lane_today button { border-left-color: #ef9f27 !important; }
.st-key-tf_lane_upcoming button { border-left-color: #7f77dd !important; }
"""


def _open_tasks(tasks) -> list[dict]:
    return [t for t in tasks if t["status"] != "Completed" and not t.get("archived", 0)]


def _due(task) -> date | None:
    return try_parse_due_date(task.get("due_date"))


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def _first_name(name: str) -> str:
    parts = (name or "").split()
    return parts[0] if parts else "Someone"


# --- Header and pop-ups ------------------------------------------------------

@st.dialog("New task", width="large")
def _new_task_dialog(current_user) -> None:
    show_create_task_form(current_user)


def _toggle_subtask(subtask_id, task, current_user) -> None:
    """Checkbox callback; also syncs the Tasks tab's copy of the same checkbox."""
    done = st.session_state.get(f"dlg_sub_{subtask_id}", False)
    success, message = set_subtask_done(subtask_id, done, current_user, task)
    if success:
        st.session_state[f"subtask_done_{subtask_id}"] = done
    else:
        st.session_state[f"dlg_sub_{subtask_id}"] = not done
        flash(message, "error")


# The pop-up uses its own widget keys (dlg_*): it is first drawn in the same run
# as the Tasks tab, so reusing that tab's keys would clash.
@st.dialog("Task", width="large")
def _task_dialog(task_id, current_user) -> None:
    task = get_task(task_id)
    if not task:
        st.info("That task no longer exists.")
        return

    st.markdown(f"#### {md_escape(task['title'])}")
    render_task_badges(task)
    editable = can_edit_task(task, current_user)

    tab_names = ["Details", "Checklist", "Comments", "Files"] + (["Edit"] if editable else [])
    tabs = st.tabs(tab_names)
    with tabs[0]:
        st.write(task["description"] or "No description provided.")
        st.caption(
            f"Created by {task['creator_name']} · Assigned to {task['assignee_name']} · "
            f"{due_label(task)}"
        )
        if editable and not task.get("archived", 0):
            next_status = NEXT_STATUS.get(task["status"], "In Progress")
            if st.button(f"Mark {next_status.lower()}", key=f"dlg_status_{task['id']}", type="primary"):
                report(set_task_status(task["id"], current_user, next_status))
        elif not editable:
            st.caption("You have read-only access to this task.")

    with tabs[1]:
        subtasks = get_subtasks(task["id"])
        if subtasks:
            percent = subtask_progress(subtasks)
            st.progress(percent / 100, text=f"{percent}% of checklist complete")
            for subtask in subtasks:
                st.checkbox(
                    md_escape(subtask["title"]),
                    value=bool(subtask["done"]),
                    key=f"dlg_sub_{subtask['id']}",
                    disabled=not editable,
                    on_change=_toggle_subtask,
                    args=(subtask["id"], task, current_user),
                )
        else:
            st.caption("No checklist items yet. Add them from the Tasks tab.")

    with tabs[2]:
        for comment in get_comments(task["id"]):
            st.markdown(
                f"**{md_escape(comment['user_name'])}** :gray[{md_escape(comment['created_at'])}]"
            )
            st.write(comment["comment"])
        with st.form(f"dlg_comment_form_{task['id']}", clear_on_submit=True):
            text = st.text_area("Add a comment", max_chars=MAX_COMMENT_LENGTH)
            if st.form_submit_button("Post comment"):
                report(add_comment(task["id"], current_user["id"], text))

    with tabs[3]:
        attachments = get_attachments(task["id"])
        for attachment in attachments:
            st.markdown(f"- {md_escape(attachment['file_name'])}")
        st.caption(
            "Download or upload files from the Tasks tab." if attachments else "No files attached yet."
        )

    if editable:
        with tabs[4]:
            if st.session_state.get("editing_task_id") == task["id"]:
                st.caption("This task is already open for editing in the Tasks tab.")
            else:
                show_edit_task_form(task, current_user)


def render_header(current_user, tasks) -> None:
    """Date, greeting and the "New task" button above the tabs."""
    today = date.today()
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    name = _first_name(current_user.get("full_name") or current_user["username"])
    mine = [t for t in _open_tasks(tasks) if t["assignee_id"] == current_user["id"]]

    left, right = st.columns([3, 1], vertical_alignment="center")
    with left:
        st.markdown(
            f'<p class="tm-sub">{today:%A}, {today:%b} {today.day}</p>'
            f'<p class="tm-welcome">{greeting}, {escape_html(name)}</p>'
            f'<p class="tm-sub">{len(mine)} open task{"s" if len(mine) != 1 else ""} assigned to you</p>',
            unsafe_allow_html=True,
        )
    with right:
        if st.button("+ New task", type="primary", width="stretch", key="tf_new_task"):
            _new_task_dialog(current_user)


# --- Tiles -------------------------------------------------------------------

def _week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def _streak(tasks, current_user, today: date) -> int:
    """Consecutive days (ending today or yesterday) on which the user finished a task."""
    days = {
        str(t.get("updated_at") or "")[:10]
        for t in tasks
        if t["status"] == "Completed" and t["assignee_id"] == current_user["id"]
    }
    cursor = today if today.isoformat() in days else today - timedelta(days=1)
    streak = 0
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _ring_tile(tasks, current_user, today: date) -> None:
    start, end = _week_bounds(today)
    active = [t for t in tasks if not t.get("archived", 0)]
    this_week = [t for t in active if (d := _due(t)) and start <= d <= end]
    scope, label = (this_week, "This week") if this_week else (active, "All tasks")
    done = sum(t["status"] == "Completed" for t in scope)
    percent = round(done / len(scope) * 100) if scope else 0
    streak = _streak(tasks, current_user, today)
    streak_text = (
        f"{streak}-day streak" if streak else "Finish a task today to start a streak"
    )
    st.markdown(
        f'<div class="tf-label">{label}</div><div class="tf-ring-wrap">'
        f'<div class="tf-ring-box"><div class="tf-ring" style="background: conic-gradient({VIOLET} '
        f'{percent * 3.6}deg, var(--tm-line) 0deg);"></div><div class="tf-ring-text"><div>'
        f"<b>{percent}%</b><span>{done} of {len(scope)} done</span></div></div></div>"
        f'<div class="tf-streak">{escape_html(streak_text)}</div></div>',
        unsafe_allow_html=True,
    )


def _pick_focus(tasks, current_user) -> dict | None:
    open_tasks = _open_tasks(tasks)
    mine = [t for t in open_tasks if t["assignee_id"] == current_user["id"]]
    pool = mine or [t for t in open_tasks if can_edit_task(t, current_user)] or open_tasks
    if not pool:
        return None
    return min(
        pool,
        key=lambda t: (not is_overdue(t), t["due_date"], PRIORITY_RANK.get(t["priority"], 9)),
    )


def _focus_tile(tasks, current_user) -> None:
    task = _pick_focus(tasks, current_user)
    if task is None:
        st.markdown(
            '<div class="tf-label">Focus now</div>'
            '<div class="tf-focus-title">You’re all caught up</div>'
            '<div class="tf-meta">No open tasks match your filters. Create one to get going.</div>',
            unsafe_allow_html=True,
        )
        return

    if is_overdue(task):
        pill = f'<span class="tf-pill" style="background:rgba(226,75,74,.16);color:{RED}">'
    elif _due(task) == date.today():
        pill = f'<span class="tf-pill" style="background:rgba(239,159,39,.18);color:#c27c0e">'
    else:
        pill = f'<span class="tf-pill" style="background:rgba(127,119,221,.18);color:{VIOLET}">'
    progress = int(task.get("progress") or 0)
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span class="tf-label" style="color:{VIOLET}">Focus now</span>'
        f"{pill}{escape_html(due_label(task))}</span></div>"
        f'<div class="tf-focus-title">{escape_html(task["title"])}</div>'
        f'<div class="tf-meta">{escape_html(task["category"])} · {escape_html(task["priority"])} priority · '
        f'{escape_html(task["assignee_name"])}</div>'
        f'<div class="tf-bar"><span style="width:{progress}%"></span></div>'
        f'<div class="tf-meta">{progress}% done</div>',
        unsafe_allow_html=True,
    )
    done_col, open_col, _ = st.columns([1, 1, 2])
    with done_col:
        if can_edit_task(task, current_user) and st.button(
            "Mark done", key="tf_focus_done", width="stretch"
        ):
            report(set_task_status(task["id"], current_user, "Completed"))
    with open_col:
        if st.button("Open", key="tf_focus_open", width="stretch"):
            _task_dialog(task["id"], current_user)


def _team_tile(tasks, users) -> None:
    open_tasks = _open_tasks(tasks)
    load = sorted(
        ((sum(t["assignee_id"] == u["id"] for t in open_tasks), u) for u in users),
        key=lambda pair: -pair[0],
    )
    shown = [pair for pair in load if pair[0] > 0][:5]
    avatars = "".join(
        f'<div class="tf-av" title="{escape_html(u["full_name"])}: {count} open" '
        f'style="background:{AVATAR_COLORS[i % len(AVATAR_COLORS)][0]};'
        f'color:{AVATAR_COLORS[i % len(AVATAR_COLORS)][1]}">{escape_html(_initials(u["full_name"]))}</div>'
        for i, (count, u) in enumerate(shown)
    )
    if shown:
        count, busiest = shown[0]
        note = f"{_first_name(busiest['full_name'])} has the most open work ({count})"
    else:
        note = "Nobody has open work right now"
    st.markdown(
        f'<div class="tf-label">Team load</div><div class="tf-avatars">{avatars}</div>'
        f'<div class="tf-meta">{escape_html(note)}</div>',
        unsafe_allow_html=True,
    )


def _week_tile(tasks, today: date) -> None:
    start, _ = _week_bounds(today)
    open_tasks = _open_tasks(tasks)
    days = [start + timedelta(days=i) for i in range(7)]
    counts = [sum(_due(t) == d for t in open_tasks) for d in days]
    peak = max(counts) or 1
    bars = ""
    for day, count in zip(days, counts):
        color = "var(--tm-line)" if count == 0 else RED if day < today else AMBER if day == today else VIOLET
        bars += f'<div title="{count} due" style="height:{max(8, round(count / peak * 100))}%;background:{color}"></div>'
    labels = "".join(
        f'<span style="{"font-weight:700;color:inherit" if d == today else ""}">{d:%a}</span>' for d in days
    )
    st.markdown(
        f'<div class="tf-label">Due this week</div><div class="tf-week">{bars}</div>'
        f'<div class="tf-days">{labels}</div>',
        unsafe_allow_html=True,
    )


def _glance_tile(tasks) -> None:
    active = [t for t in tasks if not t.get("archived", 0)]
    open_count = len(_open_tasks(active))
    overdue = sum(is_overdue(t) for t in active)
    done = sum(t["status"] == "Completed" for t in active)
    st.markdown(
        '<div class="tf-label">At a glance</div><div class="tf-glance">'
        f"<div><b>{open_count}</b><span>Open</span></div>"
        f'<div><b style="color:{RED}">{overdue}</b><span>Overdue</span></div>'
        f'<div><b style="color:#22c55e">{done}</b><span>Done</span></div></div>',
        unsafe_allow_html=True,
    )


def _lane(key, title, color, lane_tasks, current_user) -> None:
    with st.container(key=key):
        st.markdown(
            f'<div class="tf-lane-head" style="color:{color}">{escape_html(title)} · {len(lane_tasks)}</div>',
            unsafe_allow_html=True,
        )
        if not lane_tasks:
            st.caption("Nothing here.")
        for task in lane_tasks[:LANE_LIMIT]:
            label = f"{md_escape(task['title'])} · {md_escape(_first_name(task['assignee_name']))}"
            if st.button(label, key=f"{key}_{task['id']}", width="stretch"):
                _task_dialog(task["id"], current_user)
        if len(lane_tasks) > LANE_LIMIT:
            st.caption(f"+{len(lane_tasks) - LANE_LIMIT} more in the Tasks tab")


def _lanes_tile(tasks, current_user, today: date) -> None:
    open_tasks = sorted(_open_tasks(tasks), key=lambda t: (t["due_date"], PRIORITY_RANK.get(t["priority"], 9)))
    overdue = [t for t in open_tasks if is_overdue(t)]
    due_today = [t for t in open_tasks if _due(t) == today]
    upcoming = [t for t in open_tasks if (d := _due(t)) and today < d <= today + timedelta(days=7)]
    columns = st.columns(3, gap="medium")
    with columns[0]:
        _lane("tf_lane_overdue", "Overdue", RED, overdue, current_user)
    with columns[1]:
        _lane("tf_lane_today", "Today", "#c27c0e", due_today, current_user)
    with columns[2]:
        _lane("tf_lane_upcoming", "Next 7 days", VIOLET, upcoming, current_user)


def show_home_tab(current_user, tasks, users) -> None:
    """The bento overview, built from the tasks that match the sidebar filters."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
    today = date.today()

    left, right = st.columns([1, 2], gap="small")
    with left:
        with st.container(border=True, height=270, key="tf_ring"):
            _ring_tile(tasks, current_user, today)
    with right:
        with st.container(border=True, height=270, key="tf_focus"):
            _focus_tile(tasks, current_user)

    team, week, glance = st.columns(3, gap="small")
    with team:
        with st.container(border=True, height=170, key="tf_team"):
            _team_tile(tasks, users)
    with week:
        with st.container(border=True, height=170, key="tf_week"):
            _week_tile(tasks, today)
    with glance:
        with st.container(border=True, height=170, key="tf_glance"):
            _glance_tile(tasks)

    with st.container(border=True, key="tf_lanes"):
        _lanes_tile(tasks, current_user, today)

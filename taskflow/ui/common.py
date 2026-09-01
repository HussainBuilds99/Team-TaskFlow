"""Shared Streamlit widgets and helpers."""

from __future__ import annotations

import streamlit as st

from ..utils import escape_html

FLASH_KEY = "_flash_messages"


def flash(message: str, kind: str = "success") -> None:
    """Queue a message to show after the next rerun.

    ``st.success(...)`` immediately followed by ``st.rerun()`` never reaches the
    browser, which is why every mutating action queues its feedback instead.
    """
    st.session_state.setdefault(FLASH_KEY, []).append((kind, message))


def render_flashes() -> None:
    """Render and clear any queued messages."""
    renderers = {
        "success": st.success,
        "error": st.error,
        "info": st.info,
        "warning": st.warning,
    }
    for kind, message in st.session_state.pop(FLASH_KEY, []):
        renderers.get(kind, st.info)(message)


def report(result, rerun_on_success: bool = True) -> bool:
    """Handle a ``(success, message)`` pair from the data layer.

    Success queues the message and reruns so the page reflects the change;
    failure is shown straight away because nothing reruns.
    """
    success, message = result
    if success:
        flash(message, "success")
        if rerun_on_success:
            st.rerun()
    else:
        st.error(message)
    return success


def chip(label: str, css_class: str = "") -> str:
    """Build one HTML chip with the label escaped."""
    classes = f"tm-chip {css_class}".strip()
    return f'<span class="{classes}">{escape_html(label)}</span>'


def status_chip_class(status: str) -> str:
    return {
        "Pending": "tm-pending",
        "In Progress": "tm-progress",
        "Completed": "tm-completed",
    }.get(status, "tm-pending")


def priority_chip_class(priority: str) -> str:
    return {"High": "tm-high", "Medium": "tm-medium", "Low": "tm-low"}.get(priority, "tm-low")


def render_task_chips(task) -> None:
    """Status/priority/category/progress chips for a task."""
    chips = [
        chip(task["priority"], priority_chip_class(task["priority"])),
        chip(task["status"], status_chip_class(task["status"])),
        chip(task["category"]),
        chip(f"Progress: {int(task.get('progress') or 0)}%"),
    ]
    if task.get("recurrence", "None") != "None":
        chips.append(chip(f"Repeats {task['recurrence']}"))
    if task.get("archived", 0):
        chips.append(chip("Archived", "tm-archived"))
    st.markdown(f"<div>{''.join(chips)}</div>", unsafe_allow_html=True)

    tags = task.get("tags")
    if tags:
        st.caption(f"Tags: {tags}")


def render_kpis(summary) -> None:
    """The coloured counter strip at the top of the dashboard."""
    cards = [
        ("Total", summary["total"], "tm-kpi-accent"),
        ("Completed", summary["completed"], "tm-kpi-success"),
        ("Pending", summary["pending"], "tm-kpi-info"),
        ("In Progress", summary["in_progress"], "tm-kpi-warn"),
        ("Overdue", summary["overdue"], "tm-kpi-danger"),
        ("Due Today", summary["due_today"], "tm-kpi-accent"),
    ]
    html = "".join(
        f'<div class="tm-kpi {css_class}"><div class="label">{escape_html(label)}</div>'
        f'<div class="value">{escape_html(value)}</div></div>'
        for label, value, css_class in cards
    )
    st.markdown(f'<div class="tm-kpi-wrap">{html}</div>', unsafe_allow_html=True)


def dataframe(rows, **kwargs) -> None:
    """``st.dataframe`` with the settings this app always wants."""
    st.dataframe(rows, width="stretch", hide_index=True, **kwargs)


def confirm_button(label: str, key: str, help_text: str | None = None) -> bool:
    """Two-step confirmation for destructive actions.

    The first click arms the button, the second performs the action, so a stray
    click can never delete a task outright.
    """
    armed_key = f"_armed_{key}"
    if st.session_state.get(armed_key):
        columns = st.columns(2)
        with columns[0]:
            confirmed = st.button(
                "Confirm", key=f"{key}_confirm", width="stretch", type="primary"
            )
        with columns[1]:
            if st.button("Cancel", key=f"{key}_cancel", width="stretch"):
                st.session_state[armed_key] = False
                st.rerun()
        if confirmed:
            st.session_state[armed_key] = False
            return True
        return False

    if st.button(label, key=key, width="stretch", help=help_text):
        st.session_state[armed_key] = True
        st.rerun()
    return False

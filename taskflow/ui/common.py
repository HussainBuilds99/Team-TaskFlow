"""Shared Streamlit widgets and helpers."""

from __future__ import annotations

import streamlit as st

FLASH_KEY = "_flash_messages"


def flash(message: str, kind: str = "success") -> None:
    """Queue a message to show after the next rerun.

    ``st.success(...)`` immediately followed by ``st.rerun()`` never reaches the
    browser, which is why every mutating action queues its feedback instead.
    """
    st.session_state.setdefault(FLASH_KEY, []).append((kind, message))
    st.cache_data.clear()  # every change is followed by a flash, so reload fresh data


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

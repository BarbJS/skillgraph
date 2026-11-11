"""Streamlit-cached factories for process-wide read-only resources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st


def resource_signature(
    path: str | Path, *, version: str = ""
) -> tuple[Any, ...]:
    """Return a cache key that changes with resource version or file metadata."""
    target = Path(path)
    prefix = (version,)
    if target.is_dir():
        entries = []
        try:
            items = sorted(target.iterdir())
        except OSError:
            items = []
        for item in items:
            if item.is_file():
                try:
                    stat = item.stat()
                except OSError:
                    continue
                entries.append((item.name, stat.st_mtime_ns, stat.st_size))
        return prefix + (str(target.resolve()), tuple(entries))
    try:
        stat = target.stat()
    except OSError:
        return prefix + (str(target.resolve()), None)
    return prefix + (str(target.resolve()), stat.st_mtime_ns, stat.st_size)


@st.cache_resource(show_spinner=False)
def cached_database(data_dir: str, signature: tuple[Any, ...]):
    """Create the read-only in-memory DuckDB once per process and data version."""
    from src.sql_tools import SkillGraphDatabase

    return SkillGraphDatabase(data_dir)


@st.cache_resource(show_spinner=False)
def cached_session_store(path: str):
    """Reuse the SQLite store object while each operation opens its own connection."""
    from src.session_store import SessionStore

    return SessionStore(path)


@st.cache_resource(show_spinner=False)
def cached_feedback_store(path: str):
    """Reuse the SQLite feedback store object across Streamlit reruns."""
    from src.feedback import FeedbackStore

    return FeedbackStore(path)


@st.cache_resource(show_spinner=False)
def cached_ml_artifact(path: str, signature: tuple[Any, ...]):
    """Load the validated ML artifact once per process and file version."""
    from src.ml_inference import load_artifact

    return load_artifact(Path(path))

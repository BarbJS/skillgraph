"""User-facing progress helpers for long-running resume analysis."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import streamlit as st


@dataclass
class ResumeProgress:
    status: Any
    started: float

    @classmethod
    def start(cls) -> "ResumeProgress":
        progress = cls(
            st.status("Preparando análise de currículo...", expanded=True),
            perf_counter(),
        )
        progress.update(
            "upload",
            "Currículo recebido",
            "O PDF foi recebido e está pronto para análise.",
        )
        return progress

    def update(self, stage: str, label: str, detail: str) -> None:
        elapsed = perf_counter() - self.started
        self.status.update(label=f"{label} · {elapsed:.1f}s", state="running")
        self.status.write(f"**{label}** — {detail}")

    def finish(self, success: bool, detail: str = "") -> None:
        elapsed = perf_counter() - self.started
        label = (
            f"Análise concluída · {elapsed:.1f}s"
            if success
            else f"Análise interrompida · {elapsed:.1f}s"
        )
        self.status.update(
            label=label, state="complete" if success else "error", expanded=not success
        )
        if detail:
            self.status.write(detail)

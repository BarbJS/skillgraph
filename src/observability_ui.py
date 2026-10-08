"""Small renderer for the developer-only observability area."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.observability import OBSERVABILITY


def render_observability() -> None:
    st.header("Observabilidade e métricas")
    st.caption("Painel técnico local com traces sanitizados e métricas agregadas.")
    snapshot = OBSERVABILITY.snapshot()
    cols = st.columns(4)
    cols[0].metric("Traces", snapshot["traces"])
    cols[1].metric("P95 (ms)", snapshot["latency_p95_ms"])
    cols[2].metric("Erros", f"{snapshot['error_rate']:.2%}")
    cols[3].metric("Timeouts", f"{snapshot['timeout_rate']:.2%}")
    st.subheader("Consumo")
    st.json(
        {
            "input_tokens": snapshot["input_tokens"],
            "output_tokens": snapshot["output_tokens"],
            "cost": snapshot["cost"],
        }
    )
    tabs = st.tabs(["Traces", "Serviços", "Agentes/Tarefas", "Erros"])
    with tabs[1]:
        st.dataframe(
            pd.DataFrame(OBSERVABILITY.service_metrics()),
            hide_index=True,
            use_container_width=True,
        )
    with tabs[2]:
        st.dataframe(
            pd.DataFrame(OBSERVABILITY.task_metrics()),
            hide_index=True,
            use_container_width=True,
        )
    with tabs[3]:
        st.dataframe(
            pd.DataFrame(OBSERVABILITY.recent_errors()),
            hide_index=True,
            use_container_width=True,
        )
    with tabs[0]:
        st.subheader("Traces recentes")
    traces = snapshot.get("recent_traces", [])
    if traces:
        st.dataframe(pd.DataFrame(traces), hide_index=True, use_container_width=True)
    else:
        st.info("Nenhum trace registrado nesta sessão.")

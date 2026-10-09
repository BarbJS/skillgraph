"""Developer-only observability dashboard."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.observability import OBSERVABILITY


def render_observability() -> None:
    st.header("Observabilidade e métricas")
    st.caption("Painel técnico local com traces sanitizados e métricas agregadas.")
    if st.button("Atualizar traces", key="refresh-observability"):
        st.rerun()

    snapshot = OBSERVABILITY.snapshot()
    cols = st.columns(4)
    cols[0].metric("Traces", snapshot["traces"])
    cols[1].metric("P95 (ms)", snapshot["latency_p95_ms"])
    cols[2].metric("Erros", f"{snapshot['error_rate']:.2%}")
    cols[3].metric("Timeouts", f"{snapshot['timeout_rate']:.2%}")

    recent = OBSERVABILITY.recent_trace_rows(limit=10)
    st.subheader("10 traces mais recentes")
    if recent:
        st.dataframe(pd.DataFrame(recent), hide_index=True, use_container_width=True)
        trace_ids = [row["Trace ID"] for row in recent]
        selected_id = st.selectbox("Trace ID para rastrear", trace_ids, key="observability-trace-id")
        selected = OBSERVABILITY.get_trace(selected_id)
        if selected:
            with st.expander("Detalhes do trace selecionado", expanded=True):
                st.json(selected)
    else:
        st.info("Nenhum trace registrado nesta sessão.")

    st.subheader("Consumo")
    st.json({"input_tokens": snapshot["input_tokens"], "output_tokens": snapshot["output_tokens"], "cost": snapshot["cost"]})
    tabs = st.tabs(["Serviços", "Agentes/Tarefas", "Erros"])
    with tabs[0]:
        st.dataframe(pd.DataFrame(OBSERVABILITY.service_metrics()), hide_index=True, use_container_width=True)
    with tabs[1]:
        st.dataframe(pd.DataFrame(OBSERVABILITY.task_metrics()), hide_index=True, use_container_width=True)
    with tabs[2]:
        st.dataframe(pd.DataFrame(OBSERVABILITY.recent_errors()), hide_index=True, use_container_width=True)

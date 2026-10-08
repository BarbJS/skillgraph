"""Developer-only AI quality/evaluation dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.evaluation_ai import load_golden_cases


def render_quality() -> None:
    st.header("Qualidade e Evals")
    st.caption(
        "Avaliação técnica da qualidade do SkillGraph; execução live é explícita e pode consumir tokens."
    )
    report_path = Path("output/evaluation/ai_quality_report.json")
    live_path = Path("output/evaluation/live_ai_report.json")
    col1, col2, col3 = st.columns(3)
    cases = load_golden_cases(Path("evals/golden_dataset.jsonl"))
    col1.metric("Casos Golden", len(cases))
    col2.metric("Categorias", len({item.get("category") for item in cases}))
    col3.metric("DeepEval obrigatório", "4 métricas")
    st.subheader("Golden Dataset")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "id": item.get("id"),
                    "category": item.get("category"),
                    "route": item.get("expected_route"),
                    "must_block": item.get("must_block"),
                }
                for item in cases
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    if report_path.exists():
        st.subheader("Última avaliação offline")
        st.json(json.loads(report_path.read_text(encoding="utf-8")))
    else:
        st.info("Nenhum relatório offline encontrado. Execute `make evaluate-ai`.")
    if live_path.exists():
        st.subheader("Última avaliação live")
        st.json(json.loads(live_path.read_text(encoding="utf-8")))
    else:
        st.info(
            "Nenhum relatório live encontrado. Execute o runner live explicitamente quando desejar usar o judge."
        )
    st.caption(
        "Faithfulness, Answer Relevancy, Context Precision e Context Recall são avaliadas pelo runner live DeepEval; DeepEval fornece métricas complementares."
    )

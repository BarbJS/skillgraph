"""Developer-only AI quality/evaluation dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.evaluation_ai import load_golden_cases
from src.evaluation_runner import run_deterministic_evaluation, run_live_evaluation


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _metric_label(name: str) -> str:
    return {
        "faithfulness": "Faithfulness",
        "answer_relevancy": "Answer Relevancy",
        "contextual_precision": "Contextual Precision",
        "contextual_recall": "Contextual Recall",
    }.get(name, name.replace("_", " ").title())


def _deterministic_rows(cases: list[dict[str, Any]], report: dict[str, Any] | None) -> list[dict[str, Any]]:
    by_id = {str(item.get("id")): item for item in (report or {}).get("results", [])}
    rows = []
    for case in cases:
        result = by_id.get(str(case.get("id")), {})
        rows.append(
            {
                "ID": case.get("id", ""),
                "Categoria": case.get("category", ""),
                "Pergunta/caso": case.get("question", ""),
                "Rota esperada": case.get("expected_route", ""),
                "Deve bloquear?": "Sim" if case.get("must_block") else "Não",
                "Resultado offline": (
                    "Aprovado" if result.get("passed") else "Falhou"
                )
                if result
                else "Não executado",
            }
        )
    return rows


def _deterministic_report_for_display(report: dict[str, Any]) -> dict[str, Any]:
    """Show only Golden Dataset execution data, never RAG/DeepEval metadata."""

    allowed = {"mode", "run_at", "total", "passed", "passed_schema", "results"}
    display = {key: report[key] for key in allowed if key in report}
    results = display.get("results")
    if isinstance(results, list):
        display["results"] = [
            {
                key: value
                for key, value in item.items()
                if key
                not in {
                    "ragas_metrics",
                    "deepeval_metrics",
                    "deep_eval_metrics",
                    "metrics",
                }
            }
            if isinstance(item, dict)
            else item
            for item in results
        ]
    return display


def _live_metric_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, values in summary.get("metrics", {}).items():
        rows.append(
            {
                "Métrica": _metric_label(key),
                "Casos": values.get("count", 0),
                "Média geral": values.get("mean"),
                "Mediana": values.get("median"),
                "Mínimo": values.get("minimum"),
                "Máximo": values.get("maximum"),
                "Taxa de aprovação": values.get("pass_rate"),
            }
        )
    return rows


def _live_case_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for case in report.get("case_results", []):
        item = {
            "ID": case.get("case_id", ""),
            "Categoria": case.get("category", ""),
            "Aprovado": "Sim" if case.get("passed") else "Não",
            "Média do caso": case.get("score_mean"),
        }
        for metric in ("faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall"):
            item[_metric_label(metric)] = case.get("metrics", {}).get(metric, {}).get("score")
        rows.append(item)
    return rows


def _render_live_case_detail(report: dict[str, Any]) -> None:
    cases = report.get("case_results", [])
    if not cases:
        return
    by_id = {str(item.get("case_id")): item for item in cases}
    selected = st.selectbox("Detalhar caso live", list(by_id), key="quality-live-case")
    case = by_id[selected]
    st.markdown(f"**Caso:** `{selected}` · **Categoria:** {case.get('category', '—')}")
    st.metric("Média do caso", case.get("score_mean", "—"))
    for name, metric in case.get("metrics", {}).items():
        with st.expander(_metric_label(name), expanded=False):
            st.write(
                {
                    "score": metric.get("score"),
                    "threshold": metric.get("threshold"),
                    "success": metric.get("success"),
                    "evaluation_model": metric.get("evaluation_model"),
                    "cost": metric.get("cost"),
                    "reason": metric.get("reason", ""),
                }
            )


def render_quality() -> None:
    st.header("Qualidade e Evals")
    st.caption(
        "O Golden Dataset valida contratos offline; o DeepEval live julga semanticamente somente casos com resposta, contexto e ground truth."
    )
    report_path = ROOT / "output/evaluation/ai_quality_report.json"
    live_path = ROOT / "output/evaluation/live_ai_report.json"
    cases = load_golden_cases(ROOT / "evals/golden_dataset.jsonl")
    deterministic = _load_json(report_path)
    live = _load_json(live_path)

    st.subheader("Executar nova rodada")
    st.caption(
        "A rodada executa primeiro os 20 casos determinísticos e depois os 12 casos RAG com DeepEval. O segundo passo consome chamadas do modelo judge."
    )
    confirm = st.checkbox(
        "Confirmo o uso do modelo judge para avaliar os casos RAG",
        key="quality-confirm-live",
    )
    if st.button("Executar Golden Dataset + casos RAG", disabled=not confirm, key="quality-run-all"):
        progress_bar = st.progress(0.0)
        status = st.empty()
        deterministic = run_deterministic_evaluation(
            dataset_path=ROOT / "evals/golden_dataset.jsonl",
            output_path=report_path,
        )
        status.info("Golden Dataset concluído. Iniciando casos RAG...")

        def update_progress(case_id: str, index: int, total: int) -> None:
            progress_bar.progress(index / max(total, 1))
            status.info(f"Avaliando RAG {index}/{total}: {case_id}")

        live = run_live_evaluation(
            dataset_path=ROOT / "evals/rag_goldens.jsonl",
            output_path=live_path,
            progress=update_progress,
        )
        progress_bar.progress(1.0)
        status.success("Golden Dataset e casos RAG concluídos.")
        st.rerun()

    col1, col2, col3 = st.columns(3)
    col1.metric("Casos Golden Dataset", len(cases))
    col2.metric("Casos RAG", (live or {}).get("evaluated_cases", 0))
    col3.metric("Pass rate RAG", f"{float((live or {}).get('summary', {}).get('pass_rate', 0)):.1%}")

    st.subheader("Golden Dataset — validação determinística")
    st.info(
        "`Deve bloquear?` corresponde ao campo técnico `must_block`: **Sim** significa que os guardrails devem bloquear o caso; **Não** significa que o caso deve seguir normalmente. Esta etapa compara schema, rota e bloqueio; ela não executa o LLM nem produz uma resposta semântica."
    )
    st.dataframe(
        pd.DataFrame(_deterministic_rows(cases, deterministic)),
        hide_index=True,
        use_container_width=True,
    )
    if deterministic:
        with st.expander("Detalhes da validação determinística", expanded=False):
            st.json(_deterministic_report_for_display(deterministic))
    else:
        st.warning("Nenhum relatório determinístico encontrado. Execute `make evaluate-ai`.")

    st.subheader("Casos RAG — métricas semânticas")
    if not live:
        st.info(
            "Nenhum relatório live encontrado. Execute a avaliação explicitamente com `scripts/evaluate-ai-live.py --deepeval --yes-live`."
        )
        return

    summary = live.get("summary", {})
    top = st.columns(4)
    top[0].metric("Casos avaliados", summary.get("cases", live.get("evaluated_cases", 0)))
    top[1].metric("Casos aprovados", summary.get("passed_cases", 0))
    top[2].metric("Pass rate geral", f"{float(summary.get('pass_rate', 0)):.1%}")
    top[3].metric("Modelo judge", live.get("judge_model", "—"))
    st.caption(
        "Estas métricas são médias gerais dos casos RAG selecionados para DeepEval live (12 no relatório atual), não dos 25 casos determinísticos do Golden Dataset."
    )

    metric_rows = _live_metric_rows(summary)
    if metric_rows:
        st.dataframe(pd.DataFrame(metric_rows), hide_index=True, use_container_width=True)

    st.markdown("**Resultado por caso live**")
    case_rows = _live_case_rows(live)
    if case_rows:
        st.dataframe(pd.DataFrame(case_rows), hide_index=True, use_container_width=True)
        _render_live_case_detail(live)
    else:
        st.info("O relatório live não contém resultados estruturados por caso.")

    weaknesses = summary.get("weaknesses", [])
    if weaknesses:
        with st.expander("Pontos de atenção", expanded=False):
            st.dataframe(pd.DataFrame(weaknesses), hide_index=True, use_container_width=True)
    if summary.get("recommendations"):
        st.markdown("**Recomendações**")
        for recommendation in summary["recommendations"]:
            st.markdown(f"- {recommendation}")

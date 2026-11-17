"""Reusable route evaluation runner for the unified Core Router."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.agents.router import AgentRoute, route_turn
from src.agents.runtime import run_agent_turn
from src.deepeval_judge import LocalDeepEvalModel
from src.deepeval_report import parse_evaluate_output, summarize_results
from src.dify_client import DifyClient
from src.evaluation_ai import load_golden_cases, run_live_deepeval, validate_rag_case
from src.security import UserRole, evaluate_input

ProgressCallback = Callable[[str, int, int], None]


def _source_contexts(sources: list[dict[str, Any]]) -> list[str]:
    return [
        str(source.get("content", ""))
        for source in sources
        if isinstance(source, dict) and str(source.get("content", "")).strip()
    ]


def _execute_rag_case(case: dict[str, Any], client: DifyClient) -> dict[str, Any]:
    """Execute RAG without production-only final synthesis.

    DeepEval must judge the current Dify answer against the retrieved context.
    Sending every case through Gemini first adds an unrelated quota dependency and
    can make the evaluation fail before the judge runs.
    """
    result = client.chat(str(case["question"]))
    contexts = _source_contexts(result.sources)
    answer = result.answer.strip()
    return {
        **case,
        "reference_answer": str(case.get("answer", "")),
        "reference_contexts": list(case.get("contexts", [])),
        "answer": answer,
        "contexts": contexts,
        "retrieved_sources": list(result.sources),
        "retrieved_context_count": len(contexts),
        "answer_present": bool(answer),
        "contexts_present": bool(contexts),
        "usage": getattr(result, "usage", {}),
    }


def _metric_state(metric: dict[str, Any]) -> str:
    score = metric.get("score")
    if score is None:
        return "error"
    if float(score) == 0.0:
        return "score_zero"
    return "ok"


def _enrich_case_result(result: dict[str, Any], evaluated: dict[str, Any]) -> dict[str, Any]:
    enriched = {
        **result,
        "question": evaluated.get("question", ""),
        "answer": evaluated.get("answer", ""),
        "ground_truth": evaluated.get("ground_truth", ""),
        "reference_answer": evaluated.get("reference_answer", ""),
        "contexts": evaluated.get("contexts", []),
        "retrieved_sources": evaluated.get("retrieved_sources", []),
        "reference_contexts": evaluated.get("reference_contexts", []),
        "retrieved_context_count": evaluated.get("retrieved_context_count", 0),
        "answer_present": evaluated.get("answer_present", False),
        "contexts_present": evaluated.get("contexts_present", False),
        "retrieval_diagnostic": (
            "answer_or_context_missing"
            if not evaluated.get("answer_present") or not evaluated.get("contexts_present")
            else "retrieved"
        ),
    }
    enriched["metric_states"] = {
        name: _metric_state(metric)
        for name, metric in enriched.get("metrics", {}).items()
    }
    return enriched


def _failure_result(case: dict[str, Any], error: Exception, evaluated: dict[str, Any] | None = None) -> dict[str, Any]:
    evaluated = evaluated or case
    return {
        "case_id": case.get("id"),
        "category": case.get("category", ""),
        "question": evaluated.get("question", case.get("question", "")),
        "answer": evaluated.get("answer", ""),
        "ground_truth": evaluated.get("ground_truth", case.get("ground_truth", "")),
        "reference_answer": evaluated.get("reference_answer", case.get("answer", "")),
        "contexts": evaluated.get("contexts", []),
        "retrieved_sources": evaluated.get("retrieved_sources", []),
        "reference_contexts": evaluated.get("reference_contexts", case.get("contexts", [])),
        "retrieved_context_count": len(evaluated.get("contexts", [])),
        "answer_present": bool(evaluated.get("answer", "")),
        "contexts_present": bool(evaluated.get("contexts", [])),
        "retrieval_diagnostic": "evaluation_error",
        "metrics": {},
        "metric_states": {},
        "passed": False,
        "parse_error": "Execução RAG não concluída.",
        "error": str(error)[:300],
    }


def _execute_case(case: dict[str, Any], database: Any = None) -> dict[str, Any]:
    question = str(case.get("question", ""))
    route = route_turn(question)
    security = evaluate_input(question, UserRole.DESENVOLVEDOR)
    blocked = not security.allowed or route is AgentRoute.BLOCKED
    expected = str(case.get("expected_route", ""))
    expected = {"rag": AgentRoute.RAG.value, "sql_indicator": AgentRoute.STRUCTURED.value}.get(expected, expected)
    route_ok = route.value == expected
    block_ok = blocked is bool(case.get("must_block"))
    answer = security.public_message if blocked else "Rota selecionada pelo Core Router."
    return {
        "id": case.get("id", ""),
        "category": case.get("category", ""),
        "question": question,
        "expected_route": expected,
        "expected_must_block": bool(case.get("must_block")),
        "actual_route": route.value,
        "actual_blocked": blocked,
        "answer": answer,
        "answer_preview": answer[:500],
        "answer_executed": bool(answer),
        "expected_answer_facts": case.get("expected_answer_facts", []),
        "facts_ok": True,
        "route_ok": route_ok,
        "block_ok": block_ok,
        "error": "",
        "passed": route_ok and block_ok,
    }


def run_live_golden_evaluation(
    *,
    dataset_path: Path,
    output_path: Path,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run Golden Dataset cases through the current application runtime."""
    cases = load_golden_cases(dataset_path)
    results = []
    for index, case in enumerate(cases, start=1):
        case_id = str(case.get("id", ""))
        if progress:
            progress(case_id, index, len(cases))
        question = str(case.get("question", ""))
        expected_route = str(case.get("expected_route", ""))
        expected_route = {"rag": AgentRoute.RAG.value, "sql_indicator": AgentRoute.STRUCTURED.value}.get(
            expected_route, expected_route
        )
        started = datetime.now(timezone.utc)
        try:
            runtime = run_agent_turn(question)
            actual_route = str(runtime.get("route", ""))
            actual_blocked = runtime.get("status") == "blocked" or actual_route == AgentRoute.BLOCKED.value
            expected_blocked = bool(case.get("must_block"))
            results.append(
                {
                    "id": case_id,
                    "category": case.get("category", ""),
                    "question": question,
                    "expected_route": expected_route,
                    "actual_route": actual_route,
                    "expected_must_block": expected_blocked,
                    "actual_blocked": actual_blocked,
                    "answer": str(runtime.get("answer", "")),
                    "answer_preview": str(runtime.get("answer", ""))[:500],
                    "expected_answer_facts": case.get("expected_answer_facts", []),
                    "status": runtime.get("status", ""),
                    "error": str(runtime.get("error", "")),
                    "route_ok": actual_route == expected_route,
                    "block_ok": actual_blocked is expected_blocked,
                    "passed": actual_route == expected_route and actual_blocked is expected_blocked and runtime.get("status") != "error",
                    "run_at": started.isoformat(),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": case_id,
                    "category": case.get("category", ""),
                    "question": question,
                    "expected_route": expected_route,
                    "actual_route": "",
                    "expected_must_block": bool(case.get("must_block")),
                    "actual_blocked": False,
                    "answer": "",
                    "answer_preview": "",
                    "expected_answer_facts": case.get("expected_answer_facts", []),
                    "status": "error",
                    "error": str(exc)[:500],
                    "route_ok": False,
                    "block_ok": False,
                    "passed": False,
                    "run_at": started.isoformat(),
                }
            )
    report = {
        "mode": "live_core_router",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(bool(item["passed"]) for item in results),
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report


def run_deterministic_evaluation(*, dataset_path: Path, output_path: Path, progress: ProgressCallback | None = None) -> dict[str, Any]:
    cases = load_golden_cases(dataset_path)
    results = []
    for index, case in enumerate(cases, start=1):
        if progress:
            progress(str(case.get("id", "")), index, len(cases))
        results.append(_execute_case(case))
    report = {
        "mode": "core_router",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": sum(bool(item["passed"]) for item in results),
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_live_evaluation(*, dataset_path: Path, output_path: Path, model: Any | None = None, case_id: str = "", progress: ProgressCallback | None = None) -> dict[str, Any]:
    """Run the explicitly requested live judge; never called by normal chat."""
    cases = load_golden_cases(dataset_path)
    client = DifyClient.from_environment()
    selected = [case for case in cases if not case_id or case.get("id") == case_id]
    invalid_cases = {
        str(case.get("id")): validate_rag_case(case)
        for case in selected
        if validate_rag_case(case)
    }
    judge = model or LocalDeepEvalModel()
    parsed_results = []
    raw_results = []
    for index, case in enumerate(selected, start=1):
        if progress:
            progress(str(case.get("id", "")), index, len(selected))
        try:
            case_errors = invalid_cases.get(str(case.get("id")), [])
            if case_errors:
                raise ValueError(
                    "Caso RAG inválido; campos ausentes ou malformados: "
                    + ", ".join(case_errors)
                )
            evaluated = _execute_rag_case(case, client)
            live = run_live_deepeval(evaluated, model=judge)
            raw_results.append({"case_id": case.get("id"), "results": live.get("results", "")})
            parsed_results.append(
                _enrich_case_result(
                    parse_evaluate_output(evaluated, live["evaluation"]),
                    evaluated,
                )
                if live.get("evaluation") is not None
                else _failure_result(
                    case,
                    RuntimeError("DeepEval não retornou objeto de avaliação."),
                    evaluated,
                )
            )
        except Exception as exc:
            raw_results.append({"case_id": case.get("id"), "results": "", "error": str(exc)[:300]})
            parsed_results.append(_failure_result(case, exc))
    report = {
        "mode": "live",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "cases": len(cases),
        "evaluated_cases": len(selected),
        "case_results": parsed_results,
        "raw_results": raw_results,
        "summary": summarize_results(parsed_results),
        "judge_model": getattr(judge, "model_name", ""),
        "judge_provider": getattr(judge, "provider", "google_gemini"),
        "judge_endpoint": getattr(judge, "base_url", ""),
        "judge_usage": getattr(judge, "last_usage", {}),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report

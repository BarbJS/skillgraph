"""Reusable route evaluation runner for the unified Core Router."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.agents.router import AgentRoute, route_turn
from src.deepeval_judge import LocalDeepEvalModel
from src.deepeval_embeddings import GeminiEvaluationEmbeddings
from src.deepeval_report import parse_evaluate_output, summarize_results
from src.dify_client import DifyClient
from src.evaluation_ai import load_golden_cases, run_live_deepeval
from src.response_synthesis import synthesize_response
from src.security import UserRole, evaluate_input

ProgressCallback = Callable[[str, int, int], None]


def _source_contexts(sources: list[dict[str, Any]]) -> list[str]:
    return [
        str(source.get("content", ""))
        for source in sources
        if isinstance(source, dict) and str(source.get("content", "")).strip()
    ]


def _execute_rag_case(case: dict[str, Any], client: DifyClient) -> dict[str, Any]:
    result = client.chat(str(case["question"]))
    contexts = _source_contexts(result.sources)
    answer = result.answer
    if answer:
        answer, _ = synthesize_response(AgentRoute.RAG.value, answer, sources=result.sources)
    return {**case, "answer": answer, "contexts": contexts}


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
    evaluated = [_execute_rag_case(case, client) for case in selected]
    judge = model or LocalDeepEvalModel()
    embeddings = getattr(judge, "embeddings", None) or GeminiEvaluationEmbeddings()
    parsed_results = []
    raw_results = []
    for index, case in enumerate(evaluated, start=1):
        if progress:
            progress(str(case.get("id", "")), index, len(evaluated))
        live = run_live_deepeval(case, model=judge)
        raw_results.append({"case_id": case.get("id"), "results": live.get("results", "")})
        parsed_results.append(
            parse_evaluate_output(case, live["evaluation"])
            if live.get("evaluation") is not None
            else {
                "case_id": case.get("id"),
                "category": case.get("category", ""),
                "metrics": {},
                "passed": False,
                "parse_error": "DeepEval não retornou objeto de avaliação.",
            }
        )
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
        "embedding_model": embeddings.model_name,
        "embedding_provider": embeddings.provider,
        "embedding_endpoint": embeddings.base_url,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report

"""Reusable, executable evaluation runners for the developer dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.answer_router import answer_competency_question, answer_comparison_question, answer_smalltalk_question, answer_structured_question
from src.deepeval_judge import LocalDeepEvalModel
from src.deepeval_report import parse_evaluate_output, summarize_results
from src.dify_client import DifyClient
from src.evaluation_ai import load_golden_cases, run_live_deepeval
from src.intent_router import Intent, route_question
from src.response_synthesis import synthesize_response
from src.security import UserRole, evaluate_input
from src.sql_tools import SkillGraphDatabase

ProgressCallback = Callable[[str, int, int], None]


def _source_contexts(sources: list[dict[str, Any]]) -> list[str]:
    return [str(source.get("content", "")) for source in sources if isinstance(source, dict) and str(source.get("content", "")).strip()]


def _execute_rag_case(case: dict[str, Any], client: DifyClient) -> dict[str, Any]:
    result = client.chat(str(case["question"]))
    contexts = _source_contexts(result.sources)
    answer = result.answer
    if answer:
        answer, _ = synthesize_response("rag", answer, sources=result.sources)
    return {**case, "answer": answer, "contexts": contexts}


def _execute_case(case: dict[str, Any], database: SkillGraphDatabase) -> dict[str, Any]:
    question = str(case.get("question", ""))
    route = route_question(question)
    security = evaluate_input(question, UserRole.DESENVOLVEDOR)
    answer = ""
    error = ""
    try:
        if not security.allowed or route.intent is Intent.BLOCKED:
            answer = security.public_message
        elif route.intent is Intent.SMALLTALK:
            answer = answer_smalltalk_question(question).answer
        elif route.intent is Intent.COMPARISON:
            routed = answer_comparison_question(question)
            answer = routed.answer
        elif route.intent is Intent.COMPETENCY_LOOKUP:
            answer = answer_competency_question(question, database).answer
        elif route.intent is Intent.SQL_INDICATOR:
            answer = answer_structured_question(question, database).answer
        else:
            rag = DifyClient.from_environment().chat(question)
            answer = rag.answer
            if answer:
                answer, _ = synthesize_response("rag", answer, sources=rag.sources)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    blocked = not security.allowed or route.intent is Intent.BLOCKED
    route_ok = route.intent.value == case.get("expected_route")
    block_ok = blocked is bool(case.get("must_block"))
    facts = [str(item).casefold() for item in case.get("expected_answer_facts", [])]
    fact_ok = not facts or not answer or all(fact in answer.casefold() for fact in facts)
    return {
        "id": case.get("id", ""),
        "category": case.get("category", ""),
        "question": question,
        "expected_route": case.get("expected_route", ""),
        "expected_must_block": bool(case.get("must_block")),
        "actual_route": route.intent.value,
        "actual_blocked": blocked,
        "answer": answer,
        "answer_preview": answer[:500],
        "answer_executed": bool(answer),
        "expected_answer_facts": case.get("expected_answer_facts", []),
        "facts_ok": fact_ok,
        "route_ok": route_ok,
        "block_ok": block_ok,
        "error": error,
        "passed": not error and route_ok and block_ok and fact_ok,
    }


def run_deterministic_evaluation(*, dataset_path: Path, output_path: Path, progress: ProgressCallback | None = None) -> dict[str, Any]:
    cases = load_golden_cases(dataset_path)
    database = SkillGraphDatabase(Path(__file__).resolve().parents[1] / "data_bd")
    results: list[dict[str, Any]] = []
    try:
        for index, case in enumerate(cases, start=1):
            if progress:
                progress(str(case.get("id", "")), index, len(cases))
            results.append(_execute_case(case, database))
    finally:
        database.close()
    report = {"mode": "backend_execution", "run_at": datetime.now(timezone.utc).isoformat(), "total": len(results), "passed": sum(bool(item["passed"]) for item in results), "results": results}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_live_evaluation(*, dataset_path: Path, output_path: Path, model: Any | None = None, case_id: str = "", progress: ProgressCallback | None = None) -> dict[str, Any]:
    cases = load_golden_cases(dataset_path)
    client = DifyClient.from_environment()
    selected: list[dict[str, Any]] = []
    for case in cases:
        if case_id and case.get("id") != case_id:
            continue
        selected.append(_execute_rag_case(case, client))
    judge = model or LocalDeepEvalModel()
    parsed_results: list[dict[str, Any]] = []
    raw_results: list[dict[str, Any]] = []
    for index, case in enumerate(selected, start=1):
        if progress:
            progress(str(case.get("id", "")), index, len(selected))
        live = run_live_deepeval(case, model=judge)
        raw_results.append({"case_id": case.get("id"), "results": live.get("results", "")})
        parsed_results.append(parse_evaluate_output(case, live["evaluation"]) if live.get("evaluation") is not None else {"case_id": case.get("id"), "category": case.get("category", ""), "metrics": {}, "passed": False, "parse_error": "DeepEval não retornou objeto de avaliação."})
    report = {"mode": "live", "run_at": datetime.now(timezone.utc).isoformat(), "cases": len(cases), "evaluated_cases": len(selected), "case_results": parsed_results, "raw_results": raw_results, "summary": summarize_results(parsed_results), "judge_model": getattr(judge, "model_name", "")}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report

import json

from src.monitoring import MetricsStore, record_event


def test_metrics_store_tracks_routes_and_blocks():
    metrics = MetricsStore()
    metrics.record(route="rag", latency_ms=10, sources_count=2)
    metrics.record(route="blocked", latency_ms=1, blocked=True)
    snapshot = metrics.snapshot()
    assert snapshot["total_requests"] == 2
    assert snapshot["blocked_requests"] == 1
    assert snapshot["routes"]["rag"] == 1
    assert snapshot["sources_seen"] == 2


def test_record_event_does_not_write_question_or_answer(tmp_path):
    path = tmp_path / "events.jsonl"
    record_event(path, request_id="r1", route="rag", status="success", latency_ms=12.5)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["request_id"] == "r1"
    assert "question" not in data
    assert "answer" not in data
    assert "api_key" not in data

from pathlib import Path

from src.comparison import extract_hours
from src.intent_router import Intent, route_question

ROOT = Path(__file__).parents[1]


def test_comparison_route():
    question = "Qual é a carga horária de um cargo sênior comparado com um júnior?"
    assert route_question(question).intent is Intent.COMPARISON


def test_extract_hours_is_source_driven():
    class Chunk:
        def __init__(self, content, source):
            self.content, self.source = content, source
    result = extract_hours([
        Chunk("| Júnior | 40 horas |", "policy.md"),
        Chunk("| Sênior | 60 horas |", "faq.md"),
        Chunk("| Pleno | 40 horas |", "policy.md"),
    ], ["Sênior", "Pleno"])
    assert {row["nível"] for row in result.rows} == {"Sênior", "Pleno"}
    assert "20 horas" in result.answer
    assert result.sources == ("faq.md", "policy.md")

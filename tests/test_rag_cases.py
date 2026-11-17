import json
from pathlib import Path

from src.evaluation_ai import load_golden_cases, validate_rag_case


ROOT = Path(__file__).parents[1]


def test_rag_goldens_have_complete_evaluation_contract():
    cases = load_golden_cases(ROOT / "evals/rag_goldens.jsonl")
    assert len(cases) == 12
    assert all(validate_rag_case(case) == [] for case in cases)


def test_rag_ground_truth_is_supported_by_reference_contexts():
    cases = load_golden_cases(ROOT / "evals/rag_goldens.jsonl")
    for case in cases:
        corpus = " ".join(case["contexts"]).casefold()
        assert case["ground_truth"].strip()
        # The expected answer may summarize several sentences, so validate
        # minimum semantic anchors rather than requiring verbatim equality.
        anchors = {
            "rag-gold-001": ("60", "sênior"),
            "rag-gold-002": ("40", "pleno"),
            "rag-gold-003": ("3 meses", "3,0", "gestor"),
            "rag-gold-004": ("15 dias", "10 dias"),
            "rag-gold-005": ("7,0",),
            "rag-gold-006": ("50%", "gestor", "rh"),
            "rag-gold-007": ("obrigatório", "gestor", "críticas"),
            "rag-gold-008": ("2",),
            "rag-gold-009": ("avaliação", "promoções", "corretivo"),
            "rag-gold-010": ("formulário", "aprovação", "certificado"),
            "rag-gold-011": ("python", "sql", "excel"),
            "rag-gold-012": ("recomendação", "promoção"),
        }[case["id"]]
        assert all(anchor.casefold() in corpus for anchor in anchors), case["id"]


def test_rag_jsonl_is_valid_json_per_line():
    path = ROOT / "evals/rag_goldens.jsonl"
    assert all(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())

"""Lightweight ML inference API separated from the training workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ONET_VERSION = "31.0"
ARTIFACT_NAME = "skillgraph_competency_tracks.pkl"


def load_artifact(path: Path) -> dict[str, Any]:
    """Load and validate a persisted inference artifact on demand."""
    import joblib

    if not path.exists():
        raise FileNotFoundError(f"Artefato ainda não existe: {path}")
    artifact = joblib.load(path)
    if artifact.get("onet_version") != ONET_VERSION or "track_profiles" not in artifact:
        raise ValueError(
            "Artefato incompatível: gere o modelo de competências O*NET novamente."
        )
    return artifact


def normalize_skill_name(name: str) -> str:
    normalized = " ".join(str(name).strip().casefold().split())
    aliases = {
        "python": "Programming",
        "programação": "Programming",
        "programming": "Programming",
        "sql": "Database Management Systems",
        "banco de dados": "Database Management Systems",
        "bancos de dados": "Database Management Systems",
        "análise de dados": "Data Analysis",
        "analise de dados": "Data Analysis",
        "data analysis": "Data Analysis",
        "machine learning": "Machine Learning",
        "aprendizado de máquina": "Machine Learning",
        "comunicação": "Communication",
        "resolução de problemas": "Complex Problem Solving",
        "problem solving": "Complex Problem Solving",
        "segurança da informação": "Information Security",
        "cibersegurança": "Information Security",
        "cloud": "Cloud Computing",
        "computação em nuvem": "Cloud Computing",
        "ia generativa": "Generative AI",
        "generative ai": "Generative AI",
    }
    return aliases.get(normalized, str(name).strip())


def _feature_aliases(feature_names: list[str]) -> dict[str, str]:
    candidates = {
        "Database Management Systems": (
            "Database Management",
            "Database Management Systems",
        ),
        "Data Analysis": ("Analyzing Data", "Data Analysis"),
        "Information Security": ("Information Security",),
        "Cloud Computing": ("Technology Design", "Cloud Computing"),
        "Machine Learning": ("Programming", "Machine Learning"),
    }
    return {
        alias: next((target for target in targets if target in feature_names), "")
        for alias, targets in candidates.items()
    }


def map_profile_skills(
    skills: dict[str, float], feature_names: list[str]
) -> tuple[dict[str, float], list[dict[str, Any]], list[dict[str, Any]]]:
    aliases = _feature_aliases(feature_names)
    recognized, unrecognized, mapped = [], [], {}
    for original, level in skills.items():
        canonical = normalize_skill_name(original)
        target = canonical if canonical in feature_names else aliases.get(canonical, "")
        if target:
            mapped[target] = float(level)
            recognized.append(
                {
                    "input": original,
                    "feature": target,
                    "level": float(level),
                    "mapped": original != target,
                }
            )
        else:
            unrecognized.append(
                {
                    "input": original,
                    "canonical": canonical,
                    "reason": "competência não presente no vocabulário do artefato",
                }
            )
    return mapped, recognized, unrecognized


def recommend_from_profile(
    path: Path,
    skills: dict[str, float],
    top_k: int = 3,
    *,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact = artifact or load_artifact(path)
    feature_names = artifact["feature_names"]
    mapped, recognized, unrecognized = map_profile_skills(skills, feature_names)
    vector = {name: 0.0 for name in feature_names}
    vector.update(mapped)
    matrix = artifact["preprocessor"].transform(
        pd.DataFrame([vector], columns=feature_names)
    )
    probabilities = artifact["model"].predict_proba(matrix)[0]
    classes = list(artifact["model"].classes_)
    order = np.argsort(probabilities)[::-1][:top_k]
    recommendations = [
        {"track": str(classes[index]), "compatibility": float(probabilities[index])}
        for index in order
    ]
    margin = (
        float(probabilities[order[0]] - probabilities[order[1]])
        if len(order) > 1
        else 1.0
    )
    best = recommendations[0]["track"] if recommendations else ""
    profile = artifact["track_profiles"].get(best, {})
    gaps = sorted(
        (
            (skill, max(0.0, float(level) - float(vector.get(skill, 0.0))))
            for skill, level in profile.items()
        ),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    try:
        from src.ml_xai import local_tree_explanation

        local = local_tree_explanation(artifact["model"], matrix, feature_names, best)
    except Exception:
        local = []
    return {
        "recommendations": recommendations,
        "priorities": [{"skill": skill, "gap": gap} for skill, gap in gaps if gap > 0],
        "skills_received": skills,
        "recognized_skills": recognized,
        "unrecognized_skills": unrecognized,
        "uncertainty": {
            "margin": margin,
            "level": "higher" if margin >= 0.2 else "moderate" if margin >= 0.08 else "lower",
            "needs_more_information": bool(unrecognized) or margin < 0.08,
        },
        "local_explanations": local,
        "input_quality": {
            "recognized_count": len(recognized),
            "unrecognized_count": len(unrecognized),
            "coverage": round(len(recognized) / max(len(skills), 1), 3),
            "unknown_skills_do_not_affect_model": True,
        },
    }


def global_explanation(
    path: Path,
    top_k: int = 15,
    *,
    artifact: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    artifact = artifact or load_artifact(path)
    from src.ml_xai import global_tree_importance

    return global_tree_importance(
        artifact["model"], artifact["feature_names"], top_k=top_k
    )

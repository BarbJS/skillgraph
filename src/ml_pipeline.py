"""Leakage-aware FLAML workflow for tech competency-track recommendations.

The training data comes exclusively from the official O*NET occupational database.
No SkillGraph employee, DuckDB, RAG, or UCI productivity data is used.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    top_k_accuracy_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

try:
    from flaml import AutoML, tune
except Exception:  # pragma: no cover - allows the chat to start before setup
    AutoML = None  # type: ignore[assignment,misc]
    tune = None  # type: ignore[assignment,misc]


ONET_VERSION = "31.0"
ONET_SOURCE_URL = "https://www.onetcenter.org/database.html"
ONET_LICENSE = "Creative Commons Attribution 4.0 International (CC BY 4.0)"
ONET_ARCHIVE_URL = "https://www.onetcenter.org/dl_files/database/db_31_0_csv.zip"
DATASET_TARGET = "track"
ONET_ATTRIBUTION = "O*NET 31.0 Database, U.S. Department of Labor"
ARTIFACT_NAME = "skillgraph_competency_tracks.pkl"
SEED = 42

# O*NET titles are grouped only to create an explicit, inspectable teaching target.
# The model recommends a development track; it does not label a person.
TRACK_RULES: dict[str, tuple[str, ...]] = {
    "Desenvolvimento de Software": (
        "software developer",
        "web developer",
        "programmer",
        "software engineer",
        "computer programmer",
        "devops engineer",
        "quality assurance",
    ),
    "Dados e Ciência de Dados": (
        "data scientist",
        "data analyst",
        "operations research",
        "statistician",
        "data warehousing",
        "database architect",
        "database administrator",
    ),
    "Engenharia de Dados e Cloud": (
        "data engineer",
        "network architect",
        "network administrator",
        "cloud",
        "computer network",
        "systems administrator",
        "systems engineer",
    ),
    "Cibersegurança": (
        "information security",
        "cybersecurity",
        "security analyst",
        "penetration",
        "forensic computer",
        "computer systems analyst",
    ),
    "IA e Machine Learning": (
        "machine learning",
        "artificial intelligence",
        "research scientist",
        "computer and information research scientist",
        "computer science teacher",
    ),
    "Tecnologia e Sistemas": (
        "computer systems analyst",
        "computer support",
        "information technology",
        "computer user support",
        "computer systems",
    ),
}


@dataclass(frozen=True)
class SplitData:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


@dataclass(frozen=True)
class ClassificationMetrics:
    macro_f1: float
    balanced_accuracy: float
    macro_precision: float
    macro_recall: float
    accuracy: float
    top_2_accuracy: float
    roc_auc_ovr: float | None


class EncodedClassifier:
    """Expose original string labels around a numeric FLAML classifier."""

    def __init__(self, estimator: Any, encoder: LabelEncoder) -> None:
        self.estimator = estimator
        self.encoder = encoder
        self.classes_ = encoder.classes_

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.encoder.inverse_transform(
            np.asarray(self.estimator.predict(X), dtype=int)
        )

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.estimator.predict_proba(X)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "EncodedClassifier":
        self.estimator.fit(X, self.encoder.transform(y))
        return self


@dataclass
class ModelResult:
    name: str
    family: str
    model: Any
    validation: ClassificationMetrics
    test: ClassificationMetrics | None = None
    config: dict[str, Any] | None = None
    error: str | None = None


def set_global_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def _download(url: str, destination: Path) -> None:
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            destination.write_bytes(response.read())
    except urllib.error.URLError:
        if shutil.which("curl") is None:
            raise
        subprocess.run(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--max-time",
                "180",
                "--output",
                str(destination),
                url,
            ],
            check=True,
        )


def fetch_onet_dataset(cache_dir: Path) -> Path:
    """Download/extract the official O*NET CSV archive into an ignored cache."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    archive = cache_dir / f"db_{ONET_VERSION.replace('.', '_')}_csv.zip"
    extracted = cache_dir / f"db_{ONET_VERSION.replace('.', '_')}_csv"
    if not extracted.exists():
        if not archive.exists():
            _download(ONET_ARCHIVE_URL, archive)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(cache_dir)
    root = extracted if extracted.exists() else cache_dir
    required = (
        "occupation_data.csv",
        "knowledge.csv",
        "essential_skills.csv",
        "transferable_skills.csv",
    )
    missing = [name for name in required if not (root / name).exists()]
    if missing:
        raise ValueError(f"Arquivo O*NET incompleto; ausentes: {missing}")
    return root


def _track_for_title(title: str) -> str | None:
    normalized = title.casefold()
    matches = [
        track
        for track, terms in TRACK_RULES.items()
        if any(term in normalized for term in terms)
    ]
    return matches[0] if len(matches) == 1 else None


def _read_levels(root: Path, filename: str) -> pd.DataFrame:
    frame = pd.read_csv(root / filename)
    frame = frame[frame["Scale ID"].eq("LV")].copy()
    frame.loc[:, "Data Value"] = pd.to_numeric(frame["Data Value"], errors="coerce")
    return frame[["O*NET-SOC Code", "Title", "Element Name", "Data Value"]].dropna(
        subset=["Element Name", "Data Value"]
    )


def build_training_frame(root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build one row per tech occupation with O*NET competency level features."""

    occupations = pd.read_csv(root / "occupation_data.csv")
    titles = occupations.assign(
        track=occupations["Title"].map(_track_for_title)
    ).dropna(subset=["track"])
    if titles["track"].nunique() < 3:
        raise ValueError("O*NET filtering produced fewer than three competency tracks.")

    # Essential and transferable skills provide a broad career profile.
    frames = [
        _read_levels(root, name)
        for name in ("essential_skills.csv", "transferable_skills.csv")
    ]
    levels = pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["O*NET-SOC Code", "Element Name"], keep="last"
    )
    levels = levels[levels["O*NET-SOC Code"].isin(titles["O*NET-SOC Code"])]
    matrix = levels.pivot_table(
        index="O*NET-SOC Code",
        columns="Element Name",
        values="Data Value",
        aggfunc="mean",
    )
    matrix = matrix.reset_index().merge(
        titles[["O*NET-SOC Code", "Title", "track"]], on="O*NET-SOC Code", how="inner"
    )
    feature_names = sorted(set(matrix.columns) - {"O*NET-SOC Code", "Title", "track"})
    matrix[feature_names] = matrix[feature_names].apply(pd.to_numeric, errors="coerce")
    metadata = {
        "feature_names": feature_names,
        "tracks": sorted(matrix["track"].unique()),
        "occupation_count": int(len(matrix)),
        "track_counts": matrix["track"].value_counts().to_dict(),
        "onet_version": ONET_VERSION,
        "source_url": ONET_SOURCE_URL,
        "license": ONET_LICENSE,
        "attribution": ONET_ATTRIBUTION,
        "modifications": "Tech occupations grouped into explicit development tracks using title keyword rules; competency levels aggregated across O*NET skills files.",
    }
    return matrix, metadata


def profile_dataset(frame: pd.DataFrame) -> dict[str, Any]:
    feature_columns = [
        column
        for column in frame.columns
        if column not in {"O*NET-SOC Code", "Title", "track"}
    ]
    return {
        "rows": int(len(frame)),
        "features": len(feature_columns),
        "tracks": frame["track"].value_counts().to_dict(),
        "nulls": {
            str(k): int(v) for k, v in frame[feature_columns].isna().sum().items() if v
        },
        "skill_coverage": int((frame[feature_columns].notna().sum() > 0).sum()),
    }


def split_dataset(frame: pd.DataFrame, seed: int = SEED) -> SplitData:
    shuffled = frame.sample(frac=1, random_state=seed).reset_index(drop=True)
    train_end = int(len(shuffled) * 0.70)
    validation_end = train_end + int(len(shuffled) * 0.20)
    return SplitData(
        shuffled.iloc[:train_end].copy(),
        shuffled.iloc[train_end:validation_end].copy(),
        shuffled.iloc[validation_end:].copy(),
    )


def make_preprocessor(feature_names: list[str]) -> Pipeline:
    return Pipeline(
        [
            (
                "columns",
                ColumnTransformer(
                    [
                        (
                            "numeric",
                            Pipeline(
                                [
                                    ("imputer", SimpleImputer(strategy="median")),
                                    ("scaler", StandardScaler()),
                                ]
                            ),
                            feature_names,
                        ),
                    ],
                    remainder="drop",
                ),
            ),
        ]
    )


def _matrices(
    split: SplitData, feature_names: list[str]
) -> tuple[
    Pipeline, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray
]:
    preprocessor = make_preprocessor(feature_names)
    train = preprocessor.fit_transform(split.train[feature_names])
    validation = preprocessor.transform(split.validation[feature_names])
    test = preprocessor.transform(split.test[feature_names])
    return (
        preprocessor,
        train,
        validation,
        test,
        split.train["track"].to_numpy(),
        split.validation["track"].to_numpy(),
        split.test["track"].to_numpy(),
    )


def _metrics(
    y_true: np.ndarray,
    prediction: np.ndarray,
    probabilities: np.ndarray | None,
    labels: list[str],
) -> ClassificationMetrics:
    top2 = (
        float(
            top_k_accuracy_score(
                y_true, probabilities, k=min(2, len(labels)), labels=labels
            )
        )
        if probabilities is not None
        else float("nan")
    )
    try:
        auc = (
            float(
                roc_auc_score(y_true, probabilities, multi_class="ovr", labels=labels)
            )
            if probabilities is not None
            else None
        )
    except ValueError:
        auc = None
    return ClassificationMetrics(
        macro_f1=float(f1_score(y_true, prediction, average="macro", zero_division=0)),
        balanced_accuracy=float(balanced_accuracy_score(y_true, prediction)),
        macro_precision=float(
            precision_score(y_true, prediction, average="macro", zero_division=0)
        ),
        macro_recall=float(
            recall_score(y_true, prediction, average="macro", zero_division=0)
        ),
        accuracy=float(accuracy_score(y_true, prediction)),
        top_2_accuracy=top2,
        roc_auc_ovr=auc,
    )


def _flaml_model(
    name: str,
    X: np.ndarray,
    y: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    *,
    time_budget: int,
    seed: int,
    custom_hp: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    # FLAML/sklearn metrics require homogeneous encoded labels.
    encoder = LabelEncoder()
    y_encoded = encoder.fit_transform(y)
    y_val_encoded = encoder.transform(y_val)

    if AutoML is None:
        raise RuntimeError("FLAML não instalado. Execute scripts/bootstrap-flaml.sh.")
    automl = AutoML()
    settings: dict[str, Any] = {
        "task": "classification",
        "metric": "macro_f1",
        "time_budget": time_budget,
        "seed": seed,
        "eval_method": "holdout",
        "X_val": X_val,
        "y_val": y_val_encoded,
        "retrain_full": False,
        "estimator_list": [name],
        "verbose": 0,
    }
    if custom_hp:
        settings["custom_hp"] = custom_hp
    automl.fit(X, y_encoded, **settings)
    return EncodedClassifier(automl.model, encoder), dict(automl.best_config)


def train_compare(
    split: SplitData,
    feature_names: list[str],
    *,
    time_budget: int = 20,
    seed: int = SEED,
) -> tuple[Pipeline, list[ModelResult], dict[str, Any]]:
    set_global_seed(seed)
    preprocessor, X, X_val, X_test, y, y_val, y_test = _matrices(split, feature_names)
    labels = sorted(set(y))
    results: list[ModelResult] = []
    baseline = DummyClassifier(strategy="prior").fit(X, y)
    results.append(
        ModelResult(
            "baseline_prior",
            "DummyClassifier",
            baseline,
            _metrics(
                y_val, baseline.predict(X_val), baseline.predict_proba(X_val), labels
            ),
            config={"strategy": "prior"},
        )
    )
    for estimator in ("rf", "lgbm"):
        try:
            model, config = _flaml_model(
                estimator, X, y, X_val, y_val, time_budget=time_budget, seed=seed
            )
            results.append(
                ModelResult(
                    estimator,
                    f"FLAML/{estimator}",
                    model,
                    _metrics(
                        y_val, model.predict(X_val), model.predict_proba(X_val), labels
                    ),
                    config=config,
                )
            )
        except Exception as exc:
            results.append(ModelResult(estimator, f"FLAML/{estimator}", None, ClassificationMetrics(*(float("nan"),) * 6, None), error=str(exc)))  # type: ignore[arg-type]
    return preprocessor, results, {"X_test": X_test, "y_test": y_test, "labels": labels}


def choose_model(results: list[ModelResult]) -> ModelResult:
    valid = [item for item in results if item.error is None and item.model is not None]
    if not valid:
        raise RuntimeError("Nenhum modelo concluiu o treinamento FLAML.")
    return max(
        valid,
        key=lambda item: (item.validation.macro_f1, item.validation.balanced_accuracy),
    )


def fine_tune(
    split: SplitData,
    selected: ModelResult,
    feature_names: list[str],
    *,
    time_budget: int = 30,
    seed: int = SEED,
) -> tuple[Pipeline, ModelResult]:
    preprocessor, X, X_val, _, y, y_val, _ = _matrices(split, feature_names)
    custom_hp = None
    if tune is not None and selected.name == "rf":
        custom_hp = {
            "rf": {
                "n_estimators": {
                    "domain": tune.randint(lower=50, upper=600),
                    "low_cost_init_value": 100,
                },
                "max_features": {"domain": tune.uniform(lower=0.4, upper=1.0)},
            }
        }
    elif tune is not None and selected.name == "lgbm":
        custom_hp = {
            "lgbm": {
                "learning_rate": {
                    "domain": tune.loguniform(lower=0.01, upper=0.3),
                    "low_cost_init_value": 0.1,
                },
                "num_leaves": {
                    "domain": tune.randint(lower=4, upper=64),
                    "low_cost_init_value": 31,
                },
                "n_estimators": {
                    "domain": tune.randint(lower=50, upper=600),
                    "low_cost_init_value": 100,
                },
            }
        }
    if selected.name == "baseline_prior":
        return preprocessor, selected
    model, config = _flaml_model(
        selected.name,
        X,
        y,
        X_val,
        y_val,
        time_budget=time_budget,
        seed=seed,
        custom_hp=custom_hp,
    )
    labels = sorted(set(y))
    tuned = ModelResult(
        f"{selected.name}_tuned",
        f"FLAML/{selected.name} fine-tuned",
        model,
        _metrics(y_val, model.predict(X_val), model.predict_proba(X_val), labels),
        config=config,
    )
    return (
        preprocessor,
        (
            tuned
            if (tuned.validation.macro_f1 >= selected.validation.macro_f1)
            else selected
        ),
    )


def fit_final_and_test(
    split: SplitData, tuned: ModelResult, feature_names: list[str], *, seed: int = SEED
) -> tuple[Pipeline, ModelResult, ClassificationMetrics]:
    train_validation = pd.concat([split.train, split.validation], ignore_index=True)
    preprocessor = make_preprocessor(feature_names)
    X = preprocessor.fit_transform(train_validation[feature_names])
    X_test = preprocessor.transform(split.test[feature_names])
    y = train_validation["track"].to_numpy()
    y_test = split.test["track"].to_numpy()
    model = (
        DummyClassifier(strategy="prior").fit(X, y)
        if tuned.name == "baseline_prior"
        else tuned.model.fit(X, y)
    )
    labels = sorted(set(y))
    metrics = _metrics(
        y_test, model.predict(X_test), model.predict_proba(X_test), labels
    )
    return (
        preprocessor,
        ModelResult(
            tuned.name, tuned.family, model, tuned.validation, metrics, tuned.config
        ),
        metrics,
    )


def build_track_profiles(
    frame: pd.DataFrame, feature_names: list[str]
) -> dict[str, dict[str, float]]:
    profiles: dict[str, dict[str, float]] = {}
    for track, group in frame.groupby("track"):
        profiles[track] = {
            name: float(group[name].median()) if group[name].notna().any() else 0.0
            for name in feature_names
        }
    return profiles


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
    path: Path, skills: dict[str, float], top_k: int = 3
) -> dict[str, Any]:
    artifact = load_artifact(path)
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
            "level": (
                "higher" if margin >= 0.2 else "moderate" if margin >= 0.08 else "lower"
            ),
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


def global_explanation(path: Path, top_k: int = 15) -> list[dict[str, Any]]:
    artifact = load_artifact(path)
    from src.ml_xai import global_tree_importance

    return global_tree_importance(
        artifact["model"], artifact["feature_names"], top_k=top_k
    )


def save_artifact(
    path: Path,
    preprocessor: Pipeline,
    result: ModelResult,
    metadata: dict[str, Any],
    track_profiles: dict[str, dict[str, float]],
    *,
    seed: int = SEED,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "preprocessor": preprocessor,
            "model": result.model,
            "feature_names": metadata["feature_names"],
            "track_profiles": track_profiles,
            "tracks": metadata["tracks"],
            "seed": seed,
            "source_url": ONET_SOURCE_URL,
            "onet_version": ONET_VERSION,
            "license": ONET_LICENSE,
            "attribution": ONET_ATTRIBUTION,
            "validation_metrics": asdict(result.validation),
            "test_metrics": asdict(result.test) if result.test else None,
            "config": result.config,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        path,
    )


def load_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Artefato ainda não existe: {path}")
    artifact = joblib.load(path)
    if artifact.get("onet_version") != ONET_VERSION or "track_profiles" not in artifact:
        raise ValueError(
            "Artefato incompatível: gere o modelo de competências O*NET novamente."
        )
    return artifact


def report_to_json(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

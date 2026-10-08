import pandas as pd

from src.ml_pipeline import (
    build_training_frame,
    normalize_skill_name,
    profile_dataset,
    split_dataset,
)


def test_split_is_deterministic_and_has_requested_proportions():
    frame = pd.DataFrame(
        {
            "track": ["A", "B", "C", "A", "B", "C", "A", "B", "C", "A"],
            "skill": range(10),
        }
    )
    first = split_dataset(frame, seed=42)
    second = split_dataset(frame, seed=42)
    assert [len(first.train), len(first.validation), len(first.test)] == [7, 2, 1]
    assert first.train.equals(second.train)


def test_profile_reports_tracks_and_features():
    frame = pd.DataFrame(
        {
            "O*NET-SOC Code": ["1", "2"],
            "Title": ["Data Analyst", "Software Developer"],
            "track": ["Dados", "Software"],
            "Python": [3.0, 4.0],
        }
    )
    profile = profile_dataset(frame)
    assert profile["rows"] == 2
    assert profile["features"] == 1
    assert profile["tracks"] == {"Dados": 1, "Software": 1}


def test_skill_aliases_are_user_facing_and_domain_relevant():
    assert normalize_skill_name("Python") == "Programming"
    assert normalize_skill_name("IA generativa") == "Generative AI"
    assert normalize_skill_name("SQL") == "Database Management Systems"


def test_onet_fixture_builds_explicit_track_target(tmp_path):
    root = tmp_path
    pd.DataFrame(
        {
            "O*NET-SOC Code": ["1", "2", "3"],
            "Title": [
                "Software Developer",
                "Data Scientist",
                "Information Security Analyst",
            ],
            "Description": ["", "", ""],
        }
    ).to_csv(root / "occupation_data.csv", index=False)
    for filename in ("essential_skills.csv", "transferable_skills.csv"):
        pd.DataFrame(
            {
                "O*NET-SOC Code": ["1", "2", "3"],
                "Title": [
                    "Software Developer",
                    "Data Scientist",
                    "Information Security Analyst",
                ],
                "Element ID": ["a", "b", "c"],
                "Element Name": ["Programming", "Programming", "Programming"],
                "Scale ID": ["LV"] * 3,
                "Scale Name": ["Level"] * 3,
                "Data Value": [4.0, 3.0, 2.0],
            }
        ).to_csv(root / filename, index=False)
    frame, metadata = build_training_frame(root)
    assert "track" in frame
    assert metadata["occupation_count"] == 3

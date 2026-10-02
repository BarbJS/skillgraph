from src.ml_pipeline import map_profile_skills


def test_unknown_skills_are_reported_not_silently_zeroed():
    mapped, recognized, unknown = map_profile_skills({"Python": 4, "SQL": 3, "IA generativa": 2}, ["Programming", "Mathematics"])
    assert mapped == {"Programming": 4.0}
    assert recognized[0]["input"] == "Python"
    assert {item["input"] for item in unknown} == {"SQL", "IA generativa"}

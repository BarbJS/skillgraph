from src.agents.schemas import EmployeeProfile
from src.resume_profile import render_profile


def test_render_profile_formats_recognized_unknown_and_missing_skills():
    text = render_profile(
        EmployeeProfile.model_validate(
            {
                "skills": [
                    {
                        "name": "Python",
                        "level": 4,
                        "confidence": 0.88,
                        "evidence": "APIs Python",
                    }
                ],
                "unrecognized_skills": [
                    {
                        "name": "Kubernetes",
                        "level": None,
                        "confidence": 0.2,
                        "evidence": "menção breve",
                    }
                ],
                "missing_information": ["Profundidade em cloud"],
            }
        )
    )
    assert "Python" in text
    assert "4/5" in text
    assert "Kubernetes" in text
    assert "não determinável" in text
    assert "Profundidade em cloud" in text


def test_render_profile_does_not_turn_missing_level_into_zero():
    text = render_profile(
        EmployeeProfile.model_validate(
            {
                "skills": [{"name": "Cloud", "level": None, "confidence": 0.2}],
                "unrecognized_skills": [],
            }
        )
    )
    assert "não determinável" in text
    assert "nível 0/5" not in text

import pandas as pd


def test_grouped_manager_chart_numeric_conversion_handles_multiple_columns(monkeypatch):
    import app

    rendered = []
    monkeypatch.setattr(app.st, "markdown", lambda value, **kwargs: rendered.append(value))
    frame = pd.DataFrame(
        {
            "Competência": ["Python", "SQL"],
            "lacunas_criticas": [2, "1"],
            "lacunas_comuns": [3, "4"],
        }
    )

    app._render_grouped_manager_chart(
        frame, "Competência", ["lacunas_criticas", "lacunas_comuns"]
    )

    assert rendered
    assert "Python" in rendered[0]
    assert "SQL" in rendered[0]
    assert "5.0" in rendered[0]

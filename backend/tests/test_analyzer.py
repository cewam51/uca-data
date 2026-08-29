from pathlib import Path

from app.analyzer import analyze_csv


def test_analyze_csv_returns_schema_count_and_preview(tmp_path: Path):
    csv_path = tmp_path / "population.csv"
    csv_path.write_text("COM,LIBCOM,ANNEE,POPULATION\n75056,Paris,2022,2102650\n69123,Lyon,2022,522250\n")

    result = analyze_csv(csv_path)

    assert result["row_count"] == 2
    assert [column["name"] for column in result["columns"]] == [
        "COM",
        "LIBCOM",
        "ANNEE",
        "POPULATION",
    ]
    assert result["preview"][0]["LIBCOM"] == "Paris"

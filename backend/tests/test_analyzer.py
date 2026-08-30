from pathlib import Path

from app.analyzer import (
    analyze_join,
    calculate_indicator,
    calculate_single_source_chart,
    preview_single_source_chart,
    profile_csv_columns,
)


def test_single_source_chart_aggregates_selected_columns(tmp_path: Path):
    source = tmp_path / "source.csv"
    source.write_text(
        "annee,commune,valeur\n2023,Paris,10\n2023,Lyon,5\n2024,Paris,8\n",
        encoding="utf-8",
    )

    result = calculate_single_source_chart(source, "annee", "valeur", "sum", "line")

    assert result["formula"] == "Somme de « valeur » pour chaque « annee »"
    assert result["result_count"] == 2
    assert result["rows"] == [
        {"label": "2023", "value": 15.0},
        {"label": "2024", "value": 8.0},
    ]


def test_scatter_uses_two_numeric_columns_without_filling_missing_values(tmp_path: Path):
    source = tmp_path / "source.csv"
    source.write_text("x,y\n1,2\n3,inconnu\n4,8\n", encoding="utf-8")

    result = calculate_single_source_chart(source, "x", "y", "average", "scatter")

    assert result["rows"] == [{"x": 1.0, "y": 2.0}, {"x": 4.0, "y": 8.0}]
    assert result["excluded_rows"] == 1
    assert result["warnings"]


def test_chart_preview_uses_only_first_twenty_compatible_rows(tmp_path: Path):
    source = tmp_path / "source.csv"
    source.write_text(
        "categorie,x,valeur\n"
        + "\n".join(f"A,{index},{index}" for index in range(1, 26))
        + "\n",
        encoding="utf-8",
    )

    result = preview_single_source_chart(source, "categorie", "valeur", "sum")

    assert result["sampled_rows"] == 20
    assert result["grouped_rows"] == [{"label": "A", "value": 210.0}]
    assert result["scatter_rows"] == []


def test_profiles_columns_and_suggests_roles(tmp_path: Path):
    source = tmp_path / "source.csv"
    source.write_text(
        "Code commune,Année,valeur\n75056,2022,10\n69123,2023,20\n",
        encoding="utf-8",
    )

    profiles = profile_csv_columns(source)

    assert profiles[0]["suggested_roles"] == ["commune"]
    assert profiles[1]["suggested_roles"] == ["année"]
    assert profiles[2]["suggested_roles"] == []
    assert profiles[0]["distinct_count"] == 2
    assert sorted(profiles[0]["samples"]) == [69123, 75056]


def test_join_reports_matches_duplicates_and_unmatched_keys(tmp_path: Path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    left.write_text(
        "commune,annee,valeur\nParis,2023,10\nLyon,2023,20\nLyon,2023,5\nLille,2023,4\n",
        encoding="utf-8",
    )
    right.write_text(
        "ville,year,mesure\nPARIS,2023,2\nLyon,2023,4\nNantes,2023,6\n",
        encoding="utf-8",
    )

    result = analyze_join(left, right, "commune", "ville", "annee", "year")

    assert result["dimensions"] == ["commune", "année"]
    assert result["matched_keys"] == 2
    assert result["left_match_rate"] == 66.7
    assert result["right_match_rate"] == 66.7
    assert result["left_duplicate_keys"] == 1
    assert result["right_duplicate_keys"] == 0
    assert result["geography"] == {
        "left_communes": 3,
        "right_communes": 3,
        "matched_communes": 2,
        "left_match_rate": 66.7,
        "right_match_rate": 66.7,
    }
    assert result["periods"]["matched_years"] == 1
    assert result["left_unmatched_samples"] == [{"commune": "LILLE", "année": "2023"}]
    assert result["right_unmatched_samples"] == [{"commune": "NANTES", "année": "2023"}]
    assert any("Périmètres géographiques différents" in warning for warning in result["warnings"])
    assert len(result["warnings"]) == 3


def test_join_without_year_warns_instead_of_inventing_one(tmp_path: Path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    left.write_text("commune,valeur\nParis,10\n", encoding="utf-8")
    right.write_text("ville,mesure\nParis,2\n", encoding="utf-8")

    result = analyze_join(left, right, "commune", "ville")

    assert result["dimensions"] == ["commune"]
    assert result["matched_keys"] == 1
    assert "uniquement sur la commune" in result["warnings"][0]


def test_join_reports_different_periods_explicitly(tmp_path: Path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    left.write_text("commune,annee,valeur\nParis,2022,10\nParis,2023,12\n", encoding="utf-8")
    right.write_text("ville,year,mesure\nParis,2023,2\nParis,2024,3\n", encoding="utf-8")

    result = analyze_join(left, right, "commune", "ville", "annee", "year")

    assert result["periods"] == {
        "left": {"first": "2022", "last": "2023", "distinct_years": 2},
        "right": {"first": "2023", "last": "2024", "distinct_years": 2},
        "matched_years": 1,
    }
    assert any("Périodes différentes" in warning for warning in result["warnings"])


def test_indicator_aggregates_before_calculating_a_transparent_ratio(tmp_path: Path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    left.write_text(
        "commune,annee,valeur\nParis,2023,10\nParis,2023,5\nLyon,2023,8\n",
        encoding="utf-8",
    )
    right.write_text(
        "ville,year,mesure\nPARIS,2023,3\nLyon,2023,0\n",
        encoding="utf-8",
    )

    result = calculate_indicator(
        left,
        right,
        "commune",
        "ville",
        "valeur",
        "mesure",
        "sum",
        "sum",
        "ratio_percent",
        "annee",
        "year",
    )

    assert result["formula"] == "(Somme de « valeur » (source 1) ÷ Somme de « mesure » (source 2)) × 100"
    assert result["dimension_matches"] == 2
    assert result["result_count"] == 1
    assert result["excluded_zero_denominator"] == 1
    assert result["rows"] == [
        {
            "commune": "PARIS",
            "année": "2023",
            "source_1_value": 15.0,
            "source_2_value": 3.0,
            "value": 500.0,
        }
    ]


def test_indicator_difference_does_not_fill_missing_values(tmp_path: Path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    left.write_text("commune,valeur\nParis,10\nLyon,4\n", encoding="utf-8")
    right.write_text("ville,mesure\nParis,2\nLyon,inconnu\n", encoding="utf-8")

    result = calculate_indicator(
        left,
        right,
        "commune",
        "ville",
        "valeur",
        "mesure",
        "average",
        "average",
        "difference",
    )

    assert result["dimension_matches"] == 2
    assert result["result_count"] == 1
    assert result["excluded_missing_values"] == 1
    assert result["rows"][0]["value"] == 8.0

from pathlib import Path

from app.analyzer import analyze_join, calculate_indicator, profile_csv_columns


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
    assert result["left_unmatched_samples"] == [{"commune": "LILLE", "année": "2023"}]
    assert result["right_unmatched_samples"] == [{"commune": "NANTES", "année": "2023"}]
    assert len(result["warnings"]) == 2


def test_join_without_year_warns_instead_of_inventing_one(tmp_path: Path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    left.write_text("commune,valeur\nParis,10\n", encoding="utf-8")
    right.write_text("ville,mesure\nParis,2\n", encoding="utf-8")

    result = analyze_join(left, right, "commune", "ville")

    assert result["dimensions"] == ["commune"]
    assert result["matched_keys"] == 1
    assert "uniquement sur la commune" in result["warnings"][0]


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

from app.publication import build_publication_snapshot, snapshot_sha256


def sample_project():
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Mobilité communale",
        "sources": [
            {
                "position": 1,
                "id": "22222222-2222-2222-2222-222222222222",
                "title": "Parc automobile",
                "publisher": "Producteur public",
                "catalog_source": "data.gouv.fr",
                "catalog_dataset_id": "dataset-1",
                "catalog_resource_id": "resource-1",
                "source_url": "https://example.test/source.csv",
                "sha256": "a" * 64,
                "size_bytes": 120,
                "row_count": 2,
                "columns": [{"name": "commune", "type": "VARCHAR"}],
                "dimensions": {"commune": "commune", "année": "annee"},
            },
            {
                "position": 2,
                "id": "33333333-3333-3333-3333-333333333333",
                "title": "Population",
                "publisher": "Autre producteur",
                "catalog_source": "data.europa.eu",
                "catalog_dataset_id": "dataset-2",
                "catalog_resource_id": "resource-2",
                "source_url": "https://example.test/population.csv",
                "sha256": "b" * 64,
                "size_bytes": 140,
                "row_count": 2,
                "columns": [{"name": "ville", "type": "VARCHAR"}],
                "dimensions": {"commune": "ville", "année": "year"},
            },
        ],
        "join_analysis": {"matched_keys": 2, "warnings": []},
        "indicator": {
            "title": "Voitures pour 100 habitants",
            "formula": "source 1 ÷ source 2 × 100",
            "result_count": 2,
            "rows": [{"commune": "PARIS", "value": 42}],
        },
    }


def test_publication_snapshot_contains_provenance_and_reproducibility():
    snapshot = build_publication_snapshot(
        sample_project(),
        1,
        "2026-08-29T18:00:00+00:00",
        "Camille",
        "Mobilité communale",
        "Deux communes sont comparées.",
        "L’indicateur décrit un rapport.",
        "Les données ne couvrent qu’une année.",
    )

    assert snapshot["version_number"] == 1
    assert snapshot["indicator"]["formula"] == "source 1 ÷ source 2 × 100"
    assert snapshot["sources"][0]["source_url"] == "https://example.test/source.csv"
    assert snapshot["reproducibility"]["source_hashes"] == ["a" * 64, "b" * 64]
    assert "Aucune valeur n’est inventée" in snapshot["reproducibility"]["missing_data_policy"]


def test_snapshot_fingerprint_is_stable_and_detects_a_change():
    arguments = (
        sample_project(),
        1,
        "2026-08-29T18:00:00+00:00",
        "Camille",
        "Mobilité communale",
        "Deux communes sont comparées.",
        "L’indicateur décrit un rapport.",
        "Les données ne couvrent qu’une année.",
    )
    first = build_publication_snapshot(*arguments)
    second = build_publication_snapshot(*arguments)
    changed = build_publication_snapshot(*arguments[:-3], "Résumé différent.", *arguments[-2:])

    assert snapshot_sha256(first) == snapshot_sha256(second)
    assert snapshot_sha256(first) != snapshot_sha256(changed)
    assert len(snapshot_sha256(first)) == 64

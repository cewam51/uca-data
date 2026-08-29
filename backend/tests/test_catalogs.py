import asyncio

import httpx
import pytest

from app.catalog_importer import (
    CatalogResourceError,
    _data_europa_tabular_resources,
    _research_data_gouv_tabular_resources,
    _select_best_data_gouv_resource,
    _validate_public_url,
)
from app.catalogs import search_data_europa, search_data_gouv, search_recherche_data_gouv


def test_normalizes_data_gouv_result():
    def handler(request):
        assert request.url.params["q"] == "population"
        return httpx.Response(200, json={"data": [{
            "id": "abc", "title": "Population communale", "description": "<p>Valeurs annuelles</p>",
            "organization": {"name": "INSEE"}, "last_update": "2026-01-02",
            "license": "fr-lo", "page": "https://example.test/dataset",
            "resources": [
                {"id": "r1", "title": "Données", "format": "csv", "url": "https://example.test/data.csv"},
                {"id": "r2", "title": "API", "format": "json", "url": "https://example.test/data.json"},
            ],
        }]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await search_data_gouv(client, "population", 5)

    result = asyncio.run(run())[0]
    assert result["publisher"] == "INSEE"
    assert result["formats"] == ["CSV", "JSON"]
    assert result["description"] == "Valeurs annuelles"
    assert result["can_explore"] is True


def test_prefers_french_european_metadata():
    def handler(_):
        return httpx.Response(200, json={"result": {"results": [{
            "id": "eu-1", "title": {"fr": "Titre français", "en": "English title"},
            "description": {"fr": "Description française"}, "publisher": {"name": "Eurostat"},
            "resource": "https://data.europa.eu/example", "modified": "2026-02-03",
            "distributions": [{
                "id": "r1", "title": {"fr": "Fichier"}, "format": {"label": "CSV"},
                "access_url": ["https://example.test/data.csv"],
                "download_url": ["https://example.test/download.csv"],
            }],
        }]}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await search_data_europa(client, "emploi", 5)

    result = asyncio.run(run())[0]
    assert result["title"] == "Titre français"
    assert result["formats"] == ["CSV"]
    assert result["resources"][0]["title"] == "Fichier"
    assert result["resources"][0]["url"] == "https://example.test/download.csv"
    assert result["can_explore"] is True


def test_normalizes_research_data_result():
    def handler(request):
        if request.url.path.endswith("/:persistentId/"):
            return httpx.Response(200, json={"data": {"latestVersion": {"files": [{
                "restricted": False,
                "dataFile": {
                    "id": 7,
                    "filename": "etude.tab",
                    "contentType": "text/tab-separated-values",
                    "filesize": 123,
                },
            }]}}})
        return httpx.Response(200, json={"data": {"items": [{
            "global_id": "doi:10/example", "name": "Étude", "description": "Données scientifiques",
            "publisher": "Université", "updatedAt": "2026-03-04", "url": "https://doi.org/10/example",
            "fileCount": 2,
        }]}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await search_recherche_data_gouv(client, "climat", 5)

    result = asyncio.run(run())[0]
    assert result["source"] == "Recherche Data Gouv"
    assert result["publisher"] == "Université"
    assert result["can_explore"] is True
    assert result["formats"] == ["TSV"]
    assert result["can_check"] is False


@pytest.mark.parametrize("url", [
    "http://localhost/data.csv",
    "http://127.0.0.1/data.csv",
    "file:///etc/passwd",
])
def test_blocks_non_public_download_addresses(url):
    with pytest.raises(CatalogResourceError):
        _validate_public_url(url)


def test_automatically_selects_latest_available_main_csv():
    selected = _select_best_data_gouv_resource([
        {"id": "json", "format": "json", "url": "https://example.test/data.json"},
        {"id": "dead", "format": "csv", "url": "https://example.test/dead.csv", "extras": {"check:available": False}},
        {"id": "old", "format": "csv", "url": "https://example.test/old.csv", "type": "main", "last_modified": "2025-01-01"},
        {"id": "new", "format": "csv", "url": "https://example.test/new.csv", "type": "main", "last_modified": "2026-01-01"},
    ])

    assert selected["id"] == "new"


def test_data_europa_prefers_download_url_and_keeps_access_url_as_fallback():
    resources = _data_europa_tabular_resources([{
        "id": "eu-csv",
        "title": {"fr": "Données"},
        "format": {"id": "CSV", "label": "CSV"},
        "download_url": ["https://example.test/download.csv"],
        "access_url": ["https://example.test/landing"],
    }])

    assert [resource["url"] for resource in resources] == [
        "https://example.test/download.csv",
        "https://example.test/landing",
    ]


def test_data_europa_rejects_a_catalog_page_mislabeled_as_csv():
    with pytest.raises(CatalogResourceError):
        _data_europa_tabular_resources([{
            "id": "not-a-file",
            "title": {"fr": "Données"},
            "format": {"id": "CSV"},
            "access_url": ["http://data.europa.eu/88u/dataset/example"],
        }])


def test_research_data_gouv_keeps_only_public_tabular_files():
    metadata = {"data": {"latestVersion": {"files": [
        {"restricted": False, "dataFile": {
            "id": 42, "filename": "resultats.tab",
            "contentType": "text/tab-separated-values", "filesize": 120,
        }},
        {"restricted": True, "dataFile": {
            "id": 43, "filename": "secret.csv", "contentType": "text/csv",
        }},
        {"restricted": False, "dataFile": {
            "id": 44, "filename": "rapport.pdf", "contentType": "application/pdf",
        }},
    ]}}}

    resources = _research_data_gouv_tabular_resources(metadata, "https://example.test")

    assert resources == [{
        "id": "42",
        "title": "resultats.tab",
        "format": "TSV",
        "url": "https://example.test/api/access/datafile/42",
        "size": 120,
    }]

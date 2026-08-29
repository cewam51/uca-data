import asyncio

import httpx
import pytest

from app.catalog_importer import CatalogResourceError, _validate_public_url
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
            "distributions": [{"id": "r1", "title": {"fr": "Fichier"}, "format": {"label": "CSV"}}],
        }]}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await search_data_europa(client, "emploi", 5)

    result = asyncio.run(run())[0]
    assert result["title"] == "Titre français"
    assert result["formats"] == ["CSV"]
    assert result["resources"][0]["title"] == "Fichier"


def test_normalizes_research_data_result():
    def handler(_):
        return httpx.Response(200, json={"data": {"items": [{
            "global_id": "doi:10/example", "name": "Étude", "description": "Données scientifiques",
            "publisher": "Université", "updatedAt": "2026-03-04", "url": "https://doi.org/10/example",
        }]}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await search_recherche_data_gouv(client, "climat", 5)

    result = asyncio.run(run())[0]
    assert result["source"] == "Recherche Data Gouv"
    assert result["publisher"] == "Université"


@pytest.mark.parametrize("url", [
    "http://localhost/data.csv",
    "http://127.0.0.1/data.csv",
    "file:///etc/passwd",
])
def test_blocks_non_public_download_addresses(url):
    with pytest.raises(CatalogResourceError):
        _validate_public_url(url)

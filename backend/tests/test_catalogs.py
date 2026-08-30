import asyncio
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest

from app.catalog_importer import (
    CatalogResourceError,
    _data_europa_tabular_resources,
    _download_open_response,
    _import_insee_archive,
    _research_data_gouv_tabular_resources,
    _select_best_data_gouv_resource,
    _validate_public_url,
    resolve_catalog_url,
)
from app.catalogs import search_data_europa, search_data_gouv, search_insee, search_recherche_data_gouv
from app.catalogs import _is_usable_result
from app.service import CsvUploadService


class MemoryRepository:
    def __init__(self):
        self.saved = []

    def save(self, dataset):
        self.saved.append(dataset)

    def update_provenance(self, dataset):
        pass


def test_searches_official_insee_catalog_and_keeps_french_csv():
    def handler(request):
        assert request.url.path == "/melodi/catalog/all"
        return httpx.Response(200, json=[{
            "identifier": "DS_POP_TEST",
            "title": [{"content": "Population par commune", "lang": "fr"}],
            "abstract": [{"content": "Population municipale annuelle", "lang": "fr"}],
            "modified": "2026-08-01",
            "product": [{
                "id": "DS_POP_TEST_CSV_FR",
                "format": "CSV",
                "language": "FR",
                "accessURL": "https://api.insee.fr/melodi/file/test",
                "byteSize": 900_000_000,
            }],
        }])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await search_insee(client, "population commune", 5)

    result = asyncio.run(run())[0]
    assert result["id"] == "DS_POP_TEST"
    assert result["source"] == "Insee"
    assert result["formats"] == ["CSV"]
    assert result["can_explore"] is True
    assert result["resources"][0]["size"] == 900_000_000


def test_imports_data_csv_from_insee_zip_without_using_metadata_file(tmp_path):
    archive = BytesIO()
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("DS_TEST_data.csv", "GEO;TIME_PERIOD;OBS_VALUE\n75056;2024;2100000\n69123;2024;520000\n")
        zipped.writestr("DS_TEST_metadata.csv", "COD_VAR;LIB_VAR\nGEO;Géographie\n")
    archive.seek(0)
    service = CsvUploadService(tmp_path, 1024 * 1024, MemoryRepository())

    result = _import_insee_archive(archive, service)

    assert result["original_name"] == "DS_TEST_data.csv"
    assert result["row_count"] == 2
    assert [column["name"] for column in result["columns"]] == [
        "GEO", "TIME_PERIOD", "OBS_VALUE",
    ]


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


@pytest.mark.parametrize(("url", "expected"), [
    ("https://www.data.gouv.fr/fr/datasets/population-communale/", ("data.gouv.fr", "population-communale")),
    ("https://data.europa.eu/data/datasets/emploi-1?locale=fr", ("data.europa.eu", "emploi-1")),
    ("https://catalogue-donnees.insee.fr/fr/explorateur/DS_POPULATION", ("Insee", "DS_POPULATION")),
    ("https://entrepot.recherche.data.gouv.fr/dataset.xhtml?persistentId=doi:10.57745/ABCD", ("Recherche Data Gouv", "doi:10.57745/ABCD")),
    ("https://doi.org/10.57745/ABCD", ("Recherche Data Gouv", "doi:10.57745/ABCD")),
])
def test_resolves_supported_catalog_links(url, expected):
    assert resolve_catalog_url(url) == expected


def test_keeps_direct_data_gouv_resource_as_a_file_url():
    assert resolve_catalog_url("https://www.data.gouv.fr/fr/datasets/r/file-id") is None


def test_imports_an_open_direct_csv_response(tmp_path):
    repository = MemoryRepository()
    service = CsvUploadService(tmp_path, 0, repository)
    response = httpx.Response(
        200,
        headers={"content-type": "text/csv"},
        content=b"commune,population\nParis,2100000\n",
        request=httpx.Request("GET", "https://example.test/population.csv"),
    )

    result = _download_open_response(
        response,
        "https://example.test/population.csv",
        {
            "id": "https://example.test/population.csv",
            "title": "population.csv",
            "format": "CSV",
            "url": "https://example.test/population.csv",
        },
        service,
        "example.test",
    )

    assert result["row_count"] == 1
    assert result["catalog_source"] == "example.test"
    assert result["source_url"] == "https://example.test/population.csv"


def test_automatically_selects_latest_available_main_csv():
    selected = _select_best_data_gouv_resource([
        {"id": "json", "format": "json", "url": "https://example.test/data.json"},
        {"id": "dead", "format": "csv", "url": "https://example.test/dead.csv", "extras": {"check:available": False}},
        {"id": "old", "format": "csv", "url": "https://example.test/old.csv", "type": "main", "last_modified": "2025-01-01"},
        {"id": "new", "format": "csv", "url": "https://example.test/new.csv", "type": "main", "last_modified": "2026-01-01"},
    ])

    assert selected["id"] == "new"


def test_uses_an_xlsx_when_a_data_gouv_dataset_has_no_csv():
    selected = _select_best_data_gouv_resource([
        {"id": "pdf", "format": "PDF", "url": "https://example.test/readme.pdf"},
        {"id": "excel", "format": "XLSX", "url": "https://example.test/data.xlsx"},
    ])

    assert selected["id"] == "excel"


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


def test_data_europa_recognizes_the_xlsx_mime_type():
    resources = _data_europa_tabular_resources([{
        "id": "eu-xlsx",
        "title": {"fr": "Classeur"},
        "format": {"id": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        "download_url": ["https://example.test/data.xlsx"],
    }])

    assert resources[0]["format"] == "XLSX"
    assert resources[0]["url"] == "https://example.test/data.xlsx"


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


def test_research_data_gouv_recognizes_an_xlsx_file():
    metadata = {"data": {"latestVersion": {"files": [{
        "restricted": False,
        "dataFile": {
            "id": 55,
            "filename": "resultats.xlsx",
            "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "filesize": 456,
        },
    }]}}}

    resources = _research_data_gouv_tabular_resources(metadata, "https://example.test")

    assert resources[0]["format"] == "XLSX"
    assert resources[0]["url"] == "https://example.test/api/access/datafile/55"


def test_hides_results_that_cannot_be_used_in_the_project():
    assert _is_usable_result({"can_explore": True}) is True
    assert _is_usable_result({"can_check": True}) is True
    assert _is_usable_result({"can_explore": False, "can_check": False}) is False

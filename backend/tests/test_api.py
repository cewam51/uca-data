from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from app.main import app
from app.service import CsvUploadService


class MemoryRepository:
    def __init__(self):
        self.saved = []

    def save(self, dataset):
        self.saved.append(dataset)

    def update_provenance(self, dataset):
        self.saved[-1].update({
            key: dataset.get(key)
            for key in ("catalog_source", "catalog_dataset_id", "catalog_resource_id", "source_url")
        })


def test_no_direct_file_upload_is_exposed():
    assert "/api/datasets" not in app.openapi()["paths"]


def test_project_can_receive_two_persisted_sources():
    paths = app.openapi()["paths"]

    assert "post" in paths["/api/projects"]
    assert "get" in paths["/api/projects"]
    assert "get" in paths["/api/projects/{project_id}"]
    assert "post" in paths["/api/projects/{project_id}/sources"]
    assert "get" in paths["/api/projects/{project_id}/qualification"]
    assert "post" in paths["/api/projects/{project_id}/dimensions"]
    assert "post" in paths["/api/projects/{project_id}/join-analysis"]
    assert "post" in paths["/api/projects/{project_id}/indicator"]
    assert "post" in paths["/api/projects/{project_id}/chart"]
    assert "post" in paths["/api/projects/{project_id}/chart-preview"]
    assert "post" in paths["/api/sources/explore"]
    assert "delete" in paths["/api/projects/{project_id}/sources/{dataset_id}"]
    assert "get" in paths["/api/projects/{project_id}/versions"]
    assert "post" in paths["/api/projects/{project_id}/versions"]
    assert "get" in paths["/api/publications/{version_id}"]
    assert "post" in paths["/api/publications/{version_id}/comments"]
    assert "post" in paths["/api/catalogs/insee/{dataset_id}/explore"]


def test_upload_keeps_original_and_returns_analysis(tmp_path: Path):
    repository = MemoryRepository()
    service = CsvUploadService(tmp_path, 1024 * 1024, repository)
    body = service.import_csv(
        "population.csv",
        BytesIO(b"ville,population\nParis,2102650\n"),
    )

    assert body["row_count"] == 1
    assert len(body["sha256"]) == 64
    assert (tmp_path / body["stored_name"]).read_bytes() == b"ville,population\nParis,2102650\n"
    assert repository.saved[0]["id"] == body["id"]


def test_rejects_non_csv(tmp_path: Path):
    service = CsvUploadService(tmp_path, 1024, MemoryRepository())

    try:
        service.import_csv("notes.txt", BytesIO(b"not csv"))
    except ValueError as error:
        assert "CSV" in str(error)
    else:
        raise AssertionError("Un fichier non CSV doit être refusé")


def test_imports_a_tab_separated_research_table(tmp_path: Path):
    service = CsvUploadService(tmp_path, 1024 * 1024, MemoryRepository())

    body = service.import_tabular(
        "communes.tab",
        BytesIO(b"code\tpopulation\n01001\t806\n"),
    )

    assert body["row_count"] == 1
    assert body["original_name"] == "communes.tab"
    assert [column["name"] for column in body["columns"]] == ["code", "population"]


def test_imports_xlsx_and_keeps_the_original_workbook(tmp_path: Path):
    workbook = Workbook()
    cover = workbook.active
    cover.title = "Présentation"
    cover.append(["Jeu de données"])
    cover.append(["Documentation seulement"])
    data = workbook.create_sheet("Prénoms")
    data.append(["COMMUNE", "PRENOM", "NOMBRE", "ANNEE"])
    data.append(["Épinal", "Jules", 10, 2011])
    data.append(["Épinal", "Léa", 9, 2011])
    source = BytesIO()
    workbook.save(source)
    source.seek(0)
    original_bytes = source.getvalue()
    service = CsvUploadService(tmp_path, 0, MemoryRepository())

    body = service.import_xlsx("prenoms.xlsx", source)

    assert body["original_name"] == "prenoms.xlsx"
    assert body["source_format"] == "XLSX"
    assert body["source_sheet"] == "Prénoms"
    assert body["row_count"] == 2
    assert [column["name"] for column in body["columns"]] == [
        "COMMUNE", "PRENOM", "NOMBRE", "ANNEE",
    ]
    assert (tmp_path / f'{body["id"]}.xlsx').read_bytes() == original_bytes
    assert (tmp_path / body["stored_name"]).suffix == ".csv"

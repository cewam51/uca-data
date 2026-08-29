from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, get_service
from app.service import CsvUploadService


class MemoryRepository:
    def __init__(self):
        self.saved = []

    def save(self, dataset):
        self.saved.append(dataset)


def test_upload_keeps_original_and_returns_analysis(tmp_path: Path):
    repository = MemoryRepository()
    service = CsvUploadService(tmp_path, 1024 * 1024, repository)
    app.dependency_overrides[get_service] = lambda: service

    client = TestClient(app)
    response = client.post(
        "/api/datasets",
        files={"file": ("population.csv", b"ville,population\nParis,2102650\n", "text/csv")},
    )
    client.close()

    app.dependency_overrides.clear()
    assert response.status_code == 201
    body = response.json()
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

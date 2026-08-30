from hashlib import sha256
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from .analyzer import analyze_csv
from .repository import DatasetRepository
from .xlsx_converter import convert_xlsx_to_csv


class UploadTooLargeError(ValueError):
    pass


class CsvUploadService:
    def __init__(self, upload_dir: Path, max_upload_bytes: int, repository: DatasetRepository):
        self.upload_dir = upload_dir
        self.max_upload_bytes = max_upload_bytes
        self.repository = repository

    def import_csv(self, original_name: str, stream: BinaryIO) -> dict:
        if not original_name.lower().endswith(".csv"):
            raise ValueError("Seuls les fichiers CSV sont acceptés.")

        return self.import_tabular(original_name, stream)

    def import_tabular(self, original_name: str, stream: BinaryIO) -> dict:
        suffix = Path(original_name).suffix.lower()
        if suffix not in {".csv", ".tsv", ".tab"}:
            raise ValueError("Seules les tables CSV et TSV sont acceptées.")

        dataset_id = str(uuid4())
        stored_name = f"{dataset_id}{suffix}"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        destination = self.upload_dir / stored_name
        digest = sha256()
        size_bytes = 0

        try:
            with destination.open("xb") as target:
                while chunk := stream.read(1024 * 1024):
                    size_bytes += len(chunk)
                    if self.max_upload_bytes > 0 and size_bytes > self.max_upload_bytes:
                        raise UploadTooLargeError(
                            f"Le fichier dépasse la limite de {self.max_upload_bytes} octets."
                        )
                    digest.update(chunk)
                    target.write(chunk)

            analysis = analyze_csv(destination)
            result = {
                "id": dataset_id,
                "original_name": Path(original_name).name,
                "stored_name": stored_name,
                "sha256": digest.hexdigest(),
                "size_bytes": size_bytes,
                **analysis,
            }
            self.repository.save(result)
            return result
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def import_xlsx(self, original_name: str, stream: BinaryIO) -> dict:
        if not original_name.lower().endswith(".xlsx"):
            raise ValueError("Seuls les classeurs Excel XLSX sont acceptés.")

        dataset_id = str(uuid4())
        original_destination = self.upload_dir / f"{dataset_id}.xlsx"
        converted_destination = self.upload_dir / f"{dataset_id}.csv"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        digest = sha256()
        size_bytes = 0

        try:
            with original_destination.open("xb") as target:
                while chunk := stream.read(1024 * 1024):
                    size_bytes += len(chunk)
                    if self.max_upload_bytes > 0 and size_bytes > self.max_upload_bytes:
                        raise UploadTooLargeError(
                            f"Le fichier dépasse la limite de {self.max_upload_bytes} octets."
                        )
                    digest.update(chunk)
                    target.write(chunk)

            conversion = convert_xlsx_to_csv(original_destination, converted_destination)
            analysis = analyze_csv(converted_destination)
            result = {
                "id": dataset_id,
                "original_name": Path(original_name).name,
                "stored_name": converted_destination.name,
                "sha256": digest.hexdigest(),
                "size_bytes": size_bytes,
                "source_format": "XLSX",
                "source_sheet": conversion["sheet_name"],
                **analysis,
            }
            self.repository.save(result)
            return result
        except Exception:
            original_destination.unlink(missing_ok=True)
            converted_destination.unlink(missing_ok=True)
            raise

    def attach_provenance(self, dataset: dict) -> None:
        self.repository.update_provenance(dataset)

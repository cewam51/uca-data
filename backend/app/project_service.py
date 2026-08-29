from pathlib import Path
from typing import Any
from uuid import UUID

from .analyzer import analyze_join, profile_csv_columns
from .repository import PostgresDatasetRepository


class ProjectAnalysisService:
    def __init__(self, upload_dir: Path, repository: PostgresDatasetRepository):
        self.upload_dir = upload_dir
        self.repository = repository

    def qualification(self, project_id: UUID) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        files = self.repository.get_project_source_files(project_id)
        files_by_id = {source["id"]: source for source in files}
        for source in project["sources"]:
            source_file = files_by_id[source["id"]]
            source["columns"] = profile_csv_columns(
                self._source_path(source_file["stored_name"])
            )
        return project

    def analyze_join(self, project_id: UUID) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        files = self.repository.get_project_source_files(project_id)
        if len(files) != 2:
            raise ValueError("Ajoutez deux sources avant d’analyser le croisement.")
        if not all(source["commune_column"] for source in files):
            raise ValueError("Choisissez une colonne commune dans chaque source.")

        left, right = files
        analysis = analyze_join(
            self._source_path(left["stored_name"]),
            self._source_path(right["stored_name"]),
            left["commune_column"],
            right["commune_column"],
            left["year_column"],
            right["year_column"],
        )
        project_sources = {source["id"]: source for source in project["sources"]}
        analysis["sources"] = [
            {
                "dataset_id": source["id"],
                "title": project_sources[source["id"]]["title"],
                "sha256": project_sources[source["id"]]["sha256"],
                "commune_column": source["commune_column"],
                "year_column": source["year_column"],
            }
            for source in files
        ]
        self.repository.save_join_analysis(project_id, analysis)
        return analysis

    def _source_path(self, stored_name: str) -> Path:
        upload_dir = self.upload_dir.resolve()
        path = (upload_dir / stored_name).resolve()
        if path.parent != upload_dir:
            raise ValueError("Chemin de source invalide.")
        if not path.is_file():
            raise LookupError("Le fichier source conservé est introuvable.")
        return path

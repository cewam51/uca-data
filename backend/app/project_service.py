from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from .analyzer import (
    analyze_join,
    calculate_indicator,
    calculate_single_source_chart,
    preview_single_source_chart,
    profile_csv_columns,
)
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

    def calculate_chart(
        self,
        project_id: UUID,
        title: str,
        dataset_id: UUID,
        category_column: str,
        value_column: str,
        aggregation: str,
        chart_type: str,
    ) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        files = self.repository.get_project_source_files(project_id)
        source = next((item for item in files if item["id"] == str(dataset_id)), None)
        if source is None:
            raise ValueError("Cette source ne fait pas partie du projet.")
        columns_by_name = {column["name"]: column for column in source["columns"]}
        for column_name in (category_column, value_column):
            if column_name not in columns_by_name:
                raise ValueError(f"Colonne introuvable : {column_name}")
        numeric_prefixes = (
            "TINYINT", "UTINYINT", "SMALLINT", "USMALLINT", "INTEGER",
            "UINTEGER", "BIGINT", "UBIGINT", "HUGEINT", "FLOAT", "DOUBLE",
            "DECIMAL", "REAL",
        )
        if not columns_by_name[value_column]["type"].startswith(numeric_prefixes):
            raise ValueError(f"La colonne « {value_column} » n’est pas numérique.")
        if chart_type == "scatter" and not columns_by_name[category_column]["type"].startswith(numeric_prefixes):
            raise ValueError("Un nuage de points nécessite deux colonnes numériques.")

        result = calculate_single_source_chart(
            self._source_path(source["stored_name"]),
            category_column,
            value_column,
            aggregation,
            chart_type,
        )
        project_source = next(item for item in project["sources"] if item["id"] == source["id"])
        result.update(
            {
                "title": title,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": {
                    "dataset_id": source["id"],
                    "title": project_source["title"],
                    "sha256": project_source["sha256"],
                },
            }
        )
        self.repository.save_chart(project_id, result)
        return result

    def preview_chart(
        self,
        project_id: UUID,
        dataset_id: UUID,
        category_column: str,
        value_column: str,
        aggregation: str,
    ) -> dict[str, Any]:
        files = self.repository.get_project_source_files(project_id)
        source = next((item for item in files if item["id"] == str(dataset_id)), None)
        if source is None:
            raise ValueError("Cette source ne fait pas partie du projet.")
        column_names = {column["name"] for column in source["columns"]}
        for column_name in (category_column, value_column):
            if column_name not in column_names:
                raise ValueError(f"Colonne introuvable : {column_name}")
        result = preview_single_source_chart(
            self._source_path(source["stored_name"]),
            category_column,
            value_column,
            aggregation,
        )
        result["dataset_id"] = source["id"]
        return result

    def calculate_indicator(
        self,
        project_id: UUID,
        title: str,
        operation: str,
        configurations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        files = self.repository.get_project_source_files(project_id)
        if len(files) != 2:
            raise ValueError("Ajoutez deux sources avant de calculer un indicateur.")
        if not project.get("join_analysis"):
            raise ValueError("Vérifiez d’abord le croisement des deux sources.")
        if project["join_analysis"]["matched_keys"] == 0:
            raise ValueError("Aucune clé ne correspond : cet indicateur ne peut pas être calculé.")

        expected_ids = {source["id"] for source in files}
        configured_ids = {str(item["dataset_id"]) for item in configurations}
        if configured_ids != expected_ids or len(configurations) != 2:
            raise ValueError("Choisissez une valeur pour chacune des deux sources.")
        configuration_by_id = {str(item["dataset_id"]): item for item in configurations}
        for source in files:
            configuration = configuration_by_id[source["id"]]
            columns_by_name = {column["name"]: column for column in source["columns"]}
            value_column = configuration["value_column"]
            if value_column not in columns_by_name:
                raise ValueError(f"Colonne de valeur introuvable : {value_column}")
            if value_column in {source["commune_column"], source["year_column"]}:
                raise ValueError("Une dimension commune/année ne peut pas servir de valeur à calculer.")
            if not columns_by_name[value_column]["type"].startswith(
                (
                    "TINYINT",
                    "UTINYINT",
                    "SMALLINT",
                    "USMALLINT",
                    "INTEGER",
                    "UINTEGER",
                    "BIGINT",
                    "UBIGINT",
                    "HUGEINT",
                    "FLOAT",
                    "DOUBLE",
                    "DECIMAL",
                    "REAL",
                )
            ):
                raise ValueError(f"La colonne « {value_column} » n’est pas numérique.")

        left, right = files
        left_configuration = configuration_by_id[left["id"]]
        right_configuration = configuration_by_id[right["id"]]
        result = calculate_indicator(
            self._source_path(left["stored_name"]),
            self._source_path(right["stored_name"]),
            left["commune_column"],
            right["commune_column"],
            left_configuration["value_column"],
            right_configuration["value_column"],
            left_configuration["aggregation"],
            right_configuration["aggregation"],
            operation,
            left["year_column"],
            right["year_column"],
        )
        project_sources = {source["id"]: source for source in project["sources"]}
        result.update(
            {
                "title": title,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "sources": [
                    {
                        "dataset_id": source["id"],
                        "title": project_sources[source["id"]]["title"],
                        "sha256": project_sources[source["id"]]["sha256"],
                        "value_column": configuration_by_id[source["id"]]["value_column"],
                        "aggregation": configuration_by_id[source["id"]]["aggregation"],
                    }
                    for source in files
                ],
            }
        )
        self.repository.save_indicator(project_id, result)
        return result

    def _source_path(self, stored_name: str) -> Path:
        upload_dir = self.upload_dir.resolve()
        path = (upload_dir / stored_name).resolve()
        if path.parent != upload_dir:
            raise ValueError("Chemin de source invalide.")
        if not path.is_file():
            raise LookupError("Le fichier source conservé est introuvable.")
        return path

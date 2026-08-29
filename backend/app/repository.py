from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb


class DatasetRepository(Protocol):
    def save(self, dataset: dict[str, Any]) -> None: ...

    def update_provenance(self, dataset: dict[str, Any]) -> None: ...


class PostgresDatasetRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def initialize(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    id UUID PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    sha256 CHAR(64) NOT NULL,
                    size_bytes BIGINT NOT NULL,
                    row_count BIGINT NOT NULL,
                    columns_json JSONB NOT NULL,
                    imported_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                ALTER TABLE datasets
                ADD COLUMN IF NOT EXISTS provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id UUID PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    join_analysis_json JSONB
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_sources (
                    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    dataset_id UUID NOT NULL REFERENCES datasets(id),
                    position SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 2),
                    label TEXT,
                    publisher TEXT,
                    commune_column TEXT,
                    year_column TEXT,
                    added_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (project_id, dataset_id),
                    UNIQUE (project_id, position)
                )
                """
            )
            connection.execute(
                "ALTER TABLE project_sources ADD COLUMN IF NOT EXISTS label TEXT"
            )
            connection.execute(
                "ALTER TABLE project_sources ADD COLUMN IF NOT EXISTS publisher TEXT"
            )
            connection.execute(
                "ALTER TABLE project_sources ADD COLUMN IF NOT EXISTS commune_column TEXT"
            )
            connection.execute(
                "ALTER TABLE project_sources ADD COLUMN IF NOT EXISTS year_column TEXT"
            )
            connection.execute(
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS join_analysis_json JSONB"
            )

    def save(self, dataset: dict[str, Any]) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO datasets (
                    id, original_name, stored_name, sha256, size_bytes,
                    row_count, columns_json, imported_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    UUID(dataset["id"]),
                    dataset["original_name"],
                    dataset["stored_name"],
                    dataset["sha256"],
                    dataset["size_bytes"],
                    dataset["row_count"],
                    Jsonb(dataset["columns"]),
                    datetime.now(timezone.utc),
                ),
            )

    def update_provenance(self, dataset: dict[str, Any]) -> None:
        provenance = {
            "catalog_source": dataset.get("catalog_source"),
            "catalog_dataset_id": dataset.get("catalog_dataset_id"),
            "catalog_resource_id": dataset.get("catalog_resource_id"),
            "source_url": dataset.get("source_url"),
        }
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "UPDATE datasets SET provenance_json = %s WHERE id = %s",
                (Jsonb(provenance), UUID(dataset["id"])),
            )

    def create_project(
        self,
        title: str,
        dataset_id: UUID,
        source_title: str,
        source_publisher: str | None,
    ) -> dict[str, Any]:
        project_id = uuid4()
        now = datetime.now(timezone.utc)
        with psycopg.connect(self.database_url) as connection:
            if connection.execute(
                "SELECT 1 FROM datasets WHERE id = %s", (dataset_id,)
            ).fetchone() is None:
                raise LookupError("Jeu de données introuvable.")
            connection.execute(
                "INSERT INTO projects (id, title, created_at) VALUES (%s, %s, %s)",
                (project_id, title, now),
            )
            connection.execute(
                """
                INSERT INTO project_sources (
                    project_id, dataset_id, position, label, publisher, added_at
                ) VALUES (%s, %s, 1, %s, %s, %s)
                """,
                (project_id, dataset_id, source_title, source_publisher, now),
            )
        return self.get_project(project_id)

    def add_project_source(
        self,
        project_id: UUID,
        dataset_id: UUID,
        source_title: str,
        source_publisher: str | None,
    ) -> dict[str, Any]:
        with psycopg.connect(self.database_url) as connection:
            if connection.execute(
                "SELECT 1 FROM projects WHERE id = %s", (project_id,)
            ).fetchone() is None:
                raise LookupError("Projet introuvable.")
            if connection.execute(
                "SELECT 1 FROM datasets WHERE id = %s", (dataset_id,)
            ).fetchone() is None:
                raise LookupError("Jeu de données introuvable.")
            existing = connection.execute(
                """
                SELECT position FROM project_sources
                WHERE project_id = %s AND dataset_id = %s
                """,
                (project_id, dataset_id),
            ).fetchone()
            if existing is not None:
                return self.get_project(project_id)
            count = connection.execute(
                "SELECT COUNT(*) FROM project_sources WHERE project_id = %s",
                (project_id,),
            ).fetchone()[0]
            if count >= 2:
                raise ValueError("Ce projet possède déjà ses deux sources.")
            connection.execute(
                """
                INSERT INTO project_sources (
                    project_id, dataset_id, position, label, publisher, added_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    project_id,
                    dataset_id,
                    count + 1,
                    source_title,
                    source_publisher,
                    datetime.now(timezone.utc),
                ),
            )
        return self.get_project(project_id)

    def get_project(self, project_id: UUID) -> dict[str, Any]:
        with psycopg.connect(self.database_url) as connection:
            project = connection.execute(
                "SELECT id, title, created_at, join_analysis_json FROM projects WHERE id = %s",
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError("Projet introuvable.")
            rows = connection.execute(
                """
                SELECT ps.position, d.id, d.original_name, d.sha256, d.size_bytes,
                       d.row_count, d.columns_json, d.provenance_json,
                       COALESCE(ps.label, d.original_name), ps.publisher,
                       ps.commune_column, ps.year_column
                FROM project_sources ps
                JOIN datasets d ON d.id = ps.dataset_id
                WHERE ps.project_id = %s
                ORDER BY ps.position
                """,
                (project_id,),
            ).fetchall()

        sources = [
            {
                "position": row[0],
                "id": str(row[1]),
                "original_name": row[2],
                "sha256": row[3],
                "size_bytes": row[4],
                "row_count": row[5],
                "columns": row[6],
                **(row[7] or {}),
                "title": row[8],
                "publisher": row[9],
                "dimensions": {
                    "commune": row[10],
                    "année": row[11],
                },
            }
            for row in rows
        ]
        return {
            "id": str(project[0]),
            "title": project[1],
            "created_at": project[2].isoformat(),
            "sources": sources,
            "join_analysis": project[3],
        }

    def get_project_source_files(self, project_id: UUID) -> list[dict[str, Any]]:
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """
                SELECT ps.position, d.id, d.stored_name, d.columns_json,
                       ps.commune_column, ps.year_column
                FROM project_sources ps
                JOIN datasets d ON d.id = ps.dataset_id
                WHERE ps.project_id = %s
                ORDER BY ps.position
                """,
                (project_id,),
            ).fetchall()
        if not rows:
            raise LookupError("Projet introuvable ou sans source.")
        return [
            {
                "position": row[0],
                "id": str(row[1]),
                "stored_name": row[2],
                "columns": row[3],
                "commune_column": row[4],
                "year_column": row[5],
            }
            for row in rows
        ]

    def set_dimensions(
        self,
        project_id: UUID,
        configurations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        sources = self.get_project_source_files(project_id)
        if len(sources) != 2:
            raise ValueError("Ajoutez deux sources avant de choisir les colonnes.")
        expected_ids = {source["id"] for source in sources}
        configured_ids = {str(item["dataset_id"]) for item in configurations}
        if configured_ids != expected_ids or len(configurations) != 2:
            raise ValueError("Les colonnes doivent être choisies pour les deux sources du projet.")

        source_by_id = {source["id"]: source for source in sources}
        with psycopg.connect(self.database_url) as connection:
            for item in configurations:
                dataset_id = str(item["dataset_id"])
                column_names = {
                    column["name"] for column in source_by_id[dataset_id]["columns"]
                }
                commune_column = item["commune_column"]
                year_column = item.get("year_column")
                if commune_column not in column_names:
                    raise ValueError(f"Colonne commune introuvable : {commune_column}")
                if year_column and year_column not in column_names:
                    raise ValueError(f"Colonne année introuvable : {year_column}")
                connection.execute(
                    """
                    UPDATE project_sources
                    SET commune_column = %s, year_column = %s
                    WHERE project_id = %s AND dataset_id = %s
                    """,
                    (commune_column, year_column, project_id, UUID(dataset_id)),
                )
            connection.execute(
                "UPDATE projects SET join_analysis_json = NULL WHERE id = %s",
                (project_id,),
            )
        return self.get_project(project_id)

    def save_join_analysis(self, project_id: UUID, analysis: dict[str, Any]) -> None:
        with psycopg.connect(self.database_url) as connection:
            result = connection.execute(
                "UPDATE projects SET join_analysis_json = %s WHERE id = %s",
                (Jsonb(analysis), project_id),
            )
            if result.rowcount == 0:
                raise LookupError("Projet introuvable.")

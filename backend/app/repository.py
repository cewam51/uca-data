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
                    created_at TIMESTAMPTZ NOT NULL
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
                "SELECT id, title, created_at FROM projects WHERE id = %s",
                (project_id,),
            ).fetchone()
            if project is None:
                raise LookupError("Projet introuvable.")
            rows = connection.execute(
                """
                SELECT ps.position, d.id, d.original_name, d.sha256, d.size_bytes,
                       d.row_count, d.columns_json, d.provenance_json,
                       COALESCE(ps.label, d.original_name), ps.publisher
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
            }
            for row in rows
        ]
        return {
            "id": str(project[0]),
            "title": project[1],
            "created_at": project[2].isoformat(),
            "sources": sources,
        }

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


class DatasetRepository(Protocol):
    def save(self, dataset: dict[str, Any]) -> None: ...


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

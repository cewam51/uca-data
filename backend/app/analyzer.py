from pathlib import Path
from typing import Any

import duckdb


def analyze_csv(path: Path, preview_limit: int = 20) -> dict[str, Any]:
    """Analyse un CSV sans modifier son contenu."""
    connection = duckdb.connect(":memory:")
    try:
        path_value = str(path)
        relation = connection.read_csv(path_value, header=True, auto_detect=True)
        columns = [
            {"name": name, "type": str(column_type)}
            for name, column_type in zip(relation.columns, relation.types, strict=True)
        ]
        row_count = relation.aggregate("count(*) AS row_count").fetchone()[0]
        rows = relation.limit(preview_limit).fetchall()
        preview = [
            {name: _json_value(value) for name, value in zip(relation.columns, row, strict=True)}
            for row in rows
        ]
        return {"row_count": row_count, "columns": columns, "preview": preview}
    finally:
        connection.close()


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)

from pathlib import Path
from typing import Any
import re

import duckdb


COMMUNE_TERMS = (
    "commune",
    "code commune",
    "code_commune",
    "codgeo",
    "insee",
    "municipality",
    "municipalite",
    "ville",
)
YEAR_TERMS = ("annee", "year", "millesime", "exercice")


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


def profile_csv_columns(path: Path, sample_limit: int = 3) -> list[dict[str, Any]]:
    """Décrit les colonnes et suggère des rôles sans décider à la place de l’utilisateur."""
    connection = duckdb.connect(":memory:")
    try:
        relation = connection.read_csv(str(path), header=True, auto_detect=True)
        profiles = []
        for name, column_type in zip(relation.columns, relation.types, strict=True):
            identifier = _quote_identifier(name)
            non_null_count, distinct_count = connection.execute(
                f"""
                SELECT count({identifier}), count(DISTINCT {identifier})
                FROM relation
                """
            ).fetchone()
            samples = [
                _json_value(row[0])
                for row in connection.execute(
                    f"""
                    SELECT DISTINCT {identifier}
                    FROM relation
                    WHERE {identifier} IS NOT NULL
                    LIMIT ?
                    """,
                    [sample_limit],
                ).fetchall()
            ]
            roles = _suggest_roles(name, str(column_type), samples)
            profiles.append(
                {
                    "name": name,
                    "type": str(column_type),
                    "non_null_count": non_null_count,
                    "distinct_count": distinct_count,
                    "samples": samples,
                    "suggested_roles": roles,
                }
            )
        return profiles
    finally:
        connection.close()


def analyze_join(
    left_path: Path,
    right_path: Path,
    left_commune: str,
    right_commune: str,
    left_year: str | None = None,
    right_year: str | None = None,
) -> dict[str, Any]:
    """Mesure une jointure déterministe sans modifier ni compléter les données."""
    connection = duckdb.connect(":memory:")
    try:
        left = connection.read_csv(str(left_path), header=True, auto_detect=True)
        right = connection.read_csv(str(right_path), header=True, auto_detect=True)
        _require_column(left.columns, left_commune)
        _require_column(right.columns, right_commune)
        if left_year:
            _require_column(left.columns, left_year)
        if right_year:
            _require_column(right.columns, right_year)

        uses_year = bool(left_year and right_year)
        left_keys = _key_query("left_source", left_commune, left_year if uses_year else None)
        right_keys = _key_query("right_source", right_commune, right_year if uses_year else None)
        connection.register("left_source", left)
        connection.register("right_source", right)
        connection.execute(f"CREATE TEMP TABLE left_keys AS {left_keys}")
        connection.execute(f"CREATE TEMP TABLE right_keys AS {right_keys}")

        left_distinct, left_duplicates = connection.execute(
            "SELECT count(*), count(*) FILTER (WHERE source_rows > 1) FROM left_keys"
        ).fetchone()
        right_distinct, right_duplicates = connection.execute(
            "SELECT count(*), count(*) FILTER (WHERE source_rows > 1) FROM right_keys"
        ).fetchone()
        matched = connection.execute(
            """
            SELECT count(*) FROM left_keys l
            INNER JOIN right_keys r USING (commune_key, year_key)
            """
        ).fetchone()[0]
        left_unmatched = _unmatched_samples(connection, "left_keys", "right_keys")
        right_unmatched = _unmatched_samples(connection, "right_keys", "left_keys")

        left_rate = _rate(matched, left_distinct)
        right_rate = _rate(matched, right_distinct)
        warnings = []
        if not uses_year:
            warnings.append(
                "Aucune année commune n’est sélectionnée dans les deux sources : "
                "la comparaison porte uniquement sur la commune."
            )
        if left_duplicates or right_duplicates:
            warnings.append(
                "Plusieurs lignes partagent la même clé dans au moins une source. "
                "Une agrégation devra être choisie avant de calculer un indicateur."
            )
        if matched == 0:
            warnings.append(
                "Aucune clé ne correspond. Vérifiez que les deux colonnes utilisent "
                "les mêmes codes ou les mêmes noms de commune."
            )
        elif left_rate < 80 or right_rate < 80:
            warnings.append(
                "Moins de 80 % des clés correspondent dans au moins une source. "
                "Les lignes non appariées doivent être examinées."
            )

        return {
            "dimensions": ["commune", *(["année"] if uses_year else [])],
            "left_distinct_keys": left_distinct,
            "right_distinct_keys": right_distinct,
            "matched_keys": matched,
            "left_match_rate": left_rate,
            "right_match_rate": right_rate,
            "left_duplicate_keys": left_duplicates,
            "right_duplicate_keys": right_duplicates,
            "left_unmatched_samples": left_unmatched,
            "right_unmatched_samples": right_unmatched,
            "warnings": warnings,
        }
    finally:
        connection.close()


def _suggest_roles(name: str, column_type: str, samples: list[Any]) -> list[str]:
    normalized = _normalize_label(name)
    roles = []
    if any(term in normalized for term in COMMUNE_TERMS):
        roles.append("commune")
    if any(term in normalized for term in YEAR_TERMS):
        roles.append("année")
    elif column_type in {"BIGINT", "INTEGER", "SMALLINT"} and samples:
        numeric_samples = [value for value in samples if isinstance(value, int)]
        if numeric_samples and all(1800 <= value <= 2200 for value in numeric_samples):
            roles.append("année")
    return roles


def _normalize_label(value: str) -> str:
    replacements = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
    return re.sub(r"[^a-z0-9]+", " ", value.lower().translate(replacements)).strip()


def _key_query(relation: str, commune: str, year: str | None) -> str:
    commune_identifier = _quote_identifier(commune)
    commune_key = (
        f"upper(trim(regexp_replace(CAST({commune_identifier} AS VARCHAR), "
        "'\\s+', ' ', 'g')))"
    )
    year_key = "''"
    conditions = [f"{commune_identifier} IS NOT NULL", f"trim(CAST({commune_identifier} AS VARCHAR)) <> ''"]
    if year:
        year_identifier = _quote_identifier(year)
        year_key = f"trim(CAST({year_identifier} AS VARCHAR))"
        conditions.extend(
            [f"{year_identifier} IS NOT NULL", f"trim(CAST({year_identifier} AS VARCHAR)) <> ''"]
        )
    return f"""
        SELECT {commune_key} AS commune_key, {year_key} AS year_key, count(*) AS source_rows
        FROM {relation}
        WHERE {' AND '.join(conditions)}
        GROUP BY commune_key, year_key
    """


def _unmatched_samples(
    connection: duckdb.DuckDBPyConnection,
    source_table: str,
    other_table: str,
) -> list[dict[str, str | None]]:
    rows = connection.execute(
        f"""
        SELECT s.commune_key, nullif(s.year_key, '')
        FROM {source_table} s
        LEFT JOIN {other_table} o USING (commune_key, year_key)
        WHERE o.commune_key IS NULL
        ORDER BY s.commune_key, s.year_key
        LIMIT 5
        """
    ).fetchall()
    return [{"commune": row[0], "année": row[1]} for row in rows]


def _rate(matched: int, total: int) -> float:
    return round((matched / total * 100) if total else 0, 1)


def _require_column(columns: list[str], name: str) -> None:
    if name not in columns:
        raise ValueError(f"Colonne introuvable : {name}")


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)

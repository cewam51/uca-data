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
AGGREGATIONS = {
    "sum": ("sum", "Somme"),
    "average": ("avg", "Moyenne"),
    "minimum": ("min", "Minimum"),
    "maximum": ("max", "Maximum"),
    "count": ("count", "Nombre de valeurs"),
}
OPERATIONS = {
    "ratio_percent": "Rapport en pourcentage",
    "difference": "Différence",
}
CHART_TYPES = {"bar", "line", "scatter", "table"}


def preview_single_source_chart(
    path: Path,
    category_column: str,
    value_column: str,
    aggregation: str,
    sample_limit: int = 20,
) -> dict[str, Any]:
    """Prépare les mini-aperçus à partir des premières lignes numériques utilisables."""
    if aggregation not in AGGREGATIONS:
        raise ValueError("Agrégation non autorisée.")
    if category_column == value_column:
        raise ValueError("Choisissez deux colonnes différentes.")

    connection = duckdb.connect(":memory:")
    try:
        relation = connection.read_csv(str(path), header=True, auto_detect=True)
        _require_column(relation.columns, category_column)
        _require_column(relation.columns, value_column)
        connection.register("source", relation)
        category = _quote_identifier(category_column)
        value = _quote_identifier(value_column)
        rows = connection.execute(
            f"""
            SELECT CAST({category} AS VARCHAR) AS label,
                   try_cast({category} AS DOUBLE) AS numeric_category,
                   try_cast({value} AS DOUBLE) AS numeric_value
            FROM source
            WHERE {category} IS NOT NULL
              AND trim(CAST({category} AS VARCHAR)) <> ''
              AND try_cast({value} AS DOUBLE) IS NOT NULL
            LIMIT ?
            """,
            [sample_limit],
        ).fetchall()

        grouped: dict[str, list[float]] = {}
        for label, _, numeric_value in rows:
            grouped.setdefault(label, []).append(float(numeric_value))
        grouped_rows = [
            {"label": label, "value": _rounded(_aggregate_preview(values, aggregation))}
            for label, values in grouped.items()
        ]
        scatter_rows = [
            {"x": _rounded(numeric_category), "y": _rounded(numeric_value)}
            for _, numeric_category, numeric_value in rows
            if numeric_category is not None
        ]
        return {
            "category_column": category_column,
            "value_column": value_column,
            "aggregation": aggregation,
            "sampled_rows": len(rows),
            "grouped_rows": grouped_rows,
            "scatter_rows": scatter_rows,
        }
    finally:
        connection.close()


def _aggregate_preview(values: list[float], aggregation: str) -> float:
    if aggregation == "sum":
        return sum(values)
    if aggregation == "average":
        return sum(values) / len(values)
    if aggregation == "minimum":
        return min(values)
    if aggregation == "maximum":
        return max(values)
    return float(len(values))


def calculate_single_source_chart(
    path: Path,
    category_column: str,
    value_column: str,
    aggregation: str,
    chart_type: str,
    result_limit: int = 100,
) -> dict[str, Any]:
    """Prépare un graphique déterministe à partir de deux colonnes d'un CSV."""
    if aggregation not in AGGREGATIONS:
        raise ValueError("Agrégation non autorisée.")
    if chart_type not in CHART_TYPES:
        raise ValueError("Type de graphique non autorisé.")
    if category_column == value_column:
        raise ValueError("Choisissez deux colonnes différentes.")

    connection = duckdb.connect(":memory:")
    try:
        relation = connection.read_csv(str(path), header=True, auto_detect=True)
        _require_column(relation.columns, category_column)
        _require_column(relation.columns, value_column)
        connection.register("source", relation)
        category = _quote_identifier(category_column)
        value = _quote_identifier(value_column)
        numeric_category = f"try_cast({category} AS DOUBLE)"
        numeric_value = f"try_cast({value} AS DOUBLE)"

        if chart_type == "scatter":
            valid_count = connection.execute(
                f"SELECT count(*) FROM source WHERE {numeric_category} IS NOT NULL AND {numeric_value} IS NOT NULL"
            ).fetchone()[0]
            rejected_count = connection.execute(
                f"SELECT count(*) FROM source WHERE {category} IS NOT NULL AND {value} IS NOT NULL "
                f"AND ({numeric_category} IS NULL OR {numeric_value} IS NULL)"
            ).fetchone()[0]
            result_rows = connection.execute(
                f"""
                SELECT {numeric_category}, {numeric_value}
                FROM source
                WHERE {numeric_category} IS NOT NULL AND {numeric_value} IS NOT NULL
                ORDER BY {numeric_category}, {numeric_value}
                LIMIT ?
                """,
                [result_limit],
            ).fetchall()
            rows = [{"x": _rounded(row[0]), "y": _rounded(row[1])} for row in result_rows]
            formula = f"Une ligne = « {category_column} » en x et « {value_column} » en y"
            result_count = valid_count
        else:
            aggregate_sql = AGGREGATIONS[aggregation][0]
            valid_category = f"{category} IS NOT NULL AND trim(CAST({category} AS VARCHAR)) <> ''"
            result_count = connection.execute(
                f"""
                SELECT count(*) FROM (
                    SELECT CAST({category} AS VARCHAR)
                    FROM source
                    WHERE {valid_category} AND {numeric_value} IS NOT NULL
                    GROUP BY CAST({category} AS VARCHAR)
                ) groups
                """
            ).fetchone()[0]
            rejected_count = connection.execute(
                f"SELECT count(*) FROM source WHERE {valid_category} AND {numeric_value} IS NULL"
            ).fetchone()[0]
            ordering = (
                "abs(aggregated_value) DESC, label"
                if chart_type == "bar"
                else "try_cast(label AS DOUBLE) NULLS LAST, label"
            )
            result_rows = connection.execute(
                f"""
                SELECT CAST({category} AS VARCHAR) AS label,
                       {aggregate_sql}({numeric_value}) AS aggregated_value
                FROM source
                WHERE {valid_category}
                GROUP BY label
                HAVING count({numeric_value}) > 0
                ORDER BY {ordering}
                LIMIT ?
                """,
                [result_limit],
            ).fetchall()
            rows = [{"label": row[0], "value": _rounded(row[1])} for row in result_rows]
            formula = (
                f"{AGGREGATIONS[aggregation][1]} de « {value_column} » "
                f"pour chaque « {category_column} »"
            )

        warnings = []
        if rejected_count:
            warnings.append(
                f"{rejected_count} ligne(s) ont été ignorées car une valeur nécessaire n’est pas numérique."
            )
        if result_count > result_limit:
            warnings.append(
                f"Le calcul contient {result_count} résultats ; cet aperçu en affiche {result_limit}."
            )
        return {
            "chart_type": chart_type,
            "category_column": category_column,
            "value_column": value_column,
            "aggregation": aggregation,
            "formula": formula,
            "result_count": result_count,
            "displayed_count": len(rows),
            "excluded_rows": rejected_count,
            "warnings": warnings,
            "rows": rows,
        }
    finally:
        connection.close()


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

        left_communes = connection.execute(
            "SELECT count(DISTINCT commune_key) FROM left_keys"
        ).fetchone()[0]
        right_communes = connection.execute(
            "SELECT count(DISTINCT commune_key) FROM right_keys"
        ).fetchone()[0]
        matched_communes = connection.execute(
            """
            SELECT count(*) FROM (
                SELECT DISTINCT l.commune_key
                FROM left_keys l INNER JOIN right_keys r USING (commune_key)
            ) common_communes
            """
        ).fetchone()[0]
        geography = {
            "left_communes": left_communes,
            "right_communes": right_communes,
            "matched_communes": matched_communes,
            "left_match_rate": _rate(matched_communes, left_communes),
            "right_match_rate": _rate(matched_communes, right_communes),
        }
        periods = _period_diagnostics(connection) if uses_year else None

        left_rate = _rate(matched, left_distinct)
        right_rate = _rate(matched, right_distinct)
        warnings = []
        if not uses_year:
            warnings.append(
                "Aucune année commune n’est sélectionnée dans les deux sources : "
                "la comparaison porte uniquement sur la commune."
            )
        elif periods and (
            periods["left"]["first"] != periods["right"]["first"]
            or periods["left"]["last"] != periods["right"]["last"]
            or periods["matched_years"] < min(
                periods["left"]["distinct_years"],
                periods["right"]["distinct_years"],
            )
        ):
            warnings.append(
                "Périodes différentes : la source 1 couvre "
                f"{periods['left']['first']}–{periods['left']['last']} et la source 2 "
                f"{periods['right']['first']}–{periods['right']['last']}."
            )
        if matched_communes < left_communes or matched_communes < right_communes:
            warnings.append(
                "Périmètres géographiques différents : "
                f"{matched_communes} commune(s) sont communes aux deux sources, "
                f"sur {left_communes} dans la source 1 et {right_communes} dans la source 2."
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
            "geography": geography,
            "periods": periods,
            "warnings": warnings,
        }
    finally:
        connection.close()


def calculate_indicator(
    left_path: Path,
    right_path: Path,
    left_commune: str,
    right_commune: str,
    left_value: str,
    right_value: str,
    left_aggregation: str,
    right_aggregation: str,
    operation: str,
    left_year: str | None = None,
    right_year: str | None = None,
    result_limit: int = 5000,
) -> dict[str, Any]:
    """Agrège deux mesures puis calcule un indicateur sur les seules clés appariées."""
    if left_aggregation not in AGGREGATIONS or right_aggregation not in AGGREGATIONS:
        raise ValueError("Agrégation non autorisée.")
    if operation not in OPERATIONS:
        raise ValueError("Formule d’indicateur non autorisée.")

    connection = duckdb.connect(":memory:")
    try:
        left = connection.read_csv(str(left_path), header=True, auto_detect=True)
        right = connection.read_csv(str(right_path), header=True, auto_detect=True)
        for columns, commune, year, value in (
            (left.columns, left_commune, left_year, left_value),
            (right.columns, right_commune, right_year, right_value),
        ):
            _require_column(columns, commune)
            _require_column(columns, value)
            if year:
                _require_column(columns, year)

        uses_year = bool(left_year and right_year)
        connection.register("left_source", left)
        connection.register("right_source", right)
        connection.execute(
            f"CREATE TEMP TABLE left_all_keys AS "
            f"{_key_query('left_source', left_commune, left_year if uses_year else None)}"
        )
        connection.execute(
            f"CREATE TEMP TABLE right_all_keys AS "
            f"{_key_query('right_source', right_commune, right_year if uses_year else None)}"
        )
        connection.execute(
            f"CREATE TEMP TABLE left_values AS {_value_query('left_source', left_commune, left_year if uses_year else None, left_value, left_aggregation)}"
        )
        connection.execute(
            f"CREATE TEMP TABLE right_values AS {_value_query('right_source', right_commune, right_year if uses_year else None, right_value, right_aggregation)}"
        )

        dimension_matches = connection.execute(
            """
            SELECT count(*) FROM left_all_keys l
            INNER JOIN right_all_keys r USING (commune_key, year_key)
            """
        ).fetchone()[0]
        value_matches = connection.execute(
            """
            SELECT count(*) FROM left_values l
            INNER JOIN right_values r USING (commune_key, year_key)
            """
        ).fetchone()[0]
        missing_values = dimension_matches - value_matches
        rejected_left = connection.execute(
            "SELECT coalesce(sum(rejected_rows), 0) FROM left_values"
        ).fetchone()[0]
        rejected_right = connection.execute(
            "SELECT coalesce(sum(rejected_rows), 0) FROM right_values"
        ).fetchone()[0]

        value_expression = (
            "(l.aggregated_value / r.aggregated_value) * 100.0"
            if operation == "ratio_percent"
            else "l.aggregated_value - r.aggregated_value"
        )
        denominator_condition = (
            "AND r.aggregated_value <> 0" if operation == "ratio_percent" else ""
        )
        zero_denominators = (
            connection.execute(
                """
                SELECT count(*) FROM left_values l
                INNER JOIN right_values r USING (commune_key, year_key)
                WHERE r.aggregated_value = 0
                """
            ).fetchone()[0]
            if operation == "ratio_percent"
            else 0
        )
        total_rows = value_matches - zero_denominators
        result_rows = connection.execute(
            f"""
            SELECT l.commune_key, nullif(l.year_key, ''),
                   l.aggregated_value, r.aggregated_value,
                   {value_expression} AS indicator_value
            FROM left_values l
            INNER JOIN right_values r USING (commune_key, year_key)
            WHERE l.aggregated_value IS NOT NULL
              AND r.aggregated_value IS NOT NULL
              {denominator_condition}
            ORDER BY abs(indicator_value) DESC, l.commune_key, l.year_key
            LIMIT ?
            """,
            [result_limit],
        ).fetchall()

        warnings = []
        if missing_values:
            warnings.append(
                f"{missing_values} clé(s) appariée(s) ont été exclues car une valeur numérique manque dans au moins une source."
            )
        if rejected_left or rejected_right:
            warnings.append(
                f"{rejected_left + rejected_right} valeur(s) non numériques ont été ignorées pendant l’agrégation."
            )
        if zero_denominators:
            warnings.append(
                f"{zero_denominators} résultat(s) ont été exclus car le dénominateur vaut zéro."
            )
        if total_rows > result_limit:
            warnings.append(
                f"Le projet contient {total_rows} résultats ; les {result_limit} valeurs les plus éloignées de zéro sont conservées dans cet aperçu."
            )

        left_label = AGGREGATIONS[left_aggregation][1]
        right_label = AGGREGATIONS[right_aggregation][1]
        left_term = f"{left_label} de « {left_value} » (source 1)"
        right_term = f"{right_label} de « {right_value} » (source 2)"
        formula = (
            f"({left_term} ÷ {right_term}) × 100"
            if operation == "ratio_percent"
            else f"{left_term} − {right_term}"
        )
        return {
            "operation": operation,
            "operation_label": OPERATIONS[operation],
            "unit": "%" if operation == "ratio_percent" else "écart",
            "formula": formula,
            "dimensions": ["commune", *(["année"] if uses_year else [])],
            "dimension_matches": dimension_matches,
            "result_count": total_rows,
            "displayed_count": len(result_rows),
            "excluded_missing_values": missing_values,
            "excluded_zero_denominator": zero_denominators,
            "warnings": warnings,
            "rows": [
                {
                    "commune": row[0],
                    "année": row[1],
                    "source_1_value": _rounded(row[2]),
                    "source_2_value": _rounded(row[3]),
                    "value": _rounded(row[4]),
                }
                for row in result_rows
            ],
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


def _value_query(
    relation: str,
    commune: str,
    year: str | None,
    value: str,
    aggregation: str,
) -> str:
    commune_identifier = _quote_identifier(commune)
    value_identifier = _quote_identifier(value)
    numeric_value = f"try_cast({value_identifier} AS DOUBLE)"
    aggregate_sql = AGGREGATIONS[aggregation][0]
    commune_key = (
        f"upper(trim(regexp_replace(CAST({commune_identifier} AS VARCHAR), "
        "'\\s+', ' ', 'g')))"
    )
    year_key = "''"
    conditions = [
        f"{commune_identifier} IS NOT NULL",
        f"trim(CAST({commune_identifier} AS VARCHAR)) <> ''",
    ]
    if year:
        year_identifier = _quote_identifier(year)
        year_key = f"trim(CAST({year_identifier} AS VARCHAR))"
        conditions.extend(
            [f"{year_identifier} IS NOT NULL", f"trim(CAST({year_identifier} AS VARCHAR)) <> ''"]
        )
    return f"""
        SELECT {commune_key} AS commune_key, {year_key} AS year_key,
               {aggregate_sql}({numeric_value}) AS aggregated_value,
               count(*) - count({numeric_value}) AS rejected_rows
        FROM {relation}
        WHERE {' AND '.join(conditions)}
        GROUP BY commune_key, year_key
        HAVING count({numeric_value}) > 0
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


def _period_diagnostics(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    left = connection.execute(
        """
        SELECT min(year_key), max(year_key), count(DISTINCT year_key)
        FROM left_keys WHERE year_key <> ''
        """
    ).fetchone()
    right = connection.execute(
        """
        SELECT min(year_key), max(year_key), count(DISTINCT year_key)
        FROM right_keys WHERE year_key <> ''
        """
    ).fetchone()
    matched_years = connection.execute(
        """
        SELECT count(*) FROM (
            SELECT DISTINCT l.year_key
            FROM left_keys l INNER JOIN right_keys r USING (year_key)
            WHERE l.year_key <> ''
        ) common_years
        """
    ).fetchone()[0]
    return {
        "left": {"first": left[0], "last": left[1], "distinct_years": left[2]},
        "right": {"first": right[0], "last": right[1], "distinct_years": right[2]},
        "matched_years": matched_years,
    }


def _rate(matched: int, total: int) -> float:
    return round((matched / total * 100) if total else 0, 1)


def _rounded(value: float) -> float:
    return round(float(value), 6)


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

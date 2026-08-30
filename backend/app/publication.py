import hashlib
import json
from typing import Any


CALCULATION_VERSION = "1"


def build_publication_snapshot(
    project: dict[str, Any],
    version_number: int,
    published_at: str,
    author_name: str,
    title: str,
    summary: str,
    interpretation: str,
    limitations: str,
) -> dict[str, Any]:
    """Crée le contenu immuable et reproductible d’une version publiée."""
    if not project.get("indicator"):
        raise ValueError("Calculez un indicateur avant de publier une fiche.")
    sources = [
        {
            "position": source["position"],
            "dataset_id": source["id"],
            "title": source["title"],
            "publisher": source.get("publisher"),
            "catalog_source": source.get("catalog_source"),
            "catalog_dataset_id": source.get("catalog_dataset_id"),
            "catalog_resource_id": source.get("catalog_resource_id"),
            "source_url": source.get("source_url"),
            "source_format": source.get("source_format"),
            "source_sheet": source.get("source_sheet"),
            "sha256": source["sha256"],
            "size_bytes": source["size_bytes"],
            "row_count": source["row_count"],
            "columns": source["columns"],
            "dimensions": source["dimensions"],
        }
        for source in project["sources"]
    ]
    return {
        "schema_version": 1,
        "calculation_version": CALCULATION_VERSION,
        "project_id": project["id"],
        "project_title": project["title"],
        "version_number": version_number,
        "published_at": published_at,
        "author_name": author_name,
        "title": title,
        "summary": summary,
        "interpretation": interpretation,
        "limitations": limitations,
        "sources": sources,
        "join_analysis": project["join_analysis"],
        "indicator": project["indicator"],
        "reproducibility": {
            "engine": "DuckDB",
            "key_normalization": (
                "Conversion textuelle, suppression des espaces en bordure, "
                "réduction des espaces consécutifs et comparaison sans distinction de casse."
            ),
            "missing_data_policy": (
                "Aucune valeur n’est inventée. Les valeurs absentes ou non numériques "
                "et les divisions par zéro sont exclues et comptabilisées."
            ),
            "source_hashes": [source["sha256"] for source in sources],
        },
    }


def snapshot_sha256(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

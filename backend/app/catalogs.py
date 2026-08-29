import asyncio
import html
import re
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx


CatalogSearch = Callable[[httpx.AsyncClient, str, int], Awaitable[list[dict[str, Any]]]]


async def search_catalogs(query: str, limit: int = 6) -> dict[str, Any]:
    catalogs: list[tuple[str, CatalogSearch]] = [
        ("data.gouv.fr", search_data_gouv),
        ("data.europa.eu", search_data_europa),
        ("Recherche Data Gouv", search_recherche_data_gouv),
    ]
    timeout = httpx.Timeout(10, connect=5)
    headers = {"User-Agent": "public-data-explorer/0.1"}
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        responses = await asyncio.gather(
            *(search(client, query, limit) for _, search in catalogs),
            return_exceptions=True,
        )

    results: list[dict[str, Any]] = []
    sources = []
    for (name, _), response in zip(catalogs, responses, strict=True):
        if isinstance(response, BaseException):
            sources.append({"name": name, "status": "unavailable", "count": 0})
            continue
        results.extend(response)
        sources.append({"name": name, "status": "ok", "count": len(response)})

    results.sort(
        key=lambda item: (bool(item.get("can_explore")), bool(item.get("can_check"))),
        reverse=True,
    )
    return {
        "query": query,
        "total": len(results),
        "usable_total": sum(bool(item.get("can_explore")) for item in results),
        "sources": sources,
        "results": results,
    }


async def search_data_gouv(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    response = await client.get(
        "https://www.data.gouv.fr/api/1/datasets/",
        params={"q": query, "page_size": limit, "sort": "-last_update"},
    )
    response.raise_for_status()
    return [_data_gouv_result(item) for item in response.json().get("data", [])]


async def search_data_europa(client: httpx.AsyncClient, query: str, limit: int) -> list[dict[str, Any]]:
    response = await client.post(
        "https://data.europa.eu/api/hub/search/search",
        json={"q": query, "filters": ["dataset"], "page": 0, "limit": limit},
    )
    response.raise_for_status()
    datasets = response.json().get("result", {}).get("results", [])[:limit]
    return [
        {
            "id": str(item.get("id") or _localized(item.get("identifier"))),
            "source": "data.europa.eu",
            "title": _localized(item.get("title")) or "Jeu de données sans titre",
            "description": _plain_text(_localized(item.get("description"))),
            "publisher": (item.get("publisher") or {}).get("name") or "Producteur non précisé",
            "updated_at": item.get("modified") or item.get("issued"),
            "formats": _formats_from_europa(item),
            "license": None,
            "url": item.get("resource"),
            "resources": [_europa_resource(resource) for resource in item.get("distributions", [])[:12]],
            "can_explore": any(
                resource["can_explore"]
                for resource in map(_europa_resource, item.get("distributions", []))
            ),
        }
        for item in datasets
    ]


async def search_recherche_data_gouv(
    client: httpx.AsyncClient, query: str, limit: int
) -> list[dict[str, Any]]:
    response = await client.get(
        "https://entrepot.recherche.data.gouv.fr/api/search",
        params={"q": query, "type": "dataset", "per_page": limit},
    )
    response.raise_for_status()
    datasets = response.json().get("data", {}).get("items", [])
    return list(
        await asyncio.gather(
            *(_research_data_gouv_result(client, item) for item in datasets)
        )
    )


async def _research_data_gouv_result(
    client: httpx.AsyncClient,
    item: dict[str, Any],
) -> dict[str, Any]:
    persistent_id = str(item.get("global_id") or item.get("url"))
    resources: list[dict[str, Any]] = []
    metadata_checked = False
    if item.get("fileCount") and persistent_id.lower().startswith("doi:"):
        try:
            response = await client.get(
                "https://entrepot.recherche.data.gouv.fr/api/datasets/:persistentId/",
                params={"persistentId": persistent_id},
            )
            if response.is_success:
                metadata_checked = True
                resources = _research_data_gouv_resources(response.json())
        except httpx.HTTPError:
            pass

    return {
        "id": persistent_id,
        "source": "Recherche Data Gouv",
        "title": item.get("name") or "Jeu de données sans titre",
        "description": _plain_text(item.get("description")),
        "publisher": item.get("publisher") or "Producteur non précisé",
        "updated_at": item.get("updatedAt") or item.get("published_at"),
        "formats": sorted({resource["format"] for resource in resources})
        or (["Fichiers à vérifier"] if item.get("fileCount") and not metadata_checked else ["Aucune table"]),
        "license": None,
        "url": item.get("url"),
        "resources": resources,
        "can_explore": bool(resources),
        "can_check": bool(item.get("fileCount")) and not metadata_checked,
    }


def _data_gouv_result(item: dict[str, Any]) -> dict[str, Any]:
    resources = [_data_gouv_resource(resource) for resource in item.get("resources", [])[:20]]
    return {
        "id": item["id"],
        "source": "data.gouv.fr",
        "title": item.get("title") or "Jeu de données sans titre",
        "description": _plain_text(item.get("description")),
        "publisher": (item.get("organization") or {}).get("name")
        or (item.get("owner") or {}).get("first_name")
        or "Producteur non précisé",
        "updated_at": item.get("last_update") or item.get("last_modified"),
        "formats": sorted({resource["format"] for resource in resources if resource["format"]})[:8],
        "license": item.get("license"),
        "url": item.get("page"),
        "resources": resources,
        "can_explore": any(resource["can_explore"] for resource in resources),
    }


def _data_gouv_resource(resource: dict[str, Any]) -> dict[str, Any]:
    resource_format = str(resource.get("format") or "").upper()
    return {
        "id": resource.get("id"),
        "title": resource.get("title") or resource.get("filename") or "Ressource",
        "format": resource_format,
        "url": resource.get("url"),
        "size": resource.get("filesize"),
        "can_explore": (
            resource_format == "CSV"
            and bool(resource.get("url"))
            and (resource.get("extras") or {}).get("check:available") is not False
        ),
    }


def _europa_resource(resource: dict[str, Any]) -> dict[str, Any]:
    value = resource.get("format")
    if isinstance(value, dict):
        value = value.get("label") or value.get("id")
    resource_urls = resource.get("download_url") or resource.get("access_url") or []
    if isinstance(resource_urls, str):
        resource_urls = [resource_urls]
    resource_format = str(value or "").upper()
    return {
        "id": resource.get("id"),
        "title": _localized(resource.get("title")) or "Ressource",
        "format": resource_format,
        "url": resource_urls[0] if resource_urls else None,
        "size": resource.get("byte_size"),
        "can_explore": (
            resource_format in {"CSV", "TSV", "TAB"}
            and bool(resource_urls)
            and not _is_data_europa_landing_page(resource_urls[0])
        ),
    }


def _research_data_gouv_resources(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    files = (metadata.get("data") or {}).get("latestVersion", {}).get("files", [])
    for file_entry in files:
        if file_entry.get("restricted") is True:
            continue
        data_file = file_entry.get("dataFile") or {}
        filename = str(data_file.get("filename") or "")
        content_type = str(data_file.get("contentType") or "").lower()
        if content_type == "text/csv" or filename.lower().endswith(".csv"):
            resource_format = "CSV"
        elif content_type == "text/tab-separated-values" or filename.lower().endswith((".tsv", ".tab")):
            resource_format = "TSV"
        else:
            continue
        resources.append(
            {
                "id": str(data_file.get("id")),
                "title": filename or "Table de recherche",
                "format": resource_format,
                "url": None,
                "size": data_file.get("filesize"),
                "can_explore": True,
            }
        )
    return resources


def _is_data_europa_landing_page(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in {"data.europa.eu", "www.data.europa.eu"} and "/dataset/" in parsed.path


def _localized(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return str(value[0]) if value else ""
    if not isinstance(value, dict) or not value:
        return ""
    return str(value.get("fr") or value.get("en") or next(iter(value.values()), ""))


def _formats_from_europa(dataset: dict[str, Any]) -> list[str]:
    return sorted(
        {resource["format"] for resource in map(_europa_resource, dataset.get("distributions", [])) if resource["format"]}
    )[:8]


def _plain_text(value: Any, limit: int = 360) -> str:
    if not value:
        return "Aucune description fournie."
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = re.sub(r"[#*_`>\[\]]", "", text)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text if len(text) <= limit else f"{text[:limit].rstrip()}…"

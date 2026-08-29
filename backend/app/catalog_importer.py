from contextlib import closing
import ipaddress
import socket
from tempfile import SpooledTemporaryFile
from urllib.parse import urljoin, urlparse

import httpx

from .service import CsvUploadService, UploadTooLargeError


class CatalogResourceError(ValueError):
    pass


def import_data_gouv_resource(
    dataset_id: str,
    resource_id: str,
    service: CsvUploadService,
) -> dict:
    timeout = httpx.Timeout(20, connect=5)
    headers = {"User-Agent": "public-data-explorer/0.1"}
    with httpx.Client(timeout=timeout, headers=headers) as client:
        resources = _get_data_gouv_resources(client, dataset_id)
        resource = next((item for item in resources if item.get("id") == resource_id), None)
        if resource is None:
            raise CatalogResourceError("Cette ressource n’existe plus dans le catalogue.")
        result = _download_and_import(client, dataset_id, resource, service)

    return result


def import_best_data_gouv_resource(dataset_id: str, service: CsvUploadService) -> dict:
    """Choisit automatiquement la ressource CSV la plus pertinente et disponible."""
    timeout = httpx.Timeout(30, connect=5)
    headers = {"User-Agent": "public-data-explorer/0.1"}
    with httpx.Client(timeout=timeout, headers=headers) as client:
        resources = _get_data_gouv_resources(client, dataset_id)
        resource = _select_best_data_gouv_resource(resources)
        return _download_and_import(client, dataset_id, resource, service)


def _select_best_data_gouv_resource(resources: list[dict]) -> dict:
    candidates = [
        resource
        for resource in resources
        if str(resource.get("format") or "").upper() == "CSV"
        and resource.get("url")
        and (resource.get("extras") or {}).get("check:available") is not False
    ]
    if not candidates:
        raise CatalogResourceError("Aucune ressource tabulaire disponible n’a été trouvée pour ce jeu de données.")
    candidates.sort(
        key=lambda resource: (
            resource.get("type") == "main",
            resource.get("last_modified") or resource.get("created_at") or "",
        ),
        reverse=True,
    )
    return candidates[0]


def _get_data_gouv_resources(client: httpx.Client, dataset_id: str) -> list[dict]:
    metadata = client.get(f"https://www.data.gouv.fr/api/1/datasets/{dataset_id}/")
    metadata.raise_for_status()
    return metadata.json().get("resources", [])


def _download_and_import(
    client: httpx.Client,
    dataset_id: str,
    resource: dict,
    service: CsvUploadService,
) -> dict:
    resource_id = resource.get("id")
    if str(resource.get("format") or "").upper() != "CSV":
        raise CatalogResourceError("Aucune donnée tabulaire directement exploitable n’a été trouvée.")
    source_url = resource.get("url")
    if not source_url:
        raise CatalogResourceError("La plateforme ne fournit pas d’adresse de téléchargement.")

    with closing(_open_safe_stream(client, source_url)) as response:
        response.raise_for_status()
        declared_size = int(response.headers.get("content-length") or 0)
        if declared_size > service.max_upload_bytes:
            limit_mb = service.max_upload_bytes // (1024 * 1024)
            raise UploadTooLargeError(
                f"Ce jeu de données dépasse encore la capacité du prototype ({limit_mb} Mo)."
            )

        with SpooledTemporaryFile(max_size=8 * 1024 * 1024) as temporary:
            downloaded = 0
            for chunk in response.iter_bytes(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > service.max_upload_bytes:
                    limit_mb = service.max_upload_bytes // (1024 * 1024)
                    raise UploadTooLargeError(
                        f"Ce jeu de données dépasse encore la capacité du prototype ({limit_mb} Mo)."
                    )
                temporary.write(chunk)
            temporary.seek(0)
            name = resource.get("filename") or resource.get("title") or f"{resource_id}.csv"
            if not str(name).lower().endswith(".csv"):
                name = f"{name}.csv"
            result = service.import_csv(str(name), temporary)

    result["catalog_source"] = "data.gouv.fr"
    result["catalog_dataset_id"] = dataset_id
    result["catalog_resource_id"] = resource_id
    result["source_url"] = source_url
    return result


def _open_safe_stream(client: httpx.Client, initial_url: str) -> httpx.Response:
    current_url = initial_url
    for _ in range(6):
        _validate_public_url(current_url)
        request = client.build_request("GET", current_url)
        response = client.send(request, stream=True, follow_redirects=False)
        if response.is_redirect:
            location = response.headers.get("location")
            response.close()
            if not location:
                raise CatalogResourceError("Redirection de téléchargement invalide.")
            current_url = urljoin(current_url, location)
            continue
        return response
    raise CatalogResourceError("Trop de redirections pendant le téléchargement.")


def _validate_public_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CatalogResourceError("Adresse de téléchargement invalide.")
    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or default_port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise CatalogResourceError("Le serveur de téléchargement est introuvable.") from error
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise CatalogResourceError("Cette adresse de téléchargement n’est pas publique.")

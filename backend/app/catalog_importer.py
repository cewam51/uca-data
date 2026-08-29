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
        metadata = client.get(f"https://www.data.gouv.fr/api/1/datasets/{dataset_id}/")
        metadata.raise_for_status()
        resources = metadata.json().get("resources", [])
        resource = next((item for item in resources if item.get("id") == resource_id), None)
        if resource is None:
            raise CatalogResourceError("Cette ressource n’existe plus dans le catalogue.")
        if str(resource.get("format") or "").upper() != "CSV":
            raise CatalogResourceError("Seules les ressources CSV peuvent être explorées pour le moment.")
        source_url = resource.get("url")
        if not source_url:
            raise CatalogResourceError("Cette ressource ne possède pas d’adresse de téléchargement.")

        with closing(_open_safe_stream(client, source_url)) as response:
            response.raise_for_status()
            declared_size = int(response.headers.get("content-length") or 0)
            if declared_size > service.max_upload_bytes:
                raise UploadTooLargeError("Cette ressource dépasse la taille maximale autorisée.")

            with SpooledTemporaryFile(max_size=8 * 1024 * 1024) as temporary:
                downloaded = 0
                for chunk in response.iter_bytes(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > service.max_upload_bytes:
                        raise UploadTooLargeError("Cette ressource dépasse la taille maximale autorisée.")
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

from contextlib import closing
import ipaddress
from pathlib import Path
import re
import socket
from tempfile import SpooledTemporaryFile
from urllib.parse import quote, urlencode, urljoin, urlparse
from zipfile import BadZipFile, ZipFile

import httpx

from .service import CsvUploadService, UploadTooLargeError


class CatalogResourceError(ValueError):
    pass


TABULAR_FORMATS = {"CSV", "TSV", "TAB"}


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
        return _download_and_import(client, dataset_id, resource, service, "data.gouv.fr")


def import_best_data_europa_resource(dataset_id: str, service: CsvUploadService) -> dict:
    """Récupère les distributions exactes d’un jeu data.europa.eu et ouvre la meilleure table."""
    timeout = httpx.Timeout(30, connect=5)
    headers = {"User-Agent": "public-data-explorer/0.1"}
    with httpx.Client(timeout=timeout, headers=headers) as client:
        response = client.get(
            f"https://data.europa.eu/api/hub/search/datasets/{quote(dataset_id, safe='')}"
        )
        response.raise_for_status()
        dataset = response.json().get("result") or {}
        resources = _data_europa_tabular_resources(dataset.get("distributions", []))
        return _import_first_available(client, dataset_id, resources, service, "data.europa.eu")


def import_best_research_data_gouv_resource(
    persistent_id: str,
    service: CsvUploadService,
) -> dict:
    """Résout un DOI Recherche Data Gouv puis ouvre sa meilleure table publique."""
    if not re.fullmatch(r"doi:[^\s/]+/.+", persistent_id, flags=re.IGNORECASE):
        raise CatalogResourceError("Identifiant Recherche Data Gouv invalide.")

    timeout = httpx.Timeout(30, connect=5)
    headers = {"User-Agent": "public-data-explorer/0.1"}
    with httpx.Client(timeout=timeout, headers=headers) as client:
        metadata, base_url = _get_research_data_gouv_metadata(client, persistent_id)
        resources = _research_data_gouv_tabular_resources(metadata, base_url)
        return _import_first_available(
            client,
            persistent_id,
            resources,
            service,
            "Recherche Data Gouv",
        )


def import_best_insee_resource(dataset_id: str, service: CsvUploadService) -> dict:
    """Récupère le CSV français exact d'un jeu du catalogue officiel Melodi."""
    if not re.fullmatch(r"[A-Z0-9_-]{2,160}", dataset_id):
        raise CatalogResourceError("Identifiant de jeu de données Insee invalide.")
    timeout = httpx.Timeout(45, connect=5)
    headers = {"User-Agent": "public-data-explorer/0.1"}
    with httpx.Client(timeout=timeout, headers=headers) as client:
        response = client.get(
            f"https://api.insee.fr/melodi/catalog/{quote(dataset_id, safe='')}"
        )
        response.raise_for_status()
        products = response.json().get("product") or []
        candidates = [
            product for product in products
            if str(product.get("format") or "").upper() == "CSV"
            and str(product.get("language") or "").upper() == "FR"
            and product.get("accessURL")
        ]
        if not candidates:
            raise CatalogResourceError(
                "Ce jeu Insee ne contient pas de table CSV française directement utilisable."
            )
        candidates.sort(
            key=lambda product: product.get("modified") or product.get("issued") or "",
            reverse=True,
        )
        product = candidates[0]
        resource = {
            "id": product.get("id"),
            "title": product.get("title") or dataset_id,
            "url": product.get("accessURL"),
            "size": product.get("byteSize"),
        }
        return _download_and_import_insee_archive(
            client, dataset_id, resource, service
        )


def _download_and_import_insee_archive(
    client: httpx.Client,
    dataset_id: str,
    resource: dict,
    service: CsvUploadService,
) -> dict:
    source_url = resource.get("url")
    if not source_url:
        raise CatalogResourceError("L’Insee ne fournit pas d’adresse de téléchargement.")
    with closing(_open_safe_stream(client, source_url)) as response:
        response.raise_for_status()
        declared_size = int(response.headers.get("content-length") or 0)
        if declared_size > service.max_upload_bytes:
            limit_mb = service.max_upload_bytes // (1024 * 1024)
            raise UploadTooLargeError(
                f"Ce jeu de données dépasse encore la capacité du prototype ({limit_mb} Mo)."
            )
        with SpooledTemporaryFile(max_size=8 * 1024 * 1024) as archive_file:
            downloaded = 0
            for chunk in response.iter_bytes(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > service.max_upload_bytes:
                    raise UploadTooLargeError("L’archive Insee dépasse la taille maximale autorisée.")
                archive_file.write(chunk)
            archive_file.seek(0)
            result = _import_insee_archive(archive_file, service)

    result["catalog_source"] = "Insee"
    result["catalog_dataset_id"] = dataset_id
    result["catalog_resource_id"] = resource.get("id")
    result["source_url"] = source_url
    service.attach_provenance(result)
    return result


def _import_insee_archive(archive_file, service: CsvUploadService) -> dict:
    try:
        with ZipFile(archive_file) as archive:
            csv_entries = [
                entry for entry in archive.infolist()
                if not entry.is_dir()
                and entry.filename.lower().endswith(".csv")
                and "metadata" not in entry.filename.lower()
            ]
            preferred = [entry for entry in csv_entries if entry.filename.lower().endswith("_data.csv")]
            entry = (preferred or csv_entries)[0] if (preferred or csv_entries) else None
            if entry is None:
                raise CatalogResourceError("L’archive Insee ne contient pas de table de données CSV.")
            if entry.file_size > service.max_upload_bytes:
                limit_mb = service.max_upload_bytes // (1024 * 1024)
                raise UploadTooLargeError(
                    f"La table Insee décompressée dépasse la capacité du prototype ({limit_mb} Mo)."
                )
            with archive.open(entry) as source, SpooledTemporaryFile(max_size=8 * 1024 * 1024) as table:
                copied = 0
                while chunk := source.read(1024 * 1024):
                    copied += len(chunk)
                    if copied > service.max_upload_bytes:
                        raise UploadTooLargeError("La table Insee dépasse la taille maximale autorisée.")
                    table.write(chunk)
                table.seek(0)
                return service.import_tabular(Path(entry.filename).name, table)
    except BadZipFile as error:
        raise CatalogResourceError("L’archive fournie par l’Insee n’est pas lisible.") from error


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


def _data_europa_tabular_resources(distributions: list[dict]) -> list[dict]:
    resources: list[dict] = []
    for distribution in distributions:
        resource_format = _catalog_format(distribution.get("format"))
        if resource_format not in TABULAR_FORMATS:
            continue
        urls = _url_list(distribution.get("download_url")) + _url_list(
            distribution.get("access_url")
        )
        seen: set[str] = set()
        for source_url in urls:
            if source_url in seen or _is_data_europa_landing_page(source_url):
                continue
            seen.add(source_url)
            resources.append(
                {
                    "id": distribution.get("id"),
                    "title": _localized_title(distribution.get("title")) or f"donnees.{_extension(resource_format)}",
                    "format": resource_format,
                    "url": source_url,
                    "size": distribution.get("byte_size"),
                }
            )
    if not resources:
        raise CatalogResourceError(
            "Ce jeu de données ne contient pas de table CSV ou TSV directement utilisable."
        )
    return resources


def _research_data_gouv_tabular_resources(metadata: dict, base_url: str) -> list[dict]:
    resources: list[dict] = []
    files = (metadata.get("data") or {}).get("latestVersion", {}).get("files", [])
    for file_entry in files:
        if file_entry.get("restricted") is True:
            continue
        data_file = file_entry.get("dataFile") or {}
        filename = str(data_file.get("filename") or "")
        content_type = str(data_file.get("contentType") or "").lower()
        suffix = Path(filename).suffix.lower()
        if content_type == "text/csv" or suffix == ".csv":
            resource_format = "CSV"
        elif content_type == "text/tab-separated-values" or suffix in {".tsv", ".tab"}:
            resource_format = "TSV"
        else:
            continue
        file_id = data_file.get("id")
        if file_id is None:
            continue
        resources.append(
            {
                "id": str(file_id),
                "title": filename or f"donnees.{_extension(resource_format)}",
                "format": resource_format,
                "url": urljoin(base_url, f"/api/access/datafile/{file_id}"),
                "size": data_file.get("filesize"),
            }
        )
    if not resources:
        raise CatalogResourceError(
            "Ce jeu de recherche ne contient aucune table publique CSV ou TSV utilisable."
        )
    resources.sort(
        key=lambda item: (
            item["format"] != "CSV",
            item.get("size") if item.get("size") is not None else float("inf"),
        )
    )
    return resources


def _get_data_gouv_resources(client: httpx.Client, dataset_id: str) -> list[dict]:
    metadata = client.get(f"https://www.data.gouv.fr/api/1/datasets/{dataset_id}/")
    metadata.raise_for_status()
    return metadata.json().get("resources", [])


def _get_research_data_gouv_metadata(
    client: httpx.Client,
    persistent_id: str,
) -> tuple[dict, str]:
    central_base = "https://entrepot.recherche.data.gouv.fr"
    central = client.get(
        f"{central_base}/api/datasets/:persistentId/",
        params={"persistentId": persistent_id},
    )
    if central.is_success:
        return central.json(), central_base
    if central.status_code not in {401, 404}:
        central.raise_for_status()

    doi_url = f"https://doi.org/{quote(persistent_id.split(':', 1)[1], safe='/')}"
    with closing(_open_safe_stream(client, doi_url)) as landing:
        landing.raise_for_status()
        parsed = urlparse(str(landing.url))
        base_url = f"{parsed.scheme}://{parsed.netloc}"

    metadata_url = (
        f"{base_url}/api/datasets/:persistentId/?"
        f"{urlencode({'persistentId': persistent_id})}"
    )
    metadata = _read_safe_json(client, metadata_url)
    return metadata, base_url


def _read_safe_json(client: httpx.Client, url: str) -> dict:
    with closing(_open_safe_stream(client, url)) as response:
        response.raise_for_status()
        response.read()
        return response.json()


def _import_first_available(
    client: httpx.Client,
    dataset_id: str,
    resources: list[dict],
    service: CsvUploadService,
    catalog_source: str,
) -> dict:
    last_error: Exception | None = None
    for resource in resources:
        try:
            return _download_and_import(
                client,
                dataset_id,
                resource,
                service,
                catalog_source,
            )
        except (CatalogResourceError, httpx.HTTPError) as error:
            last_error = error
    if isinstance(last_error, CatalogResourceError):
        raise last_error
    raise CatalogResourceError(
        "Les tables annoncées par la plateforme ne sont pas téléchargeables actuellement."
    ) from last_error


def _download_and_import(
    client: httpx.Client,
    dataset_id: str,
    resource: dict,
    service: CsvUploadService,
    catalog_source: str = "data.gouv.fr",
) -> dict:
    resource_id = resource.get("id")
    resource_format = str(resource.get("format") or "").upper()
    if resource_format not in TABULAR_FORMATS:
        raise CatalogResourceError("Aucune donnée tabulaire directement exploitable n’a été trouvée.")
    source_url = resource.get("url")
    if not source_url:
        raise CatalogResourceError("La plateforme ne fournit pas d’adresse de téléchargement.")

    with closing(_open_safe_stream(client, source_url)) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type or "application/xhtml" in content_type:
            raise CatalogResourceError(
                "La plateforme annonce une table mais renvoie seulement une page de présentation."
            )
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
            name = resource.get("filename") or resource.get("title") or f"{resource_id}"
            if Path(str(name)).suffix.lower() not in {".csv", ".tsv", ".tab"}:
                name = f"{name}.{_extension(resource_format)}"
            try:
                result = service.import_tabular(str(name), temporary)
            except UploadTooLargeError:
                raise
            except ValueError as error:
                raise CatalogResourceError(
                    "La table fournie par la plateforme n’a pas pu être lue correctement."
                ) from error

    result["catalog_source"] = catalog_source
    result["catalog_dataset_id"] = dataset_id
    result["catalog_resource_id"] = resource_id
    result["source_url"] = source_url
    service.attach_provenance(result)
    return result


def _catalog_format(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("id") or value.get("label")
    normalized = str(value or "").upper().replace("TEXT/", "")
    return "TSV" if normalized in {"TAB", "TSV", "TAB-SEPARATED-VALUES"} else normalized


def _localized_title(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or not value:
        return ""
    return str(value.get("fr") or value.get("en") or next(iter(value.values()), ""))


def _url_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def _extension(resource_format: str) -> str:
    return "tsv" if resource_format in {"TSV", "TAB"} else "csv"


def _is_data_europa_landing_page(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in {"data.europa.eu", "www.data.europa.eu"} and "/dataset/" in parsed.path


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

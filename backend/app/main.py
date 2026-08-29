from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .catalog_importer import (
    CatalogResourceError,
    import_best_data_europa_resource,
    import_best_data_gouv_resource,
    import_best_research_data_gouv_resource,
    import_data_gouv_resource,
)
from .catalogs import search_catalogs
from .config import settings
from .repository import PostgresDatasetRepository
from .service import CsvUploadService, UploadTooLargeError


repository = PostgresDatasetRepository(settings.database_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    repository.initialize()
    yield


app = FastAPI(title="Explorateur de données publiques", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def get_service() -> CsvUploadService:
    return CsvUploadService(settings.upload_dir, settings.max_upload_bytes, repository)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/search")
async def search_datasets(
    q: str = Query(min_length=2, max_length=160),
    limit: int = Query(default=6, ge=1, le=12),
) -> dict:
    return await search_catalogs(q.strip(), limit)


@app.post("/api/catalogs/data-gouv/{dataset_id}/resources/{resource_id}/explore", status_code=201)
def explore_data_gouv_resource(
    dataset_id: str,
    resource_id: str,
    service: CsvUploadService = Depends(get_service),
) -> dict:
    try:
        return import_data_gouv_resource(dataset_id, resource_id, service)
    except UploadTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except CatalogResourceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="La plateforme source ne répond pas correctement.") from error
    except Exception as error:
        raise HTTPException(status_code=422, detail="Cette ressource n’a pas pu être analysée.") from error


@app.post("/api/catalogs/data-gouv/{dataset_id}/explore", status_code=201)
def explore_best_data_gouv_resource(
    dataset_id: str,
    service: CsvUploadService = Depends(get_service),
) -> dict:
    try:
        return import_best_data_gouv_resource(dataset_id, service)
    except UploadTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except CatalogResourceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="La plateforme source ne répond pas correctement.") from error
    except Exception as error:
        raise HTTPException(status_code=422, detail="Ces données n’ont pas pu être analysées.") from error


@app.post("/api/catalogs/data-europa/explore", status_code=201)
def explore_best_data_europa_resource(
    dataset_id: str = Query(min_length=1, max_length=500),
    service: CsvUploadService = Depends(get_service),
) -> dict:
    try:
        return import_best_data_europa_resource(dataset_id, service)
    except UploadTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except CatalogResourceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="La plateforme source ne répond pas correctement.") from error
    except Exception as error:
        raise HTTPException(status_code=422, detail="Ces données n’ont pas pu être analysées.") from error


@app.post("/api/catalogs/recherche-data-gouv/explore", status_code=201)
def explore_best_research_data_gouv_resource(
    persistent_id: str = Query(min_length=5, max_length=500),
    service: CsvUploadService = Depends(get_service),
) -> dict:
    try:
        return import_best_research_data_gouv_resource(persistent_id, service)
    except UploadTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except CatalogResourceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="La plateforme source ne répond pas correctement.") from error
    except Exception as error:
        raise HTTPException(status_code=422, detail="Ces données n’ont pas pu être analysées.") from error

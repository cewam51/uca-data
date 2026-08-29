from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .repository import PostgresDatasetRepository
from .service import CsvUploadService, UploadTooLargeError


repository = PostgresDatasetRepository(settings.database_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    repository.initialize()
    yield


app = FastAPI(title="UCA Data API", version="0.1.0", lifespan=lifespan)
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


@app.post("/api/datasets", status_code=201)
def upload_dataset(
    file: UploadFile = File(...),
    service: CsvUploadService = Depends(get_service),
) -> dict:
    try:
        return service.import_csv(file.filename or "dataset.csv", file.file)
    except UploadTooLargeError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=422, detail="Le CSV n’a pas pu être analysé.") from error

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://uca:uca@localhost:5432/uca",
    )
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "uploads"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))


settings = Settings()

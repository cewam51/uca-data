from typing import Any
from uuid import UUID

from .repository import PostgresDatasetRepository


class PublicationService:
    def __init__(self, repository: PostgresDatasetRepository):
        self.repository = repository

    def publish(
        self,
        project_id: UUID,
        author_name: str,
        title: str,
        summary: str,
        interpretation: str,
        limitations: str,
    ) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        if not project.get("join_analysis"):
            raise ValueError("Vérifiez le croisement avant de publier.")
        indicator = project.get("indicator")
        if not indicator or indicator.get("result_count", 0) == 0:
            raise ValueError("Calculez un indicateur contenant des résultats avant de publier.")
        return self.repository.create_version(
            project_id,
            project,
            author_name,
            title,
            summary,
            interpretation,
            limitations,
        )

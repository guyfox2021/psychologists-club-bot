from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document
from app.database.repositories import DocumentRepository


class VerificationService:
    """Handles document uploads that back a verification application."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = DocumentRepository(session)

    async def add_document(
        self,
        application_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str,
        mime_type: str | None,
    ) -> Document:
        return await self._repo.add(
            application_id, telegram_file_id, telegram_file_unique_id, mime_type
        )

    async def list_documents(self, application_id: int) -> list[Document]:
        return await self._repo.list_by_application(application_id)

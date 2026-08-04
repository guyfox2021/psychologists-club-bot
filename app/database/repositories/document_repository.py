from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        application_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str,
        mime_type: str | None = None,
    ) -> Document:
        document = Document(
            application_id=application_id,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
            mime_type=mime_type,
        )
        self._session.add(document)
        await self._session.flush()
        return document

    async def list_by_application(self, application_id: int) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .where(Document.application_id == application_id)
            .order_by(Document.uploaded_at.asc())
        )
        return list(result.scalars().all())

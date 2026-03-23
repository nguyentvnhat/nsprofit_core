"""Persistence for upload batches."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.upload import Upload


class UploadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, filename: str, file_hash: str | None = None) -> Upload:
        row = Upload(filename=filename, file_hash=file_hash, status="pending")
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, upload_id: int) -> Upload | None:
        return self._session.get(Upload, upload_id)

    def update_status(
        self,
        upload: Upload,
        status: str,
        *,
        row_count: int | None = None,
        error_message: str | None = None,
    ) -> Upload:
        upload.status = status
        if row_count is not None:
            upload.row_count = row_count
        if error_message is not None:
            upload.error_message = error_message
        self._session.flush()
        return upload

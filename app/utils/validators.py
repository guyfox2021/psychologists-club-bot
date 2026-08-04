ALLOWED_DOCUMENT_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def is_allowed_document_mime_type(mime_type: str | None) -> bool:
    return mime_type in ALLOWED_DOCUMENT_MIME_TYPES


def is_allowed_document_size(file_size: int | None) -> bool:
    return file_size is not None and file_size <= MAX_DOCUMENT_SIZE_BYTES

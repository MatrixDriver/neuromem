"""Tests for file upload and management."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from neuromemory.services.files import FileService


@pytest.fixture
def mock_storage():
    """Mock object storage."""
    storage = MagicMock()
    storage.upload = AsyncMock(
        side_effect=lambda prefix, fn, data, ct="": f"{prefix}/{uuid.uuid4()}/{fn}"
    )
    storage.download = AsyncMock(return_value=b"file content")
    storage.get_presigned_url = AsyncMock(return_value="http://minio:9000/presigned-url")
    storage.delete = AsyncMock()
    storage.init = AsyncMock()
    return storage


@pytest.mark.asyncio
async def test_upload_text_file(db_session, mock_embedding, mock_storage):
    svc = FileService(db_session, mock_embedding, mock_storage)
    doc = await svc.upload(
        user_id="u1",
        filename="hello.txt",
        file_data=b"Hello world content",
        category="notes",
    )
    assert doc.filename == "hello.txt"
    assert doc.file_type == "txt"
    assert doc.category == "notes"
    assert doc.file_size == len(b"Hello world content")
    assert doc.extracted_text is not None
    mock_storage.upload.assert_called_once()


@pytest.mark.asyncio
async def test_upload_image_file(db_session, mock_embedding, mock_storage):
    svc = FileService(db_session, mock_embedding, mock_storage)
    doc = await svc.upload(
        user_id="u1",
        filename="photo.png",
        file_data=b"\x89PNG\r\n\x1a\n",
    )
    assert doc.filename == "photo.png"
    assert doc.file_type == "png"
    assert doc.extracted_text is None
    assert doc.embedding_id is None


@pytest.mark.asyncio
async def test_upload_invalid_type(db_session, mock_embedding, mock_storage):
    svc = FileService(db_session, mock_embedding, mock_storage)
    with pytest.raises(ValueError, match="Unsupported file type"):
        await svc.upload(
            user_id="u1",
            filename="virus.exe",
            file_data=b"malware",
        )


@pytest.mark.asyncio
async def test_create_from_text(db_session, mock_embedding, mock_storage):
    svc = FileService(db_session, mock_embedding, mock_storage)
    doc = await svc.create_from_text(
        user_id="u1",
        title="Meeting Notes",
        content="Discussed Q2 OKR targets",
        category="work",
        tags=["meeting", "okr"],
    )
    assert doc.filename == "Meeting Notes.txt"
    assert doc.file_type == "txt"
    assert doc.category == "work"
    assert doc.tags == ["meeting", "okr"]


@pytest.mark.asyncio
async def test_list_documents(db_session, mock_embedding, mock_storage):
    svc = FileService(db_session, mock_embedding, mock_storage)
    await svc.upload(user_id="u1", filename="a.txt", file_data=b"aaa", category="notes")
    await svc.upload(user_id="u1", filename="b.md", file_data=b"bbb", category="docs")
    await db_session.commit()

    docs = await svc.list_documents(user_id="u1")
    assert len(docs) == 2


@pytest.mark.asyncio
async def test_list_filter_by_category(db_session, mock_embedding, mock_storage):
    svc = FileService(db_session, mock_embedding, mock_storage)
    await svc.upload(user_id="u1", filename="a.txt", file_data=b"aaa", category="notes")
    await svc.upload(user_id="u1", filename="b.txt", file_data=b"bbb", category="docs")
    await db_session.commit()

    docs = await svc.list_documents(user_id="u1", category="notes")
    assert len(docs) == 1
    assert docs[0].category == "notes"


@pytest.mark.asyncio
async def test_get_document(db_session, mock_embedding, mock_storage):
    svc = FileService(db_session, mock_embedding, mock_storage)
    doc = await svc.upload(user_id="u1", filename="test.txt", file_data=b"test content")
    await db_session.commit()

    result = await svc.get_document(doc.id)
    assert result is not None
    assert result.filename == "test.txt"


@pytest.mark.asyncio
async def test_delete_document(db_session, mock_embedding, mock_storage):
    svc = FileService(db_session, mock_embedding, mock_storage)
    doc = await svc.upload(user_id="u1", filename="test.txt", file_data=b"test")
    await db_session.commit()

    deleted = await svc.delete_document(doc.id)
    assert deleted is True

    result = await svc.get_document(doc.id)
    assert result is None


@pytest.mark.asyncio
async def test_delete_nonexistent(db_session, mock_embedding, mock_storage):
    svc = FileService(db_session, mock_embedding, mock_storage)
    deleted = await svc.delete_document(uuid.uuid4())
    assert deleted is False

"""文件管理路由: /api/files/*"""
from fastapi import APIRouter, Depends, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.web.auth.models import User
from app.web.database import get_db
from app.web.dependencies import get_current_user
from app.web.files.schemas import FileInfo
from app.web.files.service import (
    delete_file_record,
    get_file_or_404,
    list_user_files,
    save_uploaded_file,
)


router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=FileInfo)
async def upload_file(
    file: UploadFile,
    chat_id: int | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await save_uploaded_file(db, user.id, file, chat_id)
    return FileInfo.model_validate(record)


@router.get("", response_model=list[FileInfo])
async def list_files(
    chat_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    records = await list_user_files(db, user.id, chat_id)
    return [FileInfo.model_validate(r) for r in records]


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await get_file_or_404(db, file_id, user.id)
    full_path = config.web.sandbox_data_root / record.file_path
    return FileResponse(
        str(full_path),
        filename=record.filename,
        media_type=record.mime_type or "application/octet-stream",
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await get_file_or_404(db, file_id, user.id)
    await delete_file_record(db, record)
    return {"ok": True}

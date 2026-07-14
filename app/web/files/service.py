"""文件存取业务逻辑。"""
import os
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.web.files.models import UserFile


async def save_uploaded_file(
    db: AsyncSession,
    user_id: int,
    file: UploadFile,
    chat_id: int | None = None,
) -> UserFile:
    """保存上传文件到用户目录并写入数据库记录。"""
    user_dir = config.web.sandbox_data_root / "users" / str(user_id) / "uploads"
    user_dir.mkdir(parents=True, exist_ok=True)

    dest_path = user_dir / file.filename
    # 避免覆盖：重名文件加序号
    counter = 1
    while dest_path.exists():
        stem, ext = os.path.splitext(file.filename)
        dest_path = user_dir / f"{stem}_{counter}{ext}"
        counter += 1

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    record = UserFile(
        user_id=user_id,
        chat_id=chat_id,
        filename=dest_path.name,
        file_path=str(dest_path.relative_to(config.web.sandbox_data_root)),
        file_size=len(content),
        mime_type=file.content_type,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_user_files(
    db: AsyncSession,
    user_id: int,
    chat_id: int | None = None,
) -> list[UserFile]:
    """列出用户文件，可按会话过滤。"""
    query = select(UserFile).where(UserFile.user_id == user_id)
    if chat_id is not None:
        query = query.where(UserFile.chat_id == chat_id)
    query = query.order_by(UserFile.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_file_or_404(
    db: AsyncSession,
    file_id: int,
    user_id: int,
) -> UserFile:
    """获取文件记录，校验权限。"""
    result = await db.execute(
        select(UserFile).where(UserFile.id == file_id, UserFile.user_id == user_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return record


async def delete_file_record(db: AsyncSession, record: UserFile) -> None:
    """删除数据库记录和磁盘文件。"""
    # 删磁盘
    full_path = config.web.sandbox_data_root / record.file_path
    if full_path.exists():
        full_path.unlink()
    # 删记录
    await db.delete(record)
    await db.commit()

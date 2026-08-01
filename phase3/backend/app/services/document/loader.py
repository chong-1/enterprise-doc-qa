"""文件存储封装：保存 / 读取 / 删除上传的文档。

开发期使用本地文件系统（STORAGE_TYPE=local）：
DB 中仅存相对路径（如 uploads/2026/08/xxx.pdf），
运行时通过 BASE_DIR + LOCAL_STORAGE_DIR 解析为绝对路径。
未来切换 MinIO 时只需替换本模块实现，接口不变。
"""

import uuid
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import NotFoundError

# 存储根目录：backend/data/uploads
STORAGE_ROOT: Path = settings.BASE_DIR / settings.LOCAL_STORAGE_DIR


def _resolve(relative_path: str) -> Path:
    """将 DB 中的相对路径解析为绝对路径，并做越界防护。"""
    path = (STORAGE_ROOT / relative_path).resolve()
    if not str(path).startswith(str(STORAGE_ROOT.resolve())):
        raise ValueError(f"非法存储路径: {relative_path}")
    return path


def save_file(content: bytes, filename: str) -> str:
    """保存文件内容，返回相对路径（yyyy/mm/uuid_文件名）。"""
    now = datetime.now()
    date_dir = STORAGE_ROOT / f"{now.year:04d}" / f"{now.month:02d}"
    date_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}_{filename}"
    relative_path = f"{now.year:04d}/{now.month:02d}/{unique_name}"
    target = date_dir / unique_name
    target.write_bytes(content)
    return relative_path


def read_file(relative_path: str) -> bytes:
    """读取文件内容。"""
    path = _resolve(relative_path)
    if not path.is_file():
        raise NotFoundError(f"存储文件不存在: {relative_path}")
    return path.read_bytes()


def delete_file(relative_path: str) -> None:
    """删除文件（不存在时静默忽略）。"""
    path = _resolve(relative_path)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

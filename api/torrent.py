from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from models.session import get_db
from models.models import Torrent, File, Source, User
from core.user import get_current_user
from core.scheduler import scheduler

router = APIRouter()

@router.get("/{source_id}/torrents")
async def get_source_torrents(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取指定源的所有种子"""
    # 检查源是否存在
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="源不存在"
        )
    
    # 获取该源的所有种子
    result = await db.execute(
        select(Torrent).where(Torrent.source_id == source_id)
    )
    torrents = result.scalars().all()
    
    return {
        "source": {
            "id": source.id,
            "title": source.title,
            "url": source.url,
            "type": source.type
        },
        "torrents": [
            {
                "id": torrent.id,
                "hash": torrent.hash,
                "url": torrent.url,
                "title": torrent.title,  # 添加标题字段
                "status": torrent.status,
                "download_progress": torrent.download_progress,
                "created_at": torrent.created_at.isoformat(),
                "started_at": torrent.started_at.isoformat() if torrent.started_at else None,
                "completed_at": torrent.completed_at.isoformat() if torrent.completed_at else None,
                "error_message": torrent.error_message
            }
            for torrent in torrents
        ]
    }

@router.get("/{torrent_id}/files")
async def get_torrent_files(
    torrent_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取指定种子的所有文件"""
    # 检查种子是否存在
    torrent = await db.get(Torrent, torrent_id)
    if not torrent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="种子不存在"
        )
    
    # 获取该种子的所有文件
    result = await db.execute(
        select(File).where(File.torrent_id == torrent_id)
    )
    files = result.scalars().all()
    
    return {
        "torrent": {
            "id": torrent.id,
            "hash": torrent.hash,
            "status": torrent.status,
            "download_progress": torrent.download_progress
        },
        "files": [
            {
                "id": file.id,
                "name": file.name,
                "path": file.path,
                "size": file.size,
                "file_type": file.file_type,
                "extracted_episode": file.extracted_episode,
                "final_episode": file.final_episode,
                "hardlink_path": file.hardlink_path,
                "hardlink_status": file.hardlink_status,
                "hardlink_error": file.hardlink_error,
                "created_at": file.created_at.isoformat()
            }
            for file in files
        ]
    }

@router.post("/file/{file_id}/hardlink")
async def create_manual_hardlink(
    file_id: int,
    force_overwrite: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """手动为文件创建硬链接"""
    try:
        # 检查文件是否存在
        file_record = await db.get(File, file_id)
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在"
            )
        
        # 调用调度器的硬链接创建方法
        result = await scheduler.file_make_hardlink(db, file_id, force_overwrite)
        
        # 判断结果是否为成功的路径
        if result.startswith("/") or result.startswith("\\"):
            return {
                "status": "success",
                "message": "硬链接创建成功",
                "hardlink_path": result
            }
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": "error",
                    "message": result
                }
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": f"创建硬链接失败: {str(e)}"
            }
        )

@router.get("/file/{file_id}/info")
async def get_file_info(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取文件详细信息"""
    try:
        file_info = await scheduler.get_file_info(db, file_id)
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在"
            )
        
        return {
            "status": "success",
            "file": file_info
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error", 
                "message": f"获取文件信息失败: {str(e)}"
            }
        )

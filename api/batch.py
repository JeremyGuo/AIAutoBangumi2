"""Batch operations API for torrents and sources."""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.session import get_db
from models.models import User, Torrent, Source
from core.user import get_current_admin_user
from utils.qbittorrent import QBittorrentClient

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class BatchTorrentOperation(BaseModel):
    """批量种子操作请求模型"""
    torrent_ids: List[int]
    action: str  # pause, resume, delete, retry


class BatchSourceOperation(BaseModel):
    """批量源操作请求模型"""
    source_ids: List[int]
    action: str  # delete, reset_check, enable, disable


@router.post("/torrents")
async def batch_torrent_operation(
    operation: BatchTorrentOperation,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    批量操作种子
    
    支持的操作：
    - pause: 暂停下载
    - resume: 恢复下载
    - delete: 删除种子（不删除文件）
    - retry: 重试失败的种子
    """
    try:
        if not operation.torrent_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未选择任何种子"
            )
        
        if operation.action not in ["pause", "resume", "delete", "retry"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的操作类型"
            )
        
        # 获取选中的种子
        result = await db.execute(
            select(Torrent).where(Torrent.id.in_(operation.torrent_ids))
        )
        torrents = result.scalars().all()
        
        if not torrents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到指定的种子"
            )
        
        success_count = 0
        failed_count = 0
        errors = []
        
        with QBittorrentClient() as qb_client:
            for torrent in torrents:
                try:
                    if operation.action == "pause":
                        # 暂停种子
                        if qb_client.pause_torrent(torrent.hash):
                            success_count += 1
                        else:
                            failed_count += 1
                            errors.append(f"暂停种子 {torrent.hash} 失败")
                    
                    elif operation.action == "resume":
                        # 恢复种子
                        if qb_client.resume_torrent(torrent.hash):
                            success_count += 1
                        else:
                            failed_count += 1
                            errors.append(f"恢复种子 {torrent.hash} 失败")
                    
                    elif operation.action == "delete":
                        # 从qBittorrent中删除种子（不删除文件）
                        if qb_client.delete_torrent(torrent.hash, delete_files=False):
                            # 更新数据库状态
                            await db.execute(
                                update(Torrent)
                                .where(Torrent.id == torrent.id)
                                .values(status="deleted")
                            )
                            success_count += 1
                        else:
                            failed_count += 1
                            errors.append(f"删除种子 {torrent.hash} 失败")
                    
                    elif operation.action == "retry":
                        # 重试失败的种子
                        if torrent.status == "failed":
                            await db.execute(
                                update(Torrent)
                                .where(Torrent.id == torrent.id)
                                .values(status="pending", error_message=None)
                            )
                            success_count += 1
                        else:
                            failed_count += 1
                            errors.append(f"种子 {torrent.hash} 不是失败状态")
                
                except Exception as e:
                    failed_count += 1
                    errors.append(f"处理种子 {torrent.hash} 时出错: {str(e)}")
                    logger.error(f"Error processing torrent {torrent.hash}: {e}")
        
        await db.commit()
        
        return {
            "status": "completed",
            "action": operation.action,
            "total": len(operation.torrent_ids),
            "success": success_count,
            "failed": failed_count,
            "errors": errors[:10]  # 只返回前10个错误
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch torrent operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量操作失败: {str(e)}"
        )


@router.post("/sources")
async def batch_source_operation(
    operation: BatchSourceOperation,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    批量操作源
    
    支持的操作：
    - delete: 删除源
    - reset_check: 重置检查时间
    - enable: 启用源（取消过期标记）
    - disable: 禁用源（标记为过期）
    """
    try:
        if not operation.source_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未选择任何源"
            )
        
        if operation.action not in ["delete", "reset_check", "enable", "disable"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的操作类型"
            )
        
        # 获取选中的源
        result = await db.execute(
            select(Source).where(Source.id.in_(operation.source_ids))
        )
        sources = result.scalars().all()
        
        if not sources:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到指定的源"
            )
        
        success_count = 0
        failed_count = 0
        errors = []
        
        try:
            if operation.action == "delete":
                # 删除源（会级联删除相关的种子和文件）
                for source in sources:
                    try:
                        await db.delete(source)
                        success_count += 1
                    except Exception as e:
                        failed_count += 1
                        errors.append(f"删除源 {source.title} 失败: {str(e)}")
            
            elif operation.action == "reset_check":
                # 重置检查时间
                from datetime import datetime, timezone
                past_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
                
                await db.execute(
                    update(Source)
                    .where(Source.id.in_(operation.source_ids))
                    .values(last_check=past_time)
                )
                success_count = len(sources)
            
            elif operation.action == "enable":
                # 启用源
                await db.execute(
                    update(Source)
                    .where(Source.id.in_(operation.source_ids))
                    .values(outdated=False)
                )
                success_count = len(sources)
            
            elif operation.action == "disable":
                # 禁用源
                await db.execute(
                    update(Source)
                    .where(Source.id.in_(operation.source_ids))
                    .values(outdated=True)
                )
                success_count = len(sources)
            
            await db.commit()
        
        except Exception as e:
            await db.rollback()
            raise e
        
        return {
            "status": "completed",
            "action": operation.action,
            "total": len(operation.source_ids),
            "success": success_count,
            "failed": failed_count,
            "errors": errors[:10]  # 只返回前10个错误
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch source operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量操作失败: {str(e)}"
        )


@router.post("/torrents/recheck")
async def batch_recheck_torrents(
    torrent_ids: List[int],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    批量重新检查种子文件
    
    在qBittorrent中重新验证种子文件的完整性
    """
    try:
        if not torrent_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未选择任何种子"
            )
        
        # 获取种子
        result = await db.execute(
            select(Torrent).where(Torrent.id.in_(torrent_ids))
        )
        torrents = result.scalars().all()
        
        success_count = 0
        failed_count = 0
        
        with QBittorrentClient() as qb_client:
            for torrent in torrents:
                try:
                    if qb_client.recheck_torrent(torrent.hash):
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error rechecking torrent {torrent.hash}: {e}")
        
        return {
            "status": "completed",
            "total": len(torrent_ids),
            "success": success_count,
            "failed": failed_count
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch recheck: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量重新检查失败: {str(e)}"
        )

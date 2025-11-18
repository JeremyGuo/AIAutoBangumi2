"""Notifications API endpoints."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from models.models import User
from core.user import get_current_admin_user
from utils.notifications import notification_manager

import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class NotificationTest(BaseModel):
    """测试通知请求模型"""
    title: str
    message: str


@router.post("/test")
async def test_notification(
    notification: NotificationTest,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    测试通知服务
    
    发送测试通知到所有启用的通知渠道
    """
    try:
        results = await notification_manager.send_notification(
            notification.title,
            notification.message
        )
        
        return {
            "status": "completed",
            "results": results,
            "message": "测试通知已发送"
        }
    
    except Exception as e:
        logger.error(f"Error testing notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送测试通知失败: {str(e)}"
        )


@router.get("/status")
async def get_notification_status(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    获取通知服务状态
    
    返回所有已配置的通知服务及其状态
    """
    try:
        services_status = []
        
        for service in notification_manager.services:
            service_name = service.__class__.__name__
            services_status.append({
                "name": service_name,
                "enabled": service.enabled,
                "type": service_name.replace("Notification", "").lower()
            })
        
        return {
            "total_services": len(notification_manager.services),
            "services": services_status
        }
    
    except Exception as e:
        logger.error(f"Error getting notification status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取通知状态失败: {str(e)}"
        )


@router.post("/download-completed")
async def notify_download_completed(
    torrent_title: str,
    file_count: int,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    发送下载完成通知
    """
    try:
        results = await notification_manager.notify_download_completed(
            torrent_title,
            file_count
        )
        
        return {
            "status": "completed",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Error sending download completed notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送通知失败: {str(e)}"
        )

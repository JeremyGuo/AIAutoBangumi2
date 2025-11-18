"""Notification system for AIAutoBangumi2."""
import asyncio
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from core.config import CONFIG
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服务基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enable", False)
    
    async def send(self, title: str, message: str, **kwargs) -> bool:
        """发送通知"""
        raise NotImplementedError


class TelegramNotification(NotificationService):
    """Telegram通知服务"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.token = config.get("token")
        self.chat_id = config.get("chat_id")
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
    
    async def send(self, title: str, message: str, **kwargs) -> bool:
        """发送Telegram消息"""
        if not self.enabled or not self.token or not self.chat_id:
            logger.debug("Telegram notification is disabled or not configured")
            return False
        
        try:
            full_message = f"<b>{title}</b>\n\n{message}"
            
            payload = {
                "chat_id": self.chat_id,
                "text": full_message,
                "parse_mode": "HTML"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Telegram notification sent: {title}")
                        return True
                    else:
                        logger.error(f"Failed to send Telegram notification: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False


class EmailNotification(NotificationService):
    """邮件通知服务"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_server = config.get("smtp_server")
        self.smtp_port = config.get("smtp_port", 587)
        self.smtp_username = config.get("smtp_username")
        self.smtp_password = config.get("smtp_password")
        self.smtp_from = config.get("smtp_from")
        self.smtp_to = config.get("smtp_to")
    
    async def send(self, title: str, message: str, **kwargs) -> bool:
        """发送邮件通知"""
        if not self.enabled or not all([
            self.smtp_server,
            self.smtp_username,
            self.smtp_password,
            self.smtp_from,
            self.smtp_to
        ]):
            logger.debug("Email notification is disabled or not configured")
            return False
        
        try:
            # 在线程池中运行同步的邮件发送
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email_sync, title, message)
            logger.info(f"Email notification sent: {title}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    def _send_email_sync(self, title: str, message: str):
        """同步发送邮件"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = title
        msg['From'] = self.smtp_from
        msg['To'] = self.smtp_to
        
        # 添加HTML内容
        html = f"""
        <html>
        <head></head>
        <body>
            <h2>{title}</h2>
            <p>{message}</p>
        </body>
        </html>
        """
        
        part = MIMEText(html, 'html')
        msg.attach(part)
        
        # 发送邮件
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)


class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.services = []
        self._initialize_services()
    
    def _initialize_services(self):
        """初始化通知服务"""
        try:
            if hasattr(CONFIG, 'notifications'):
                for notification_config in CONFIG.notifications:
                    notification_type = notification_config.get("type")
                    
                    if notification_type == "telegram":
                        service = TelegramNotification(notification_config)
                        if service.enabled:
                            self.services.append(service)
                            logger.info("Telegram notification service initialized")
                    
                    elif notification_type == "email":
                        service = EmailNotification(notification_config)
                        if service.enabled:
                            self.services.append(service)
                            logger.info("Email notification service initialized")
        
        except Exception as e:
            logger.error(f"Error initializing notification services: {e}")
    
    async def send_notification(self, title: str, message: str, **kwargs) -> Dict[str, bool]:
        """发送通知到所有启用的服务"""
        results = {}
        
        for service in self.services:
            service_name = service.__class__.__name__
            try:
                success = await service.send(title, message, **kwargs)
                results[service_name] = success
            except Exception as e:
                logger.error(f"Error sending notification via {service_name}: {e}")
                results[service_name] = False
        
        return results
    
    async def notify_download_completed(self, torrent_title: str, file_count: int):
        """下载完成通知"""
        title = "🎉 下载完成"
        message = f"种子 '{torrent_title}' 已下载完成！\n共 {file_count} 个文件。"
        return await self.send_notification(title, message)
    
    async def notify_download_failed(self, torrent_title: str, error_message: str):
        """下载失败通知"""
        title = "❌ 下载失败"
        message = f"种子 '{torrent_title}' 下载失败。\n错误信息: {error_message}"
        return await self.send_notification(title, message)
    
    async def notify_hardlink_completed(self, file_name: str, hardlink_path: str):
        """硬链接创建完成通知"""
        title = "🔗 硬链接创建成功"
        message = f"文件 '{file_name}' 硬链接已创建。\n路径: {hardlink_path}"
        return await self.send_notification(title, message)
    
    async def notify_new_episode(self, series_title: str, episode: int):
        """新剧集通知"""
        title = "📺 新剧集"
        message = f"'{series_title}' 第 {episode} 集已开始下载！"
        return await self.send_notification(title, message)
    
    async def notify_system_error(self, error_type: str, error_message: str):
        """系统错误通知"""
        title = "⚠️ 系统错误"
        message = f"错误类型: {error_type}\n错误信息: {error_message}"
        return await self.send_notification(title, message)


# 全局通知管理器实例
notification_manager = NotificationManager()

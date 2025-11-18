import logging
from typing import List, Dict, Any, Optional
import qbittorrentapi
from core.config import CONFIG

logger = logging.getLogger(__name__)

class QBittorrentClient:
    """qBittorrent Web API 客户端"""
    
    def __init__(self):
        self.host = CONFIG.download.qbittorrent_url
        self.port = CONFIG.download.qbittorrent_port
        self.username = CONFIG.download.qbittorrent_username
        self.password = CONFIG.download.qbittorrent_password
        self.client: Optional[qbittorrentapi.Client] = None
    
    def __enter__(self):
        self._connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.auth_log_out()
    
    def _connect(self):
        """连接到qBittorrent并登录"""
        try:
            self.client = qbittorrentapi.Client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password
            )
            
            # 登录
            self.client.auth_log_in()
            logger.debug("Successfully connected to qBittorrent")
            
        except qbittorrentapi.LoginFailed:
            logger.error("Failed to login to qBittorrent - invalid credentials")
            raise
        except qbittorrentapi.APIConnectionError as e:
            logger.error(f"Failed to connect to qBittorrent: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to qBittorrent: {e}")
            raise
    
    def _ensure_connected(self):
        """确保已连接，如果未连接则重新连接"""
        if not self.client:
            raise RuntimeError("QBittorrent client is not connected")
        
        # 检查连接状态，如果需要重新登录
        try:
            self.client.app.version
        except (qbittorrentapi.Unauthorized401Error, qbittorrentapi.Forbidden403Error):
            logger.debug("Re-authenticating with qBittorrent")
            self.client.auth_log_in()
    
    def add_magnet(self, magnet_url: str, save_path: Optional[str] = None) -> bool:
        """添加磁力链接到qBittorrent"""
        self._ensure_connected()
        assert self.client is not None  # 类型检查助手
        
        try:
            # 首先检查种子是否已存在
            if self.is_torrent_exists(magnet_url):
                logger.info(f"Torrent already exists, treating as successful: {magnet_url[:50]}...")
                return True
            
            # 添加磁力链接
            result = self.client.torrents_add(
                urls=magnet_url,
                save_path=save_path,
                use_auto_torrent_management=False
            )
            
            if result == "Ok.":
                logger.info(f"Successfully added magnet: {magnet_url[:50]}...")
                return True
            elif "already" in str(result).lower() or "exists" in str(result).lower():
                # 处理qBittorrent返回的重复添加消息
                logger.info(f"Torrent already exists (detected from response), treating as successful: {magnet_url[:50]}...")
                return True
            else:
                logger.error(f"Failed to add magnet: {result}")
                return False
                
        except Exception as e:
            # 检查异常消息是否表示重复添加
            error_msg = str(e).lower()
            if "already" in error_msg or "exists" in error_msg or "duplicate" in error_msg:
                logger.info(f"Torrent already exists (detected from exception), treating as successful: {magnet_url[:50]}...")
                return True
            
            logger.error(f"Error adding magnet to qBittorrent: {e}")
            return False
    
    def get_torrent_info(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        """获取种子信息"""
        self._ensure_connected()
        assert self.client is not None  # 类型检查助手
        
        try:
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            if torrents:
                # 将TorrentDictionary转换为普通字典
                return dict(torrents[0])
            return None
                    
        except Exception as e:
            logger.error(f"Error getting torrent info: {e}")
            return None
    
    def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """获取种子文件列表"""
        self._ensure_connected()
        assert self.client is not None  # 类型检查助手
        
        try:
            files = self.client.torrents_files(torrent_hash=torrent_hash)
            # 将TorrentFilesList转换为普通字典列表
            return [dict(f) for f in files]
                    
        except Exception as e:
            logger.error(f"Error getting torrent files: {e}")
            return []
    
    def is_torrent_exists(self, magnet_url: str) -> bool:
        """检查种子是否已存在于qBittorrent中"""
        self._ensure_connected()
        assert self.client is not None  # 类型检查助手
        
        try:
            # 从磁力链接提取hash
            torrent_hash = self.extract_hash_from_magnet(magnet_url)
            if not torrent_hash:
                return False
                
            torrents = self.client.torrents_info(torrent_hashes=torrent_hash)
            return len(torrents) > 0
                
        except Exception as e:
            logger.error(f"Error checking if torrent exists: {e}")
            return False
    
    @staticmethod
    def extract_hash_from_magnet(magnet_url: str) -> Optional[str]:
        """从磁力链接中提取hash"""
        try:
            import re
            match = re.search(r'xt=urn:btih:([a-fA-F0-9]{40})', magnet_url)
            if match:
                return match.group(1).lower()
            return None
        except Exception as e:
            logger.error(f"Error extracting hash from magnet: {e}")
            return None
    
    def pause_torrent(self, torrent_hash: str) -> bool:
        """暂停种子下载"""
        self._ensure_connected()
        assert self.client is not None
        
        try:
            self.client.torrents_pause(torrent_hashes=torrent_hash)
            logger.info(f"Successfully paused torrent: {torrent_hash}")
            return True
        except Exception as e:
            logger.error(f"Error pausing torrent {torrent_hash}: {e}")
            return False
    
    def resume_torrent(self, torrent_hash: str) -> bool:
        """恢复种子下载"""
        self._ensure_connected()
        assert self.client is not None
        
        try:
            self.client.torrents_resume(torrent_hashes=torrent_hash)
            logger.info(f"Successfully resumed torrent: {torrent_hash}")
            return True
        except Exception as e:
            logger.error(f"Error resuming torrent {torrent_hash}: {e}")
            return False
    
    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """删除种子"""
        self._ensure_connected()
        assert self.client is not None
        
        try:
            self.client.torrents_delete(
                delete_files=delete_files,
                torrent_hashes=torrent_hash
            )
            logger.info(f"Successfully deleted torrent: {torrent_hash} (delete_files={delete_files})")
            return True
        except Exception as e:
            logger.error(f"Error deleting torrent {torrent_hash}: {e}")
            return False
    
    def recheck_torrent(self, torrent_hash: str) -> bool:
        """重新检查种子文件"""
        self._ensure_connected()
        assert self.client is not None
        
        try:
            self.client.torrents_recheck(torrent_hashes=torrent_hash)
            logger.info(f"Successfully rechecked torrent: {torrent_hash}")
            return True
        except Exception as e:
            logger.error(f"Error rechecking torrent {torrent_hash}: {e}")
            return False
    
    def set_torrent_speed_limit(self, torrent_hash: str, download_limit: int, upload_limit: int) -> bool:
        """设置种子速度限制（单位：bytes/s）"""
        self._ensure_connected()
        assert self.client is not None
        
        try:
            self.client.torrents_set_download_limit(
                limit=download_limit,
                torrent_hashes=torrent_hash
            )
            self.client.torrents_set_upload_limit(
                limit=upload_limit,
                torrent_hashes=torrent_hash
            )
            logger.info(f"Successfully set speed limit for torrent: {torrent_hash}")
            return True
        except Exception as e:
            logger.error(f"Error setting speed limit for torrent {torrent_hash}: {e}")
            return False

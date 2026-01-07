import aiohttp
import hashlib
import bencodepy
import os
import tempfile
import time
import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import quote
import logging
from core.config import CONFIG
from utils.dht import dht_service

logger = logging.getLogger(__name__)

# 全局缓存配置
CACHE_DIR = os.path.join(tempfile.gettempdir(), "aibangumi_torrent_cache")
CACHE_EXPIRY_HOURS = 24 * 30 * 6  # 缓存过期时间（小时）
MAX_CACHE_SIZE_MB = 100  # 最大缓存大小（MB）

def _ensure_cache_dir():
    """确保缓存目录存在"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)

def _get_cache_path(url: str) -> str:
    """根据URL生成缓存文件路径"""
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.torrent")

def _is_cache_valid(cache_path: str) -> bool:
    """检查缓存文件是否有效（存在且未过期）"""
    if not os.path.exists(cache_path):
        return False
    
    # 检查文件修改时间
    file_mtime = os.path.getmtime(cache_path)
    current_time = time.time()
    expiry_time = CACHE_EXPIRY_HOURS * 3600  # 转换为秒
    
    return (current_time - file_mtime) < expiry_time

def _save_to_cache(url: str, data: bytes) -> None:
    """保存数据到缓存"""
    try:
        _ensure_cache_dir()
        cache_path = _get_cache_path(url)
        
        with open(cache_path, 'wb') as f:
            f.write(data)
        
        logger.debug(f"Saved torrent to cache: {cache_path}")
        
        # 清理过期缓存
        _cleanup_expired_cache()
        
    except Exception as e:
        logger.warning(f"Failed to save torrent to cache: {e}")

def _load_from_cache(url: str) -> Optional[bytes]:
    """从缓存加载数据"""
    try:
        cache_path = _get_cache_path(url)
        
        if _is_cache_valid(cache_path):
            with open(cache_path, 'rb') as f:
                data = f.read()
            logger.info(f"Loaded torrent from cache: {url}")
            return data
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to load torrent from cache: {e}")
        return None

def _cleanup_expired_cache() -> None:
    """清理过期的缓存文件"""
    try:
        if not os.path.exists(CACHE_DIR):
            return
        
        current_time = time.time()
        expiry_time = CACHE_EXPIRY_HOURS * 3600
        total_size = 0
        files_info = []
        
        # 收集所有缓存文件信息
        for filename in os.listdir(CACHE_DIR):
            if filename.endswith('.torrent'):
                filepath = os.path.join(CACHE_DIR, filename)
                try:
                    stat = os.stat(filepath)
                    files_info.append({
                        'path': filepath,
                        'mtime': stat.st_mtime,
                        'size': stat.st_size
                    })
                    total_size += stat.st_size
                except OSError:
                    continue
        
        # 删除过期文件
        deleted_count = 0
        for file_info in files_info:
            if (current_time - file_info['mtime']) > expiry_time:
                try:
                    os.remove(file_info['path'])
                    total_size -= file_info['size']
                    deleted_count += 1
                except OSError:
                    pass
        
        # 如果缓存总大小超过限制，删除最旧的文件
        max_size_bytes = MAX_CACHE_SIZE_MB * 1024 * 1024
        if total_size > max_size_bytes:
            # 按修改时间排序（最旧的在前）
            files_info.sort(key=lambda x: x['mtime'])
            
            for file_info in files_info:
                if total_size <= max_size_bytes:
                    break
                
                try:
                    os.remove(file_info['path'])
                    total_size -= file_info['size']
                    deleted_count += 1
                except OSError:
                    pass
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired/old cache files")
            
    except Exception as e:
        logger.warning(f"Error during cache cleanup: {e}")

def clear_torrent_cache() -> None:
    """清空所有种子缓存"""
    try:
        if os.path.exists(CACHE_DIR):
            import shutil
            shutil.rmtree(CACHE_DIR)
            logger.info("Torrent cache cleared")
    except Exception as e:
        logger.error(f"Error clearing torrent cache: {e}")

def get_cache_info() -> Dict[str, Any]:
    """获取缓存信息"""
    try:
        if not os.path.exists(CACHE_DIR):
            return {
                'total_files': 0,
                'total_size': 0,
                'cache_dir': CACHE_DIR
            }
        
        total_files = 0
        total_size = 0
        
        for filename in os.listdir(CACHE_DIR):
            if filename.endswith('.torrent'):
                filepath = os.path.join(CACHE_DIR, filename)
                try:
                    total_size += os.path.getsize(filepath)
                    total_files += 1
                except OSError:
                    pass
        
        return {
            'total_files': total_files,
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': CACHE_DIR,
            'expiry_hours': CACHE_EXPIRY_HOURS,
            'max_size_mb': MAX_CACHE_SIZE_MB
        }
        
    except Exception as e:
        logger.error(f"Error getting cache info: {e}")
        return {'error': str(e)}

async def get_file_list(url: str) -> List[Dict[str, Any]]:
    """
    获取种子文件列表
    """
    try:
        if url.startswith("magnet:"):
            # 对于磁力链接，我们无法直接获取文件列表
            # 需要通过BitTorrent客户端获取
            logger.warning("Cannot get file list from magnet link directly")
            return []
        else:
            # 对于.torrent文件，解析并返回文件列表
            torrent_data = await download_torrent_file(url)
            if torrent_data:
                return parse_torrent_files(torrent_data)
            return []
    except Exception as e:
        logger.error(f"Error getting file list from {url}: {e}")
        return []

async def convert_torrent_to_magnet(url: str) -> str:
    """
    将种子文件转换为磁力链接
    """
    try:
        # 如果已经是磁力链接，直接返回
        if url.startswith("magnet:"):
            return url
        
        # 1. 下载种子文件
        torrent_data = None
        
        # 如果URL看起来像种子文件URL
        if url.endswith(".torrent") or "torrent" in url:
            torrent_data = await download_torrent_file(url)
        else:
            # 如果是其他格式，尝试作为磁力链接处理
            torrent_data = await download_torrent_file_magnet(url)
        
        if not torrent_data:
            logger.error(f"Failed to download/convert torrent: {url}")
            return ""
        
        # 2. 解析种子文件并生成info_hash
        try:
            torrent_dict = bencodepy.decode(torrent_data)  # type: ignore
            info_dict = torrent_dict[b'info']  # type: ignore
            info_encoded = bencodepy.encode(info_dict)
            info_hash = hashlib.sha1(info_encoded).hexdigest()
            
            # 3. 构建磁力链接
            magnet_params = {
                'xt': f'urn:btih:{info_hash}',
            }
            
            # 添加显示名称
            if b'name' in info_dict:
                name = info_dict[b'name'].decode('utf-8', errors='ignore')  # type: ignore
                magnet_params['dn'] = name
            
            # 添加tracker信息
            if b'announce' in torrent_dict:
                tracker = torrent_dict[b'announce'].decode('utf-8', errors='ignore')  # type: ignore
                magnet_params['tr'] = tracker
            
            # 添加多个tracker
            if b'announce-list' in torrent_dict:
                trackers = []
                for tracker_list in torrent_dict[b'announce-list']:  # type: ignore
                    for tracker in tracker_list:
                        trackers.append(tracker.decode('utf-8', errors='ignore'))
                # 只取前几个tracker避免URL过长
                for tracker in trackers[:5]:
                    if 'tr' not in magnet_params:
                        magnet_params['tr'] = tracker
                    else:
                        # 对于多个tracker，需要特殊处理
                        pass
            
            # 构建最终的磁力链接
            # 手动构建磁力链接以避免对冒号进行URL编码
            magnet_link = f"magnet:?xt=urn:btih:{info_hash}"
            
            # 添加显示名称
            if 'dn' in magnet_params:
                magnet_link += f"&dn={quote(magnet_params['dn'])}"
            
            # 添加主要tracker
            if 'tr' in magnet_params:
                magnet_link += f"&tr={quote(magnet_params['tr'])}"
            
            # 添加额外的tracker（如果有多个）
            if b'announce-list' in torrent_dict:
                trackers = []
                for tracker_list in torrent_dict[b'announce-list']:  # type: ignore
                    for tracker in tracker_list:
                        trackers.append(tracker.decode('utf-8', errors='ignore'))
                
                for tracker in trackers[:10]:  # 限制tracker数量
                    magnet_link += f"&tr={quote(tracker)}"
            
            logger.info(f"Successfully converted torrent to magnet: {info_hash}")
            return magnet_link
            
        except Exception as e:
            logger.error(f"Error parsing torrent file: {e}")
            return ""
            
    except Exception as e:
        logger.error(f"Error converting torrent to magnet: {e}")
        return ""

async def download_torrent_file(url: str) -> Optional[bytes]:
    """
    下载种子文件（带缓存功能）
    """
    try:
        # 1. 首先尝试从缓存加载
        cached_data = _load_from_cache(url)
        if cached_data:
            return cached_data
        
        # 2. 缓存中没有，从网络下载
        logger.info(f"Downloading torrent file: {url}")
        async with aiohttp.ClientSession() as session:
            # 设置代理（如果配置了）
            proxy = CONFIG.general.http_proxy if hasattr(CONFIG.general, 'http_proxy') else None
            
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=30),
                proxy=proxy
            ) as response:
                if response.status == 200:
                    content = await response.read()
                    logger.info(f"Successfully downloaded torrent file: {url}")
                    
                    # 3. 保存到缓存
                    _save_to_cache(url, content)
                    
                    return content
                else:
                    logger.error(f"Failed to download torrent file: {url}, status: {response.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"Error downloading torrent file {url}: {e}")
        return None

def parse_torrent_files(torrent_data: bytes) -> List[Dict[str, Any]]:
    """
    解析种子文件，返回文件列表
    """
    try:
        torrent_dict = bencodepy.decode(torrent_data)  # type: ignore
        info_dict = torrent_dict[b'info']  # type: ignore
        
        files = []
        
        if b'files' in info_dict:
            # 多文件种子
            for file_info in info_dict[b'files']:  # type: ignore
                file_path_parts = [part.decode('utf-8', errors='ignore') for part in file_info[b'path']]  # type: ignore
                file_path = '/'.join(file_path_parts)
                file_size = file_info[b'length']  # type: ignore
                
                files.append({
                    'name': file_path_parts[-1],
                    'path': file_path,
                    'size': file_size
                })
        else:
            # 单文件种子
            file_name = info_dict[b'name'].decode('utf-8', errors='ignore')  # type: ignore
            file_size = info_dict[b'length']  # type: ignore
            
            files.append({
                'name': file_name,
                'path': file_name,
                'size': file_size
            })
        
        return files
        
    except Exception as e:
        logger.error(f"Error parsing torrent files: {e}")
        return []

def extract_info_hash_from_magnet(magnet_url: str) -> Optional[str]:
    """
    从磁力链接中提取info_hash
    """
    try:
        import re
        match = re.search(r'xt=urn:btih:([a-fA-F0-9]{40})', magnet_url)
        if match:
            return match.group(1).lower()
        return None
    except Exception as e:
        logger.error(f"Error extracting info_hash from magnet: {e}")
        return None

def is_valid_magnet_link(url: str) -> bool:
    """
    检查是否是有效的磁力链接
    """
    if not url.startswith("magnet:"):
        return False
    
    # 检查是否包含必要的xt参数
    return "xt=urn:btih:" in url

async def get_magnet_info(magnet_url: str) -> Dict[str, Any]:
    """
    从磁力链接中提取信息，优先通过下载种子文件获取详细信息
    """
    try:
        # 首先尝试下载种子文件获取详细信息
        torrent_data = await download_torrent_file_magnet(magnet_url)
        
        if torrent_data:
            try:
                # 解析种子文件
                torrent_dict = bencodepy.decode(torrent_data)
                if not isinstance(torrent_dict, dict):
                    raise ValueError("Invalid torrent file format")
                
                info_dict = torrent_dict.get(b'info', {})
                
                info = {}
                
                # 从种子文件中提取名称
                if b'name' in info_dict:
                    try:
                        info['name'] = info_dict[b'name'].decode('utf-8')
                    except UnicodeDecodeError:
                        # 尝试其他编码
                        try:
                            info['name'] = info_dict[b'name'].decode('gbk')
                        except UnicodeDecodeError:
                            info['name'] = info_dict[b'name'].decode('latin-1')
                
                # 计算info_hash
                info_encoded = bencodepy.encode(info_dict)
                info_hash = hashlib.sha1(info_encoded).hexdigest().lower()
                info['info_hash'] = info_hash
                
                # 提取文件列表
                files = []
                if b'files' in info_dict:
                    # 多文件种子
                    for file_info in info_dict[b'files']:
                        path_parts = [part.decode('utf-8', errors='ignore') for part in file_info[b'path']]
                        file_path = '/'.join(path_parts)
                        files.append({
                            'path': file_path,
                            'length': file_info[b'length']
                        })
                else:
                    # 单文件种子
                    if b'name' in info_dict and b'length' in info_dict:
                        files.append({
                            'path': info_dict[b'name'].decode('utf-8', errors='ignore'),
                            'length': info_dict[b'length']
                        })
                
                info['files'] = files
                
                # 提取tracker列表
                trackers = []
                if b'announce' in torrent_dict:
                    trackers.append(torrent_dict[b'announce'].decode('utf-8', errors='ignore'))
                if b'announce-list' in torrent_dict:
                    for tier in torrent_dict[b'announce-list']:
                        for tracker in tier:
                            tracker_url = tracker.decode('utf-8', errors='ignore')
                            if tracker_url not in trackers:
                                trackers.append(tracker_url)
                
                info['trackers'] = trackers
                
                logger.info(f"Successfully extracted torrent info from downloaded file for magnet: {magnet_url[:50]}...")
                return info
                
            except Exception as e:
                logger.warning(f"Failed to parse downloaded torrent file: {e}, falling back to URL parsing")
        
        # 如果下载种子文件失败，回退到从URL解析
        from urllib.parse import parse_qs, urlparse
        
        parsed = urlparse(magnet_url)
        params = parse_qs(parsed.query)
        
        info = {}
        
        # 提取info_hash
        if 'xt' in params:
            xt = params['xt'][0]
            if xt.startswith('urn:btih:'):
                info['info_hash'] = xt[9:].lower()
        
        # 提取显示名称
        if 'dn' in params:
            info['name'] = params['dn'][0]
        
        # 提取tracker列表
        if 'tr' in params:
            info['trackers'] = params['tr']
        
        logger.info(f"Extracted magnet info from URL parameters: {magnet_url[:50]}...")
        return info
        
    except Exception as e:
        logger.error(f"Error getting magnet info: {e}")
        return {}

def extract_title_from_rss_item(item: Dict[str, Any]) -> Optional[str]:
    """
    从RSS项目中提取种子标题
    """
    try:
        # 优先使用RSS项目的标题
        if 'title' in item and item['title']:
            return item['title'].strip()
        
        # 如果没有标题，尝试从磁力链接中提取
        magnet_url = item.get("magnet") or item.get("enclosure")
        if magnet_url and magnet_url.startswith("magnet:"):
            magnet_info = asyncio.run(get_magnet_info(magnet_url))
            if 'name' in magnet_info:
                return magnet_info['name'].strip()
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting title from RSS item: {e}")
        return None

async def extract_title_from_torrent(url: str, raise_on_error: bool = False) -> Optional[str]:
    """
    从种子文件或磁力链接中提取标题
    """
    try:
        if url.startswith("magnet:"):
            # 从磁力链接提取标题
            torrent_data = await download_torrent_file_magnet(url)
        else:
            # 从种子文件提取标题
            torrent_data = await download_torrent_file(url)
        if not torrent_data:
            if raise_on_error:
                raise RuntimeError("无法获取种子元数据，可能是DHT未启动或网络不可达")
            return None

        try:
            torrent_dict = bencodepy.decode(torrent_data)  # type: ignore
            info_dict = torrent_dict[b'info']  # type: ignore

            if b'name' in info_dict:
                name = info_dict[b'name'].decode('utf-8', errors='ignore')  # type: ignore
                return name.strip()
        except Exception as e:
            logger.error(f"Error parsing torrent file for title: {e}")
            if raise_on_error:
                raise RuntimeError(f"解析种子文件失败: {e}")

        if raise_on_error:
            raise RuntimeError("种子元数据缺少标题字段")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting title from torrent: {e}")
        if raise_on_error:
            raise RuntimeError(f"无法提取种子标题: {e}")
        return None

async def download_torrent_file_magnet(url: str) -> Optional[bytes]:
    """
    从磁力链接获取种子数据
    
    Args:
        url: 磁力链接
        
    Returns:
        Optional[bytes]: 种子文件数据，失败返回None
    """
    if not url.startswith("magnet:"):
        logger.error(f"Invalid magnet URL: {url}")
        return None
    
    # 1. 首先检查缓存
    cached_data = _load_from_cache(url)
    if cached_data:
        return cached_data
    
    # 2. 提取info_hash
    info_hash = extract_info_hash_from_magnet(url)
    if not info_hash:
        logger.error(f"Cannot extract info_hash from magnet: {url}")
        return None
    
    logger.info(f"Attempting to download torrent from magnet: {info_hash}")
    
    # 3. 尝试通过DHT服务获取种子数据
    torrent_data = await dht_service.get_torrent_file(url)
    if torrent_data:
        logger.info(f"Successfully downloaded torrent from DHT: {info_hash}")
        _save_to_cache(url, torrent_data)
        return torrent_data
    
    logger.error(f"Failed to download torrent from magnet link: {url}")
    return None


async def _download_from_itorrents(info_hash: str) -> Optional[bytes]:
    """通过 itorrents.org 下载种子文件"""
    try:
        # itorrents.org API endpoint
        torrent_url = f"https://itorrents.org/torrent/{info_hash.upper()}.torrent"
        
        async with aiohttp.ClientSession() as session:
            # 设置代理
            proxy = None
            if hasattr(CONFIG.general, 'http_proxy') and CONFIG.general.http_proxy:
                proxy = CONFIG.general.http_proxy
            logger.info(f"Downloading from itorrents.org: {torrent_url} via proxy: {proxy}")
            
            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/x-bittorrent,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            async with session.get(
                torrent_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
                proxy=proxy,
                allow_redirects=True
            ) as response:
                if response.status == 200:
                    content = await response.read()
                    # 验证是否为有效的种子文件
                    if _is_valid_torrent_data(content):
                        return content
                    else:
                        logger.warning(f"Invalid torrent data from itorrents.org: {info_hash}")
                        return None
                else:
                    logger.debug(f"itorrents.org returned status {response.status} for {info_hash}")
                    return None
                    
    except Exception as e:
        logger.debug(f"Error downloading from itorrents.org: {e}")
        return None


async def _download_from_other_services(info_hash: str) -> Optional[bytes]:
    """通过其他公共服务下载种子文件"""
    
    # 备用服务列表
    services = [
        f"https://thetorrent.org/torrent/{info_hash.upper()}.torrent",
        f"https://torrage.info/torrent.php?h={info_hash.lower()}",
        f"http://torrent.ubuntu.com:6969/file?info_hash={info_hash.lower()}",
        f"https://academictorrents.com/download/{info_hash.lower()}.torrent"
    ]
    
    for service_url in services:
        try:
            async with aiohttp.ClientSession() as session:
                # 设置代理
                proxy = None
                if hasattr(CONFIG.general, 'http_proxy') and CONFIG.general.http_proxy:
                    proxy = CONFIG.general.http_proxy
                
                # 设置请求头
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/x-bittorrent,*/*',
                }
                
                async with session.get(
                    service_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                    proxy=proxy,
                    allow_redirects=True
                ) as response:
                    if response.status == 200:
                        content = await response.read()
                        # 验证是否为有效的种子文件
                        if _is_valid_torrent_data(content):
                            logger.info(f"Downloaded torrent from alternative service: {service_url}")
                            return content
                        
        except Exception as e:
            logger.debug(f"Error downloading from {service_url}: {e}")
            continue
    
    return None


async def _download_from_local_client(magnet_url: str, info_hash: str) -> Optional[bytes]:
    """通过本地BitTorrent客户端获取种子数据"""
    try:
        # 这里可以集成本地的BitTorrent客户端
        # 例如：transmission, qbittorrent, libtorrent等
        
        # 方法1: 尝试通过qBittorrent API（如果配置了）
        if hasattr(CONFIG, 'download') and hasattr(CONFIG.download, 'qbittorrent_url'):
            torrent_data = await _download_from_qbittorrent(magnet_url, info_hash)
            if torrent_data:
                return torrent_data
        
        # 方法2: 使用临时的libtorrent session（如果库可用）
        torrent_data = await _download_with_libtorrent(magnet_url, info_hash)
        if torrent_data:
            return torrent_data
        
        return None
        
    except Exception as e:
        logger.debug(f"Error downloading from local client: {e}")
        return None


async def _download_from_qbittorrent(magnet_url: str, info_hash: str) -> Optional[bytes]:
    """通过qBittorrent API获取种子数据"""
    try:
        # 这里可以添加qBittorrent API调用
        # 暂时返回None，避免复杂的客户端集成
        return None
        
    except Exception as e:
        logger.debug(f"Error downloading from qBittorrent: {e}")
        return None


async def _download_with_libtorrent(magnet_url: str, info_hash: str) -> Optional[bytes]:
    """使用libtorrent库获取种子数据"""
    try:
        # 检查是否有libtorrent库
        try:
            import libtorrent as lt
        except ImportError:
            logger.debug("libtorrent library not available")
            return None
        
        # 由于libtorrent的API版本差异较大，这里暂时跳过
        # 在生产环境中需要根据具体的libtorrent版本进行适配
        logger.debug("libtorrent integration not implemented yet")
        return None
        
    except Exception as e:
        logger.debug(f"Error using libtorrent: {e}")
        return None


def _is_valid_torrent_data(data: bytes) -> bool:
    """验证是否为有效的种子文件数据"""
    try:
        if not data or len(data) < 100:  # 种子文件至少应该有一定大小
            return False
        
        # 尝试解析bencode格式
        import bencodepy
        torrent_dict = bencodepy.decode(data)
        
        # 检查必要的字段
        if not isinstance(torrent_dict, dict) or b'info' not in torrent_dict:
            return False
        
        info_dict = torrent_dict[b'info']
        if not isinstance(info_dict, dict) or b'name' not in info_dict:
            return False
        
        # 检查是否有文件信息
        if b'files' not in info_dict and b'length' not in info_dict:
            return False
        
        return True
        
    except Exception:
        return False

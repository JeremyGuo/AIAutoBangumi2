import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.session import AsyncSessionLocal
from models.models import Source, Torrent, File
from utils.rss import get_rss_data
from utils.qbittorrent import QBittorrentClient
from utils.ai import get_episode_from_filename, is_file_important
from core.config import CONFIG

logger = logging.getLogger(__name__)

class AutoBangumiScheduler:
    """定时任务调度器"""
    
    def __init__(self):
        self.running = False
        self.task = None
    
    async def _safe_commit(self, session: Any):
        """安全地提交数据库事务"""
        try:
            if hasattr(session, 'commit'):
                if asyncio.iscoroutinefunction(session.commit):
                    await session.commit()
                else:
                    session.commit()
        except Exception as e:
            logger.error(f"Error committing transaction: {e}")
    
    async def _safe_rollback(self, session: Any):
        """安全地回滚数据库事务"""
        try:
            if hasattr(session, 'rollback'):
                if asyncio.iscoroutinefunction(session.rollback):
                    await session.rollback()
                else:
                    session.rollback()
        except Exception as e:
            logger.error(f"Error rolling back transaction: {e}")
    
    async def start(self):
        """启动定时任务"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run_scheduler())
        logger.info("AutoBangumi scheduler started")
    
    async def stop(self):
        """停止定时任务"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("AutoBangumi scheduler stopped")
    
    async def _run_scheduler(self):
        """运行定时任务主循环"""
        while self.running:
            try:
                await self._execute_tasks()
                # 等待60秒后执行下一轮
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in scheduler: {e}")
                await asyncio.sleep(60)
    
    async def _execute_tasks(self):
        """执行所有定时任务"""
        logger.info("Executing scheduled tasks...")
        
        session = AsyncSessionLocal()
        try:
            # 1. 检查RSS并创建新种子
            await self._check_rss_and_create_torrents(session)
            
            # 2. 检查磁力链接源并创建种子
            await self._check_magnet_sources(session)
            
            # 3. 将未添加的种子添加到qBittorrent
            await self._add_torrents_to_qbittorrent(session)
            
            # 4. 更新种子下载进度
            await self._update_torrent_progress(session)
            
            # 5. 处理已完成的种子
            await self._process_completed_torrents(session)
            
        except Exception as e:
            logger.error(f"Error in execute_tasks: {e}")
        finally:
            # 尝试关闭session
            try:
                if hasattr(session, 'close'):
                    if asyncio.iscoroutinefunction(session.close):
                        await session.close()
                    else:
                        session.close()
            except Exception as e:
                logger.error(f"Error closing session: {e}")
    
    async def _check_rss_and_create_torrents(self, db: Any):
        """检查RSS源并创建新种子"""
        logger.info("Checking RSS sources for new torrents...")
        
        # 获取所有RSS源
        result = await db.execute(
            select(Source).where(Source.type == "rss")
        )
        sources : List[Source] = list(result.scalars().all())
        
        for source in sources:
            try:
                # 检查是否需要更新（根据检查间隔）
                if source.last_check:
                    next_check = source.last_check + timedelta(seconds=source.check_interval)
                    if datetime.utcnow() < next_check:
                        continue
                
                # 获取RSS数据
                rss_data = await get_rss_data(source.url)
                if not rss_data:
                    logger.warning(f"Failed to get RSS data for source {source.id}")
                    continue
                
                # 处理每个RSS项目
                for item in rss_data.get("items", []):
                    await self._process_rss_item(db, source, item)
                
                # 更新最后检查时间
                await db.execute(
                    update(Source).where(Source.id == source.id).values(
                        last_check=datetime.utcnow()
                    )
                )
                await self._safe_commit(db)
                
            except Exception as e:
                logger.error(f"Error processing RSS source {source.id}: {e}")
        
    async def _check_magnet_sources(self, db: Any):
        """检查磁力链接源并创建种子"""
        logger.info("Checking magnet sources for new torrents...")
        
        # 获取所有磁力链接源
        result = await db.execute(
            select(Source).where(Source.type == "magnet")
        )
        sources: List[Source] = list(result.scalars().all())
        
        for source in sources:
            try:
                # 检查该磁力链接源是否已经创建过种子
                existing_torrent = await db.execute(
                    select(Torrent).where(Torrent.source_id == source.id)
                )
                if existing_torrent.scalar_one_or_none():
                    # 如果已经存在种子，跳过
                    logger.debug(f"Magnet source {source.id} already has torrent, skipping")
                    continue
                
                # 验证磁力链接格式
                magnet_url = source.url
                if not magnet_url.startswith("magnet:"):
                    logger.warning(f"Invalid magnet URL for source {source.id}: {magnet_url}")
                    continue
                
                # 提取种子hash
                torrent_hash = QBittorrentClient.extract_hash_from_magnet(magnet_url)
                logger.info(f"Processing magnet source {source.id}, magnet url: {magnet_url}, torrent hash: {torrent_hash}")
                if not torrent_hash:
                    logger.warning(f"Cannot extract hash from magnet URL: {magnet_url}")
                    continue
                
                # 检查是否已存在相同hash的种子（可能来自其他源）
                existing_hash_torrent = await db.execute(
                    select(Torrent).where(Torrent.hash == torrent_hash)
                )
                if existing_hash_torrent.scalar_one_or_none():
                    logger.info(f"Torrent with hash {torrent_hash} already exists, skipping magnet source {source.id}")
                    continue
                
                # 尝试从磁力链接中提取标题
                from utils.magnet import get_magnet_info
                magnet_info = await get_magnet_info(magnet_url)
                title = magnet_info.get('name') or source.title or f"Magnet Torrent {torrent_hash[:8]}"
                
                # 创建新种子记录
                new_torrent = Torrent(
                    hash=torrent_hash,
                    source_id=source.id,
                    url=magnet_url,
                    title=title,
                    status="pending",
                    download_progress=0.0,
                    created_at=datetime.utcnow()
                )
                
                db.add(new_torrent)
                await self._safe_commit(db)
                logger.info(f"Created new torrent from magnet source {source.id}: {torrent_hash}")
                
                # 更新源的最后检查时间（虽然磁力链接源不需要周期检查）
                await db.execute(
                    update(Source).where(Source.id == source.id).values(
                        last_check=datetime.utcnow()
                    )
                )
                await self._safe_commit(db)
                
            except Exception as e:
                logger.error(f"Error processing magnet source {source.id}: {e}")
                await self._safe_rollback(db)

    
    async def _process_rss_item(self, db: Any, source: Source, item: dict):
        """处理单个RSS项目"""
        # 提取磁力链接
        magnet_url : str | None = item.get("magnet") or item.get("enclosure")
        if magnet_url:
            if magnet_url.startswith("magnet:"):
                pass
            elif magnet_url.endswith(".torrent"):
                # 如果是种子文件链接，转换为磁力链接，下载种子文件，获取infohash，tracers，生成磁力链接
                from utils.magnet import convert_torrent_to_magnet
                magnet_url = await convert_torrent_to_magnet(magnet_url)
                if not magnet_url:
                    return
            else:
                return
        else:
            return
        
        # 提取种子hash
        torrent_hash = QBittorrentClient.extract_hash_from_magnet(magnet_url)
        logger.info(f"Processing RSS item for source {source.id}, manget url: {magnet_url}, torrent hash: {torrent_hash}")
        if not torrent_hash:
            return
        
        # 检查种子是否已存在
        existing_torrent = await db.execute(
            select(Torrent).where(Torrent.hash == torrent_hash)
        )
        if existing_torrent.scalar_one_or_none():
            return
        
        # 提取种子标题
        from utils.magnet import extract_title_from_rss_item, extract_title_from_torrent
        title = extract_title_from_rss_item(item)
        if not title:
            # 如果RSS项目没有标题，尝试从种子文件/磁力链接中提取
            title = await extract_title_from_torrent(magnet_url)
        
        # 创建新种子记录
        new_torrent = Torrent(
            hash=torrent_hash,
            source_id=source.id,
            url=magnet_url,
            title=title,  # 添加标题
            status="pending",
            download_progress=0.0,
            created_at=datetime.utcnow()
        )
        
        db.add(new_torrent)
        await self._safe_commit(db)
        logger.info(f"Created new torrent: {torrent_hash}")
    
    async def _add_torrents_to_qbittorrent(self, db: Any):
        """将未添加的种子添加到qBittorrent（包括pending和failed状态的种子）"""
        logger.info("Adding pending/failed torrents to qBittorrent...")
        
        # 获取所有待添加的种子（包括failed状态的种子）
        result = await db.execute(
            select(Torrent).where(Torrent.status.in_(["pending", "failed"]))
        )
        torrents : Optional[List[Torrent]] = result.scalars().all()
        logger.info(f"Found {len(torrents) if torrents else 0} pending/failed torrents to add to qBittorrent")
        
        if not torrents:
            return
        
        with QBittorrentClient() as qb_client:
            for torrent in torrents:
                try:
                    # 为failed状态的种子记录重试日志
                    if torrent.status == "failed":
                        logger.info(f"Retrying failed torrent: {torrent.hash}")
                    
                    # 检查种子是否已存在于qBittorrent中
                    if qb_client.is_torrent_exists(torrent.url):
                        # 更新状态为downloading
                        await db.execute(
                            update(Torrent).where(Torrent.id == torrent.id).values(
                                status="downloading",
                                started_at=datetime.utcnow()
                            )
                        )
                        logger.info(f"Torrent already exists in qBittorrent: {torrent.hash}")
                        continue
                    
                    # 添加到qBittorrent
                    success = qb_client.add_magnet(torrent.url)
                    if success:
                        await db.execute(
                            update(Torrent).where(Torrent.id == torrent.id).values(
                                status="downloading",
                                started_at=datetime.utcnow()
                            )
                        )
                        logger.info(f"Added torrent to qBittorrent: {torrent.hash}")
                    else:
                        await db.execute(
                            update(Torrent).where(Torrent.id == torrent.id).values(
                                status="failed",
                                error_message="Failed to add to qBittorrent"
                            )
                        )
                        logger.error(f"Failed to add torrent to qBittorrent: {torrent.hash}")
                
                except Exception as e:
                    logger.error(f"Error adding torrent {torrent.hash}: {e}")
                    await db.execute(
                        update(Torrent).where(Torrent.id == torrent.id).values(
                            status="failed",
                            error_message=str(e)
                        )
                        )
        
        await self._safe_commit(db)
    
    async def _update_torrent_progress(self, db: Any):
        """更新种子下载进度"""
        logger.debug("Updating torrent progress...")
        
        # 获取所有正在下载的种子
        result = await db.execute(
            select(Torrent).where(Torrent.status == "downloading")
        )
        torrents = result.scalars().all()
        
        if not torrents:
            return
        
        with QBittorrentClient() as qb_client:
            for torrent in torrents:
                try:
                    info = qb_client.get_torrent_info(torrent.hash)
                    if not info:
                        continue
                    
                    progress = info.get("progress", 0)
                    state = info.get("state", "")
                    
                    # 更新进度
                    update_data = {"download_progress": progress}
                    
                    # 检查是否下载完成
                    if state in ["uploading", "stalledUP", "queuedUP"] and progress >= 1.0:
                        update_data["status"] = "completed"
                        update_data["completed_at"] = datetime.utcnow()
                        logger.info(f"Torrent completed: {torrent.hash}")
                    
                    await db.execute(
                        update(Torrent).where(Torrent.id == torrent.id).values(**update_data)
                    )
                
                except Exception as e:
                    logger.error(f"Error updating progress for torrent {torrent.hash}: {e}")
        
        await self._safe_commit(db)
    
    async def _process_completed_torrents(self, db: Any):
        """处理已完成的种子"""
        logger.info("Processing completed torrents...")
        
        # 获取所有已完成但未处理文件的种子
        result = await db.execute(
            select(Torrent).where(
                Torrent.status == "completed",
                ~Torrent.files.any()  # 没有关联的文件记录
            )
        )
        torrents = result.scalars().all()
        
        if not torrents:
            return
        
        with QBittorrentClient() as qb_client:
            for torrent in torrents:
                try:
                    await self._process_torrent_files(db, qb_client, torrent)
                except Exception as e:
                    logger.error(f"Error processing files for torrent {torrent.hash}: {e}")
        
        await self._safe_commit(db)
    
    async def _process_torrent_files(self, db: Any, qb_client: QBittorrentClient, torrent: Torrent):
        """处理种子文件"""
        # 获取种子文件列表
        files = qb_client.get_torrent_files(torrent.hash)
        if not files:
            return
        
        # 获取源信息
        source : Optional[Source] = await db.get(Source, torrent.source_id)
        if not source:
            return
        
        for file_info in files:
            file_name = file_info.get("name", "")
            file_path = file_info.get("path") or file_info.get("name", "")
            file_size = file_info.get("size", 0)
            
            # 判断文件是否重要
            is_important, is_main_episode, is_video = await is_file_important(file_name)
            if not is_important:
                continue
            
            # 判断文件类型
            file_type = "episode" if is_main_episode else "special"
            if file_name.lower().endswith(('.srt', '.ass', '.ssa', '.vtt', '.sub')):
                file_type = "subtitle"
            
            # 创建文件记录
            file_record = File(
                torrent_id=torrent.id,
                name=file_name,
                path=file_path,
                size=file_size,
                file_type=file_type,
                created_at=datetime.utcnow()
            )
            
            # 提取剧集信息
            if (is_main_episode or file_type == "subtitle") and source.media_type == "tv":
                episode = await self._extract_episode_number(source, file_name)
                if episode:
                    file_record.extracted_episode = episode
                    file_record.final_episode = episode + source.episode_offset
            
            db.add(file_record)
            
            # 如果需要创建硬链接 (视频文件或字幕文件)
            if CONFIG.hardlink.enable and (is_video or file_type == "subtitle") and is_main_episode:
                hardlink_result = await self._create_hardlink(db, source, file_record, False)
                if hardlink_result.startswith("/"):
                    logger.info(f"硬链接创建成功: {hardlink_result}")
                else:
                    logger.warning(f"硬链接创建失败: {hardlink_result}")
    
    async def _extract_episode_number(self, source: Source, filename: str) -> Optional[int]:
        """提取剧集编号"""
        try:
            if source.use_ai_episode:
                # 使用AI提取
                episode = await get_episode_from_filename(filename)
                return episode if episode > 0 else None
            elif source.episode_regex:
                # 使用正则表达式提取
                match = re.search(source.episode_regex, filename)
                if match:
                    return int(match.group(1))
            return None
        except Exception as e:
            logger.error(f"Error extracting episode from {filename}: {e}")
            return None
    
    async def _create_hardlink(self, db: Any, source: Source, file_record: File, force_overwrite: bool = False) -> str:
        """创建硬链接
        
        Args:
            db: 数据库session
            source: 源信息
            file_record: 文件记录
            force_overwrite: 是否强制覆盖已存在的硬链接
            
        Returns:
            str: 创建的硬链接路径或错误信息
        """
        try:
            # Ensure title cannot escape output_base in strict mode
            title = source.title or ""
            if os.path.isabs(title) or ".." in os.path.normpath(title).split(os.sep):
                error_msg = f"非法标题路径: {title}"
                file_record.hardlink_status = "failed"
                file_record.hardlink_error = error_msg
                return error_msg

            # 检查是否开启硬链接
            if not CONFIG.hardlink.enable:
                error_msg = "未开启硬链接功能"
                file_record.hardlink_status = "failed"
                file_record.hardlink_error = error_msg
                return error_msg
            
            if not CONFIG.hardlink.output_base:
                error_msg = "未配置硬链接输出目录"
                file_record.hardlink_status = "failed"
                file_record.hardlink_error = error_msg
                return error_msg
            
            # 检查源文件是否存在
            source_path = file_record.path
            # 如果路径不是绝对路径，尝试与下载目录合并
            if not os.path.isabs(source_path) and hasattr(CONFIG.download, 'download_dir') and CONFIG.download.download_dir:
                source_path = os.path.join(CONFIG.download.download_dir, source_path)
            
            if not os.path.exists(source_path):
                error_msg = f"源文件不存在: {source_path}"
                file_record.hardlink_status = "failed"
                file_record.hardlink_error = error_msg
                return error_msg
            
            # 获取文件扩展名和基本名称
            file_basename, file_ext = os.path.splitext(source_path)
            
            # 根据媒体类型和文件类型构建目标路径
            dest_path = await self._build_hardlink_path(source, file_record, file_ext)
            if not dest_path:
                error_msg = "无法构建硬链接目标路径"
                file_record.hardlink_status = "failed"
                file_record.hardlink_error = error_msg
                return error_msg

            output_base = os.path.abspath(CONFIG.hardlink.output_base)
            dest_abs = os.path.abspath(dest_path)
            if os.path.commonpath([output_base, dest_abs]) != output_base:
                error_msg = f"硬链接路径越界: {dest_path}"
                file_record.hardlink_status = "failed"
                file_record.hardlink_error = error_msg
                return error_msg
            
            # 检查是否有多个文件会硬链接到同一个路径（仅在非强制覆盖模式下）
            if not force_overwrite:
                conflict_check = await self._check_hardlink_conflicts(db, dest_path, file_record.id)
                if conflict_check:
                    error_msg = f"硬链接冲突: 多个文件将指向同一路径 {dest_path}，存在冲突的文件: {conflict_check}"
                    file_record.hardlink_status = "failed"
                    file_record.hardlink_error = error_msg
                    return error_msg
            
            # 确保目标目录存在
            dest_dir = os.path.dirname(dest_path)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            
            logger.info(f"创建硬链接: {source_path} -> {dest_path}")
            
            # 如果目标文件已存在，直接删除（不管是否同一文件）
            if os.path.exists(dest_path):
                os.unlink(dest_path)
                logger.info(f"删除已存在的目标文件: {dest_path}")
            
            # 创建硬链接
            os.link(source_path, dest_path)
            logger.info(f"创建硬链接成功: {source_path} -> {dest_path}")
            
            # 更新File表
            file_record.hardlink_path = dest_path
            file_record.hardlink_error = None
            file_record.hardlink_status = "completed"
            
            return dest_path
            
        except Exception as e:
            error_msg = f"创建硬链接失败: {str(e)}"
            logger.error(error_msg)
            
            # 更新文件记录的错误状态
            file_record.hardlink_status = "failed"
            file_record.hardlink_error = str(e)
            
            return error_msg
    
    async def _build_hardlink_path(self, source: Source, file_record: File, file_ext: str) -> Optional[str]:
        """构建硬链接目标路径"""
        try:
            if source.media_type == "tv":
                # 对于电视剧
                season = source.season or 1
                episode = file_record.final_episode
                
                if episode is None:
                    return None
                
                # 创建目标路径: output_base/<source title>/Season <season>/
                season_dir = os.path.join(
                    CONFIG.hardlink.output_base, 
                    source.title, 
                    f"Season {season}"
                )
                
                # 格式化季和集数
                season_str = str(season).zfill(2)
                episode_str = str(episode).zfill(2)
                
                # 处理字幕文件的特殊命名
                if file_record.file_type == "subtitle":
                    # 检查字幕语言标识
                    file_name_lower = file_record.name.lower()
                    if "chs" in file_name_lower and "cht" in file_name_lower:
                        # 同时包含简繁，使用简体标识
                        subtitle_suffix = ".chs&cht"
                    elif "chs" in file_name_lower:
                        subtitle_suffix = ".chs"
                    elif "cht" in file_name_lower:
                        subtitle_suffix = ".cht"
                    elif "sc" in file_name_lower:
                        subtitle_suffix = ".sc"
                    elif "tc" in file_name_lower:
                        subtitle_suffix = ".tc"
                    else:
                        subtitle_suffix = ""
                    
                    file_name = f"{source.title} S{season_str}E{episode_str}{subtitle_suffix}{file_ext}"
                else:
                    # 视频文件或其他文件
                    file_name = f"{source.title} S{season_str}E{episode_str}{file_ext}"
                
                return os.path.join(season_dir, file_name)
            else:
                # 对于电影
                movie_dir = os.path.join(CONFIG.hardlink.output_base, source.title)
                
                if file_record.file_type == "subtitle":
                    # 电影字幕处理
                    file_name_lower = file_record.name.lower()
                    if "chs" in file_name_lower and "cht" in file_name_lower:
                        subtitle_suffix = ".chs&cht"
                    elif "chs" in file_name_lower:
                        subtitle_suffix = ".chs"
                    elif "cht" in file_name_lower:
                        subtitle_suffix = ".cht"
                    elif "sc" in file_name_lower:
                        subtitle_suffix = ".sc"
                    elif "tc" in file_name_lower:
                        subtitle_suffix = ".tc"
                    else:
                        subtitle_suffix = ""
                    
                    file_name = f"{source.title}{subtitle_suffix}{file_ext}"
                else:
                    file_name = f"{source.title}{file_ext}"
                
                return os.path.join(movie_dir, file_name)
                
        except Exception as e:
            logger.error(f"构建硬链接路径失败: {e}")
            return None
    
    async def _check_hardlink_conflicts(self, db: Any, dest_path: str, current_file_id: int) -> Optional[str]:
        """检查硬链接冲突"""
        try:
            # 查询是否有其他文件记录指向同一个目标路径
            result = await db.execute(
                select(File).where(
                    File.hardlink_path == dest_path,
                    File.id != current_file_id
                )
            )
            conflict_files = result.scalars().all()
            
            if conflict_files:
                conflict_names = [f.name for f in conflict_files]
                return ", ".join(conflict_names)
            
            return None
            
        except Exception as e:
            logger.error(f"检查硬链接冲突失败: {e}")
            return None
    
    
    async def file_make_hardlink(self, db: AsyncSession, file_id: int, force_overwrite: bool = False) -> str:
        """为文件创建硬链接
        
        Args:
            db: 数据库session
            file_id: 文件ID
            force_overwrite: 是否强制覆盖
            
        Returns:
            str: 创建的硬链接路径或错误信息
        """
        try:
            # 获取文件信息
            result = await db.execute(
                select(File).where(File.id == file_id)
            )
            file_record = result.scalar_one_or_none()
            if not file_record:
                return "文件不存在"
            
            # 获取种子信息
            torrent_result = await db.execute(
                select(Torrent).where(Torrent.id == file_record.torrent_id)
            )
            torrent = torrent_result.scalar_one_or_none()
            if not torrent:
                return "无法获取种子信息"
            
            # 获取源信息
            source_result = await db.execute(
                select(Source).where(Source.id == torrent.source_id)
            )
            source = source_result.scalar_one_or_none()
            if not source:
                return "无法获取源信息"
            
            # 使用统一的硬链接创建方法
            result = await self._create_hardlink(db, source, file_record, force_overwrite)
            
            # 提交数据库更改
            await self._safe_commit(db)
            
            return result
            
        except Exception as e:
            error_msg = f"创建硬链接失败: {str(e)}"
            logger.error(error_msg)
            
            # 更新文件记录的错误状态
            try:
                result = await db.execute(
                    select(File).where(File.id == file_id)
                )
                file_record = result.scalar_one_or_none()
                if file_record:
                    file_record.hardlink_status = "failed"
                    file_record.hardlink_error = str(e)
                    await self._safe_commit(db)
            except Exception as db_error:
                logger.error(f"更新文件状态失败: {db_error}")
            
            return error_msg
    
    async def get_file_info(self, db: AsyncSession, file_id: int) -> Optional[dict]:
        """获取文件信息
        
        Args:
            db: 数据库session
            file_id: 文件ID
            
        Returns:
            dict: 文件信息，包含源信息，如果不存在返回None
        """
        try:
            # 获取文件信息，包含关联的种子和源信息
            result = await db.execute(
                select(File)
                .join(Torrent, File.torrent_id == Torrent.id)
                .join(Source, Torrent.source_id == Source.id)
                .where(File.id == file_id)
            )
            file_record = result.scalar_one_or_none()
            
            if not file_record:
                return None
            
            # 获取种子信息
            torrent_result = await db.execute(
                select(Torrent).where(Torrent.id == file_record.torrent_id)
            )
            torrent = torrent_result.scalar_one_or_none()
            
            # 获取源信息
            source = None
            if torrent:
                source_result = await db.execute(
                    select(Source).where(Source.id == torrent.source_id)
                )
                source = source_result.scalar_one_or_none()
            
            # 构建返回信息
            file_info = {
                "id": file_record.id,
                "name": file_record.name,
                "path": file_record.path,
                "size": file_record.size,
                "file_type": file_record.file_type,
                "extracted_episode": file_record.extracted_episode,
                "final_episode": file_record.final_episode,
                "hardlink_path": file_record.hardlink_path,
                "hardlink_status": file_record.hardlink_status,
                "hardlink_error": file_record.hardlink_error,
                "created_at": file_record.created_at,
                "torrent": {
                    "id": torrent.id,
                    "hash": torrent.hash,
                    "title": torrent.title,
                    "status": torrent.status,
                } if torrent else None,
                "source": {
                    "id": source.id,
                    "title": source.title,
                    "media_type": source.media_type,
                    "season": source.season,
                    "episode_offset": source.episode_offset,
                } if source else None
            }
            
            return file_info
            
        except Exception as e:
            logger.error(f"Error getting file info for file_id {file_id}: {e}")
            return None

# 全局调度器实例
scheduler = AutoBangumiScheduler()

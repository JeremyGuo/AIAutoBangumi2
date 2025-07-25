import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class GeneralConfig(BaseModel):
    listen: int
    system_lang: str
    address: str
    http_proxy: Optional[str]
    # 添加密钥配置，用于JWT验证
    secret_key: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"  # 默认密钥，建议在生产环境中修改

class DownloadConfig(BaseModel):
    qbittorrent_port: int
    qbittorrent_url: str
    qbittorrent_username: str = "admin"
    qbittorrent_password: str = "adminadmin"
    # 添加下载目录和目标目录配置
    download_dir: str = ""

class HardlinkConfig(BaseModel):
    enable: bool
    output_base: str

class TMDBConfig(BaseModel):
    enabled: bool
    api_key: str

class LLMConfig(BaseModel):
    enable: bool
    url: str
    token: str
    name: str = "gpt-3.5-turbo"  # 默认使用gpt-3.5-turbo

class Settings(BaseModel):
    general: GeneralConfig
    download: DownloadConfig
    hardlink: HardlinkConfig
    notifications: List[dict]
    tmdb_api: TMDBConfig
    llm: LLMConfig

def load_config() -> Settings:
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("Config file not found")
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)
    return Settings(**config_dict)

CONFIG = load_config()
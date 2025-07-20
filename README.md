# AIAutoBangumi2 🎌

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)]()

**一个智能的动画自动下载与管理系统，基于AI技术的新一代番剧追踪工具。**

AIAutoBangumi2 是一个现代化的动画自动下载系统，集成了人工智能技术，能够智能识别剧集信息、自动生成正则表达式、**创建硬链接**（不会影响原本的下载器的做种）并与媒体库系统无缝对接。

## ✨ 主要特性

### 🤖 AI 智能功能
- **智能标题清洗**: 使用AI自动清理发布组标识、画质标记等冗余信息
- **自动剧集识别**: AI智能提取文件名中的剧集编号
- **智能正则生成**: 根据RSS源或种子文件自动生成剧集匹配正则表达式
- **文件重要性判断**: AI智能判断哪些文件需要下载和创建硬链接

### 📺 媒体管理
- **多源支持**: 支持RSS源和磁力链接两种下载源
- **智能硬链接**: 自动创建符合媒体库标准的硬链接结构
- **TMDB集成**: 自动从TMDB获取媒体信息和元数据
- **分季管理**: 智能识别并按季度组织剧集文件

### 🔄 自动化工作流
- **定时任务**: 自动检查RSS更新和种子下载状态
- **下载管理**: 与qBittorrent无缝集成，自动管理下载任务
- **进度追踪**: 实时监控下载进度和文件处理状态
- **错误恢复**: 智能重试失败的任务

### 🎨 现代化界面
- **Vue.js前端**: 响应式Web界面，支持移动端
- **实时更新**: 动态显示下载进度和状态
- **用户权限**: 支持多用户和管理员权限管理
- **RESTful API**: 完整的API接口，支持第三方集成

## 🚀 快速开始

### 环境要求

- Python 3.10+
- qBittorrent 4.0+
- 现代浏览器

### 安装部署

1. **克隆项目**
```bash
git clone https://github.com/JeremyGuo/AIAutoBangumi2.git
cd AIAutoBangumi2
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置系统**
```bash
# 复制配置模板
cp config.yaml.template config.yaml

# 编辑配置文件
nano config.yaml
```

4. **初始化数据库**
```bash
# 数据库会在首次启动时自动创建
```

5. **启动服务**
```bash
python main.py
```

6. **访问系统**
   
   打开浏览器访问 `http://localhost:8001`

### Docker 部署

```bash
# 构建镜像
docker build -t aiautobangumi2 .

# 运行容器
docker run -d \
  --name aiautobangumi2 \
  -p 8001:8001 \
  -v /path/to/config:/app/config \
  -v /path/to/downloads:/downloads \
  -v /path/to/media:/media \
  aiautobangumi2
```

## ⚙️ 配置说明

### 核心配置

```yaml
general:
  address: 0.0.0.0          # 监听地址
  listen: 8001              # 监听端口
  secret_key: your_secret   # JWT密钥
  http_proxy: ""            # HTTP代理

download:
  qbittorrent_url: "192.168.1.100"
  qbittorrent_port: 8080
  qbittorrent_username: "admin"
  qbittorrent_password: "password"
  download_dir: "/downloads"

hardlink:
  enable: true
  output_base: "/media/anime"

llm:
  enable: true
  url: "http://localhost:11434/v1/chat/completions"
  name: "deepseek-r1:14b"
  token: "your_api_key"

tmdb_api:
  enabled: true
  api_key: "your_tmdb_api_key"
```

### AI模型支持

- **OpenAI Compatible**: 支持OpenAI API格式的所有LLM
- **Ollama**: 支持本地部署的开源模型
- **DeepSeek**: 推荐使用DeepSeek R1系列模型
- **其他**: 任何支持OpenAI API格式的模型服务

## 📖 使用指南

### 添加下载源

1. **RSS源配置**
   - 支持标准RSS和Atom格式
   - 自动提取磁力链接
   - 智能生成剧集匹配规则

2. **磁力链接**
   - 直接添加磁力链接
   - 自动获取种子信息
   - 支持批量下载

### 媒体库整理

系统会自动创建符合Plex/Emby/Jellyfin标准的文件结构：

```
/media/anime/
├── 刀剑神域/
│   ├── Season 1/
│   │   ├── 刀剑神域 S01E01.mkv
│   │   ├── 刀剑神域 S01E02.mkv
│   │   └── ...
│   └── Season 2/
│       ├── 刀剑神域 S02E01.mkv
│       └── ...
└── 你的名字/
    └── 你的名字.mkv
```

### API使用

```python
import requests

# 获取所有源
response = requests.get("http://localhost:8001/api/source/list")
sources = response.json()

# 添加新源
data = {
    "type": "rss",
    "url": "https://example.com/rss.xml",
    "title": "动画名称",
    "media_type": "tv",
    "season": 1
}
response = requests.post("http://localhost:8001/api/source/create", json=data)
```

## 🏗️ 项目架构

```
AIAutoBangumi2/
├── api/                    # API接口
│   ├── auth.py            # 用户认证
│   ├── source.py          # 源管理
│   ├── torrent.py         # 种子管理
│   └── user.py            # 用户管理
├── core/                  # 核心逻辑
│   ├── config.py          # 配置管理
│   ├── scheduler.py       # 定时任务
│   └── sources.py         # 源处理
├── models/                # 数据模型
│   ├── base.py            # 基础模型
│   ├── models.py          # 数据表定义
│   └── session.py         # 数据库会话
├── utils/                 # 工具模块
│   ├── ai.py              # AI功能
│   ├── qbittorrent.py     # qBittorrent集成
│   ├── rss.py             # RSS处理
│   └── tmdb.py            # TMDB集成
├── templates/             # Web模板
├── static/                # 静态资源
└── main.py                # 主程序入口
```

## 🔧 高级功能

### 自定义AI提示词

可以通过修改`utils/ai.py`中的提示词来优化AI识别效果：

```python
# 自定义剧集识别提示词
EPISODE_EXTRACTION_PROMPT = """
你是一个专业的动漫文件名分析助手...
"""
```

### 自定义正则表达式

支持手动配置正则表达式以适应特殊命名格式：

```python
# 示例正则表达式
episode_regex = r"第(\d+)话"  # 匹配"第01话"格式
episode_regex = r"EP(\d+)"    # 匹配"EP01"格式
```

### Webhook集成

```python
# 下载完成后自动通知
webhook_url = "https://your-webhook-url.com"
requests.post(webhook_url, json={
    "title": "下载完成",
    "episode": "第01话",
    "file_path": "/media/anime/..."
})
```

## 🔍 功能详解

### 智能剧集识别
系统使用多层识别机制：
1. **AI分析**: 使用大语言模型分析文件名
2. **正则匹配**: 基于用户配置或自动生成的正则表达式
3. **备用规则**: 内置的通用匹配规则

### 文件重要性判断
AI会自动判断文件类型：
- **主要剧集**: 需要下载和硬链接的视频文件
- **字幕文件**: 配套的字幕文件
- **特典内容**: OP/ED、特别篇等额外内容
- **其他文件**: 不重要的文件，可跳过处理

### 硬链接管理
自动创建媒体库友好的文件结构：
- 支持电视剧季度管理
- 支持电影单文件管理  
- 自动命名规范化
- 避免重复文件占用空间

## 🚨 故障排除

### 常见问题

**Q: AI功能不工作**
```bash
# 检查LLM配置
curl -X POST http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-r1:14b","messages":[{"role":"user","content":"test"}]}'
```

**Q: qBittorrent连接失败**
```bash
# 检查qBittorrent Web UI是否启用
# 确认用户名密码正确
# 检查网络连接
```

**Q: 硬链接创建失败**
```bash
# 检查文件权限
# 确认目标目录存在且可写
# 验证源文件和目标在同一文件系统
```

**Q: TMDB API限制**
```bash
# 检查API密钥是否有效
# 确认请求频率不超过限制
# 检查网络代理设置
```

### 日志调试

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
python main.py

# 查看特定模块日志
tail -f logs/scheduler.log
tail -f logs/ai.log
```

## 🛠️ 开发指南

### 本地开发

```bash
# 克隆项目
git clone https://github.com/JeremyGuo/AIAutoBangumi2.git
cd AIAutoBangumi2

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 运行开发服务器
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_ai.py

# 代码覆盖率
pytest --cov=./ --cov-report=html
```

### 代码风格

```bash
# 格式化代码
black .
isort .

# 检查代码风格
flake8 .
mypy .
```

### 贡献流程

1. **Fork仓库**并克隆到本地
2. **创建分支**: `git checkout -b feature/your-feature`
3. **编写代码**并添加测试
4. **运行测试**确保通过
5. **提交代码**: `git commit -m "Add your feature"`
6. **推送分支**: `git push origin feature/your-feature`
7. **创建PR**并描述变更内容

## 🤝 贡献指南

我们欢迎各种形式的贡献！

### 提交问题
- 使用GitHub Issues报告Bug
- 提出功能建议和改进意见
- 分享使用经验和最佳实践

### 代码贡献
1. Fork本项目
2. 创建功能分支 (`git checkout -b feature/新功能`)
3. 提交更改 (`git commit -am '添加新功能'`)
4. 推送到分支 (`git push origin feature/新功能`)
5. 创建Pull Request

### 文档贡献
- 改进README和Wiki文档
- 添加使用示例和教程
- 翻译文档到其他语言

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的Python Web框架
- [Vue.js](https://vuejs.org/) - 渐进式JavaScript框架
- [qBittorrent](https://www.qbittorrent.org/) - 开源BitTorrent客户端
- [TMDB](https://www.themoviedb.org/) - 电影数据库API
- [Ollama](https://ollama.ai/) - 本地LLM运行环境
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL工具包
- [Pydantic](https://pydantic-docs.helpmanual.io/) - 数据验证库

---

<div align="center">

**如果这个项目对你有帮助，请给个⭐Star支持一下！**

Made with ❤️ by [JeremyGuo](https://github.com/JeremyGuo)

</div>

# 更新日志

## [2.0.0] - 2024-11-18

### 🎉 重大更新

本次更新为 AIAutoBangumi2 带来了大量新功能和改进，使系统更加强大和易用。

### ✨ 新增功能

#### 统计分析系统
- 添加系统概览统计 API (`/api/statistics/overview`)
  - 源、种子、文件数量统计
  - 下载进度和完成率
  - 存储空间使用情况
  - 最近24小时活动统计
- 添加下载历史按天统计 (`/api/statistics/download-history`)
- 添加热门源排行 (`/api/statistics/top-sources`)
- 添加存储空间按类型统计 (`/api/statistics/storage`)

#### 标签管理系统
- 实现标签管理功能 (`/api/tags`)
- 支持预定义标签（动画、电影、连载中、已完结等）
- 支持为源分配标签
- 支持按标签筛选源
- 支持创建自定义标签

#### 批量操作功能
- 实现批量种子操作 (`/api/batch/torrents`)
  - 批量暂停/恢复种子
  - 批量删除种子
  - 批量重试失败的种子
- 实现批量源操作 (`/api/batch/sources`)
  - 批量删除源
  - 批量重置检查时间
  - 批量启用/禁用源
- 添加批量重新检查种子功能

#### 备份和导出功能
- 实现源配置导出为 JSON (`/api/backup/export/sources`)
- 实现源配置导入 (`/api/backup/import/sources`)
- 实现统计数据导出 (`/api/backup/export/statistics`)
- 添加配置信息查看（敏感信息已脱敏）

#### 搜索和过滤系统
- 实现源搜索和过滤 (`/api/search/sources`)
  - 支持关键词搜索
  - 支持按类型、媒体类型、过期状态过滤
  - 支持分页
- 实现种子搜索和过滤 (`/api/search/torrents`)
  - 支持关键词搜索
  - 支持按状态、源过滤
  - 支持分页
- 实现文件搜索和过滤 (`/api/search/files`)
  - 支持关键词搜索
  - 支持按文件类型、硬链接状态过滤
  - 支持分页
- 实现全局搜索功能 (`/api/search/global`)
  - 同时搜索源、种子和文件

#### 通知服务增强
- 实现完整的通知服务系统 (`utils/notifications.py`)
- 支持 Telegram 通知
  - 自动发送下载完成、失败通知
  - 自动发送硬链接创建通知
  - 自动发送新剧集通知
  - 自动发送系统错误通知
- 支持邮件通知
  - 支持 HTML 格式邮件
  - 支持 SMTP 认证
- 添加通知测试功能 (`/api/notifications/test`)
- 添加通知服务状态查询 (`/api/notifications/status`)

#### qBittorrent 客户端增强
- 添加暂停种子方法 (`pause_torrent`)
- 添加恢复种子方法 (`resume_torrent`)
- 添加删除种子方法 (`delete_torrent`)
- 添加重新检查种子方法 (`recheck_torrent`)
- 添加设置速度限制方法 (`set_torrent_speed_limit`)

### 🔧 改进和优化

#### 中间件系统
- 添加请求日志中间件
  - 记录所有 API 请求和响应
  - 记录处理时间
  - 在响应头中添加 `X-Process-Time`
- 添加错误处理中间件
  - 统一错误响应格式
  - 自动处理常见异常
  - 提供友好的错误消息
- 添加安全响应头中间件
  - 自动添加 `X-Content-Type-Options`
  - 自动添加 `X-Frame-Options`
  - 自动添加 `X-XSS-Protection`
  - 自动添加 `Referrer-Policy`
- 添加速率限制中间件
  - 防止 API 滥用
  - 可配置的限制策略
  - 默认每个 IP 每分钟 100 请求

#### 代码结构优化
- 为所有模块添加 `__init__.py`
  - `api/__init__.py`
  - `core/__init__.py`
  - `models/__init__.py`
  - `schemas/__init__.py`
  - `utils/__init__.py`
- 改进模块导入结构
- 添加更好的类型注释

#### API 文档改进
- 为所有 API 路由添加标签分类
- 改进 FastAPI 配置
  - 更新应用描述
  - 优化文档路径
  - 添加版本信息
- 添加健康检查端点 (`/health`)

#### 依赖处理
- 使 libtorrent 依赖可选
  - DHT 服务在缺少依赖时自动禁用
  - 不影响其他功能的正常使用

### 📚 文档

- 添加完整的 API 使用指南 (`API_GUIDE.md`)
  - 详细的功能说明
  - 使用示例
  - 最佳实践
  - 常见问题解答
- 添加更新日志 (`CHANGELOG.md`)

### 🐛 Bug 修复

- 修复 DHT 服务在缺少 libtorrent 时导致程序无法启动的问题
- 改进错误处理，提供更友好的错误信息

### 📦 依赖更新

无新增必需依赖，所有新功能使用现有依赖实现。

### ⚠️ 破坏性变更

无破坏性变更，所有现有 API 保持兼容。

### 🔜 下一步计划

- 添加更多可视化图表
- 实现 WebSocket 实时更新
- 添加更多通知渠道（如 Discord、Webhook）
- 实现更细粒度的权限控制
- 添加任务队列优先级控制

---

## [1.0.0] - 2024-XX-XX

初始版本发布。

基础功能：
- RSS 和磁力链接源管理
- qBittorrent 集成
- AI 智能识别
- 硬链接管理
- TMDB 集成
- 用户认证系统

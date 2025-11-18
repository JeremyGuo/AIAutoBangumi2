# AIAutoBangumi2 新功能使用指南

## 🎉 新增功能概览

本次更新为 AIAutoBangumi2 添加了多个实用的新功能，极大提升了系统的可用性和易用性。

### ✨ 主要新增功能

1. **统计分析面板** - 全面了解系统运行状态
2. **标签管理系统** - 更好地组织和分类源
3. **批量操作功能** - 一次性管理多个种子或源
4. **备份和导出** - 轻松备份和迁移配置
5. **强大的搜索** - 快速找到所需内容
6. **通知服务** - 及时接收重要通知
7. **请求日志和错误处理** - 更好的调试和问题排查

## 📊 统计分析功能

### 访问统计面板

访问 `/api/statistics/overview` 查看系统概览：

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8001/api/statistics/overview
```

### 功能说明

- **系统概览**: 源、种子、文件的数量统计
- **下载历史**: 按天查看下载趋势
- **热门源排行**: 了解哪些源最活跃
- **存储统计**: 按文件类型统计存储空间

## 🏷️ 标签管理

### 使用标签组织源

为源添加标签，方便分类管理：

```bash
# 为源分配标签
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tags": ["动画", "连载中"]}' \
  http://localhost:8001/api/tags/1/assign
```

### 预定义标签

系统提供以下预定义标签：
- 动画
- 电影
- 连载中
- 已完结
- 高优先级
- 待补

## ⚡ 批量操作

### 批量管理种子

一次性操作多个种子：

```bash
# 批量暂停种子
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"torrent_ids": [1, 2, 3], "action": "pause"}' \
  http://localhost:8001/api/batch/torrents
```

支持的操作：
- `pause`: 暂停下载
- `resume`: 恢复下载  
- `delete`: 删除种子
- `retry`: 重试失败的种子

### 批量管理源

```bash
# 批量重置源检查时间
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_ids": [1, 2, 3], "action": "reset_check"}' \
  http://localhost:8001/api/batch/sources
```

## 💾 备份和导出

### 导出源配置

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8001/api/backup/export/sources \
  -o sources_backup.json
```

### 导入源配置

```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d @sources_backup.json \
  http://localhost:8001/api/backup/import/sources
```

## 🔍 搜索功能

### 全局搜索

同时搜索源、种子和文件：

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8001/api/search/global?q=刀剑神域"
```

### 高级搜索

按条件过滤：

```bash
# 搜索RSS类型的TV剧源
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8001/api/search/sources?type=rss&media_type=tv"

# 搜索正在下载的种子
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8001/api/search/torrents?status=downloading"
```

## 📢 通知服务

### 配置通知

在 `config.yaml` 中配置通知服务：

```yaml
notifications:
  - enable: true
    type: telegram
    token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"
  
  - enable: true
    type: email
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    smtp_username: "your_email@gmail.com"
    smtp_password: "your_password"
    smtp_from: "your_email@gmail.com"
    smtp_to: "recipient@example.com"
```

### 测试通知

```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "测试", "message": "这是一条测试消息"}' \
  http://localhost:8001/api/notifications/test
```

### 自动通知

系统会自动发送以下通知：
- 下载完成通知
- 下载失败通知
- 硬链接创建成功通知
- 新剧集开始下载通知
- 系统错误通知

## 🔧 中间件功能

### 请求日志

所有 API 请求都会被记录，响应头包含 `X-Process-Time` 显示处理时间。

### 速率限制

默认限制：每个 IP 每分钟 100 个请求。
超过限制会返回 429 错误。

### 安全响应头

自动添加安全响应头，保护应用安全。

## 📖 API 文档

访问以下地址查看完整 API 文档：

- Swagger UI: http://localhost:8001/api/docs
- ReDoc: http://localhost:8001/api/redoc
- OpenAPI JSON: http://localhost:8001/api/openapi.json

## 🚀 最佳实践

### 1. 定期备份

建议定期导出源配置进行备份：

```bash
# 每周备份一次
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8001/api/backup/export/sources \
  -o backup_$(date +%Y%m%d).json
```

### 2. 使用标签分类

为不同类型的源添加标签，便于管理：
- 新番使用 "连载中" 标签
- 完结作品使用 "已完结" 标签
- 重要的源使用 "高优先级" 标签

### 3. 批量操作提高效率

使用批量操作功能可以：
- 批量暂停/恢复下载以节省带宽
- 批量重试失败的种子
- 批量管理过期的源

### 4. 利用搜索快速定位

使用全局搜索和高级过滤快速找到：
- 特定的源或种子
- 失败的下载任务
- 硬链接创建失败的文件

### 5. 配置通知及时了解状态

配置通知服务可以：
- 第一时间知道下载完成
- 及时处理下载失败
- 了解系统错误

## ❓ 常见问题

### Q: 如何查看系统健康状态？

访问 `/health` 端点：
```bash
curl http://localhost:8001/health
```

### Q: API 请求速度慢怎么办？

检查响应头中的 `X-Process-Time` 了解处理时间。
如果持续较慢，可以查看统计信息了解系统负载。

### Q: 通知服务不工作？

1. 检查配置文件中的通知设置
2. 使用测试接口验证配置
3. 查看日志了解错误信息

### Q: 批量操作失败了怎么办？

批量操作的响应中包含成功和失败的详细信息，
可以根据错误信息针对性处理。

## 🔗 相关链接

- 项目主页: https://github.com/JeremyGuo/AIAutoBangumi2
- 问题反馈: https://github.com/JeremyGuo/AIAutoBangumi2/issues
- API 文档: http://localhost:8001/api/docs

---

感谢使用 AIAutoBangumi2！

# Git MCP Server

基于 MCP (Model Context Protocol) 的 Git 仓库管理服务。

## 核心功能

- 🔐 **Access Key 权限管理**：通过 Key 精准控制每个用户可访问的 Git 仓库及权限级别
- 📦 **仓库管理**：配置 Git 仓库 URL、认证凭据、主分支
- 🔒 **细粒度权限**：仓库级 (read_only/read_write/admin) + 分支正则 + 路径正则
- 📋 **完整审计**：记录所有 MCP 操作，支持按 Key/仓库/操作/状态筛选
- 🤖 **内置大模型**：集成 LLM 分析代码逻辑、审查差异
- 🖥️ **Web 管理后台**：Svelte 5 + Tailwind CSS + daisyUI

## 快速开始

### Docker 部署（推荐）

```bash
# 1. 配置
cp config/config.yml.example config/config.yml
# 编辑 config/config.yml，修改密钥和数据库密码

# 2. 启动
docker compose up -d --build

# 3. 访问
# 管理后台: http://localhost:3001/admin
# 默认账号: admin / admin123
```

### 本地开发

```bash
# 1. PostgreSQL
docker run -d --name git-mcp-server-pg \
  -e POSTGRES_DB=git_mcp_admin \
  -e POSTGRES_USER=git_mcp_admin \
  -e POSTGRES_PASSWORD=git_mcp_dev \
  -p 5433:5432 postgres:16-alpine

# 2. 安装依赖
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# 3. 配置
cp config/config.yml.example config/config.yml
# 编辑 config/config.yml

# 4. 运行
python -m src.server
```

## MCP 工具列表

| 工具 | 说明 |
|------|------|
| `list_repos` | 列出可访问的 Git 仓库 |
| `list_branches` | 列出分支 |
| `list_tags` | 列出标签 |
| `list_tree` | 列出目录树 |
| `read_file` | 读取文件内容 |
| `git_log` | 提交历史 |
| `git_show` | 查看提交详情 |
| `git_diff` | 比较差异 |
| `git_blame` | 查看修改者 |
| `git_grep` | 代码搜索 |
| `analyze_code` | LLM 分析代码 |
| `review_diff` | LLM 审查差异 |

## IDE 集成

在 IDE 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "git-mcp-server": {
      "url": "http://localhost:3001/mcp/sse",
      "transport": "sse",
      "headers": {
        "X-Access-Key": "your-access-key"
      }
    }
  }
}
```

## AI 辅助开发

- [AGENTS.md](AGENTS.md) — AI 编码助手（Claude Code / Codex / Cursor / Copilot）在本仓库的工作规则
- [docs/ai-coding-rules.md](docs/ai-coding-rules.md) — 详细编码规范（后端 / 前端 / 安全红线 / 常见坑）

## 安全特性

- 所有凭据 (Git 密码/Token/LLM API Key) 加密存储
- Access Key 支持 IP 白名单
- 仓库默认只读，`allow_write` 和 `allow_push` 需显式开启
- 完整审计日志 (谁、何时、做了什么、结果如何)
- JWT 认证的管理后台

## 目录结构

```
git_mcp_server/
├── config/          # 配置文件
├── docker/          # Docker 相关
├── frontend/        # Svelte 5 管理后台
├── script/          # 工具脚本
├── src/
│   ├── admin/       # 管理后台 API
│   ├── ai/          # 大模型集成
│   ├── git/         # Git 操作封装
│   ├── logging/     # 日志
│   ├── mcp/         # MCP 协议处理
│   ├── security/    # 安全工具
│   └── services/    # 外部服务
└── docs/            # 文档
```

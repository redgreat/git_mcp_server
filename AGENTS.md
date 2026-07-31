# AGENTS.md — AI 辅助开发规则

本文件为 AI 编码助手（Claude Code / Codex / Cursor / Copilot 等）提供在本仓库中工作的行为准则。详细版见 [docs/ai-coding-rules.md](docs/ai-coding-rules.md)。

## 项目概览

Git MCP Server：基于 MCP (Model Context Protocol) 的 Git 仓库管理服务。

- **后端**：Python 3.11 + FastAPI + SQLAlchemy（原生 Table/MetaData 风格，无 ORM Model 类）+ JWT + bcrypt
- **前端**：Svelte 5（runes 语法）+ Tailwind CSS v4 + daisyUI 5 + Vite（adapter-static，SPA）
- **数据库**：PostgreSQL 16
- **部署**：Docker Compose

## 常用命令

```bash
make test          # 运行全部后端测试（test/run_all.py）
make build         # 构建前端（cd frontend && npm install && npm run build）
make dev           # 构建前端并启动后端服务
make setup         # 初始化（复制 config.yml + 安装依赖）
make docker-up     # Docker 生产环境启动
```

后端启动：`python -m src.server`；前端开发服务器：`cd frontend && npm run dev`（端口 5174）。

## 目录结构

```
config/          # 配置文件（config.yml / config.yml.example）
docker/          # Docker 相关（含 docker-compose-local.yml）
frontend/src/    # Svelte 5 管理后台
  routes/        #   页面路由（+layout.svelte 为鉴权布局，login/ 为独立登录页）
script/          # 工具脚本（dockerrebuid.ps1、start.sh）
src/
  admin/         # 管理后台 API（web.py 路由、auth.py 认证、models.py 建表）
  ai/            # 大模型集成（LLM 分析/审查）
  gitops/        # Git 操作封装（repo_manager、git_operations）
  mcp/           # MCP 协议处理（tools.py、permissions.py、server.py）
  security/      # 安全（secret.py 加密、ip_whitelist.py、client_ip.py）
  services/      # 外部服务
  server.py      # FastAPI 入口（挂载 /admin 静态资源与 API 路由）
  config.py      # 配置加载（pydantic + yaml）
test/            # 后端测试（run_all.py 汇总）
```

## 关键架构约定

1. **路由挂载**：`/api/*` 为后端 API（`src/admin/web.py` 的 `build_admin_router`）；`/admin/*` 为前端 SPA（server.py 中 StaticFiles + 回退 index.html）。前端构建产物输出到 `src/static/`。
2. **认证**：`Authorization` header 直接传 JWT 裸 token（无 `Bearer` 前缀），后端 `verify_token` 解析。token 存 localStorage。
3. **鉴权布局**：`frontend/src/routes/+layout.svelte` 检查 token。**登录页 `/admin/login` 必须跳过布局拦截**（通过 `$page.url.pathname` 判断 `isLoginPage`），否则登录表单永远无法显示。
4. **凭据加密**：Git 密码/Token、LLM API Key 用 `src/security/secret.py` 的 `encrypt_text/decrypt_text`（master_key 派生加密）存储，禁止明文入库。
5. **权限模型**：Access Key → 仓库 → 分支正则 + 路径正则三级权限，见 `src/mcp/permissions.py`。
6. **数据库**：`src/admin/models.py` 的 `ensure_schema()` 启动时建表；操作使用 SQLAlchemy `Table` + `insert/select/update/delete` 表达式，不用 ORM Model 类。

## 开发规范

- 后端新增路由统一放进 `build_admin_router`，函数签名风格与现有代码一致。
- 用户可见文案用中文；错误信息返回 `detail` 字段（FastAPI 约定）。
- 前端使用 Svelte 5 runes（`$state` / `$derived` / `$props` / `$effect`），**不要**用旧版 `let x = reactive()` 或 `export let` 语法。
- 前端样式用 Tailwind 类 + daisyUI 组件（`btn` / `card` / `table` / `modal` / `alert` 等），避免大段手写 CSS。
- 不要引入新的 UI 框架或后端依赖，除非用户明确要求。
- 修改前先读相关文件理解上下文；改动保持最小，不做无关重构。

## 测试

- 后端测试在 `test/`，全部通过 `make test`（`test/run_all.py`）执行。
- 前端改动后必须 `cd frontend && npm run build` 验证编译通过。
- 交付前必须实际运行验证，禁止只贴代码不执行。

## 禁止事项

- 不要提交 `.env`、`config/config.yml`（含真实密钥）、`*.key`、`__pycache__`、`frontend/node_modules`、`frontend/build`、`src/static`。
- 不要打印或记录明文密码 / API Key / 加密密钥。
- 不要直接修改数据库生产数据；测试数据库与生产隔离。
- 不要在没有用户要求时执行 `git push` 或改写 git 历史。

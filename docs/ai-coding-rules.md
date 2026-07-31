# AI 辅助编码规则（详细版）

> 本文件是 `AGENTS.md` 的展开说明，供 AI 编码助手与人类开发者共同遵守。
> 适用于：Claude Code、OpenAI Codex、Cursor、GitHub Copilot、通义灵码等所有 AI 辅助工具。

---

## 1. 通用原则

1. **先读后改**：修改任何文件前，先阅读相关文件与调用链，理解上下文后再动手。禁止凭猜测编写不存在的符号、API 或导入。
2. **最小改动**：只改任务需要的部分。不做顺手重构、重命名、格式化无关代码。
3. **验证交付**：任何改动必须实际执行验证（跑测试 / 构建 / 启动服务），禁止只贴代码声称完成。
4. **风格跟随**：新代码与相邻代码风格保持一致（缩进、命名、注释语言）。
5. **中文沟通**：代码注释与用户可见文案使用中文，与现有代码一致。

## 2. 后端规范（Python / FastAPI）

### 2.1 目录职责

| 目录 | 职责 | 注意 |
|------|------|------|
| `src/admin/` | 管理后台 API、认证、建表 | 路由集中在 `web.py` 的 `build_admin_router` |
| `src/ai/` | LLM 集成（代码分析、差异审查） | API Key 必须加密存储 |
| `src/gitops/` | Git 操作封装 | 不直接 `os.system("git ...")`，用封装函数 |
| `src/mcp/` | MCP 协议、工具注册、权限校验 | 新增 MCP 工具需在 `tools.py` 注册并加权限检查 |
| `src/security/` | 加密、IP 白名单、客户端 IP | 密钥只从 `config.yml` 读取 |

### 2.2 代码风格

- 类型标注：函数参数与返回值尽量标注类型。
- SQLAlchemy：使用 `Table` + `insert/select/update/delete` 表达式风格（见 `src/admin/web.py`），**不要**引入 ORM Model 类。
- 会话管理：`with Session(engine) as session:`，操作后 `session.commit()`。
- 错误处理：API 层抛 `HTTPException(status_code, detail="中文提示")`；内部函数抛普通异常并记录日志（`get_logger`）。
- 日志：统一用 `src/logging_utils.py` 的 `get_logger(name, dir)`，禁止裸 `print` 调试输出遗留。
- 数据库操作涉及审计的操作（增删改）需调用 `_log_system(...)` 写系统日志。

### 2.3 安全红线

- **禁止**在代码、日志、测试中输出明文密码 / API Key / Git Token / master_key。
- 新增存储敏感字段一律用 `encrypt_text(value, master_key)`，读取用 `decrypt_text`。
- JWT secret、master_key 必须来自 `config.yml`，禁止硬编码默认值（开发默认值只能存在于 `config.yml.example`）。
- Access Key 相关接口校验权限时先 `_get_user(authorization)` 再 `auth_service.require_admin`（如需管理员）。

### 2.4 新增接口模板

```python
class XxxRequest(BaseModel):
    field: str = "default"

@router.get("/api/admin/xxx")
def list_xxx(authorization: str = Header(None)):
    user = _get_user(authorization)          # 校验登录
    auth_service.require_admin(user)          # 如需管理员
    with Session(engine) as session:
        rows = session.execute(select(xxx_table)).mappings().all()
    return [{...} for r in rows]
```

## 3. 前端规范（Svelte 5 + Tailwind + daisyUI）

### 3.1 语法

- 使用 **Svelte 5 runes**：`$state()` / `$derived()` / `$props()` / `$effect()`。
- 事件用 `onclick={handler}`（不是 `on:click`），属性绑定用 `bind:value={x}`。
- 条件渲染 `{#if}`、循环 `{#each}`、插槽 `{@render children()}`。

### 3.2 布局与路由

- `frontend/src/routes/+layout.svelte`：全局鉴权布局。**核心规则**：登录页 `/admin/login` 必须通过 `isLoginPage = $derived($page.url.pathname === '/admin/login')` 跳过 token 拦截，否则用户永远看不到登录表单。
- 所有管理页 URL 前缀为 `/admin/...`；后端 SPA 回退在 `src/server.py`。
- 新增页面：在 `frontend/src/routes/` 下新建目录 + `+page.svelte`，并在 `+layout.svelte` 侧边栏菜单加链接。

### 3.3 样式

- 优先使用 Tailwind 工具类与 daisyUI 组件：`btn` / `card` / `table table-sm` / `modal` / `alert` / `badge` / `input input-bordered` / `stat`。
- 登录页等独立页面可用自定义渐变与玻璃拟态（backdrop-blur），风格参考 `frontend/src/routes/login/+page.svelte`。
- 避免内联 style 大段 CSS；主题变量统一在 `app.css`（`@import "tailwindcss"` + `@plugin "daisyui"`）。

### 3.4 API 调用约定

- 所有请求头：`Authorization: token`（直接传裸 JWT，**不加 Bearer**）。
- token 从 `localStorage.getItem('token')` 读取；登录成功后写入 `localStorage.setItem('token', data.token)`。
- 表单提交错误处理：`if (!res.ok) throw new Error(data.detail || '操作失败')`。

## 4. Git 与提交规范

- 提交信息用中文，格式：`<类型>: <简述>`（类型：feat / fix / docs / refactor / test / chore）。
- 提交前检查：`git status`、`git diff`，确认没有误提交密钥、构建产物。
- 除非用户明确要求，不要执行 `git push`、`git rebase`、`git reset --hard` 等破坏性操作。
- `.gitignore` 已覆盖：`config/config.yml`、`.env`、`__pycache__`、`node_modules`、`frontend/build`、`src/static` 等。

## 5. 测试与验证清单

| 改动类型 | 必须验证 |
|----------|----------|
| 后端 Python | `make test`（或 `python test/run_all.py`） |
| 前端 Svelte | `cd frontend && npm run build` |
| 数据库相关 | 测试库运行 `ensure_schema` + 基本 CRUD |
| 认证相关 | 登录 → 获取 token → 携带 token 访问受保护接口 |

## 6. 常见坑（Pitfalls）

1. **登录页被布局拦截**：改 `+layout.svelte` 时务必保留 `isLoginPage` 分支，这是最容易回归的地方。
2. **Authorization 头格式**：本项目后端 `_get_user` 直接 `verify_token(authorization)`，传 `Bearer xxx` 会校验失败。新增接口时保持裸 token 约定。
3. **脱敏显示**：部分工具/终端会把 `token`、`Authorization: xxx` 之类内容脱敏显示为 `***`，不代表文件损坏。判断文件真实内容用 `git diff` 或 Python 读取。
4. **daisyUI 5**：CSS 插件通过 `@plugin "daisyui"` 引入（Tailwind v4 语法），不要用旧版 `@tailwind base/components/utilities`。
5. **Windows 环境**：本机为 Windows + git-bash。路径用 `/d/github/git_mcp_server` 风格；PowerShell 脚本在 `script/dockerrebuid.ps1`（注意文件名拼写是 `dockerrebuid`）。
6. **前端构建产物**：`npm run build` 输出到 `frontend/build`，server.py 会将其复制/挂载到 `src/static`。改完前端必须重新构建并重启后端才生效。
7. **static 根文件（favicon 等）**：`src/server.py` 的 SPA 回退会优先返回 `src/static/` 根目录下的真实文件（favicon.svg/png 等），找不到才回退 index.html。新增前端静态资源放到 `frontend/static/`，构建后会被复制到 `src/static/`。
8. **Authorization 头脱敏显示**：编辑器/终端可能把 `Authorization: token` 显示成 `***`，这是脱敏效果，不代表文件损坏；判断真实内容用 `git diff` 或 Python 读取。

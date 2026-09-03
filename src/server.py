"""
git_mcp_server 服务入口
"""
from fastapi import FastAPI, Request, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, select, insert, update, Table, MetaData
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import os
import time
import threading
import asyncio
import uuid
import json

from .config import Config
from .logging_utils import get_logger
from .admin.models import ensure_schema, create_default_admin
from .admin.web import build_admin_router
from .admin.auth import AuthService
from .mcp.tools import MCP_TOOLS
from .mcp.permissions import MCPPermissionChecker
from .gitops.repo_manager import GitRepoManager
from .security.client_ip import get_client_ip
from .security.ip_whitelist import IPWhitelistChecker
from .security.secret import decrypt_text


# ---- 全局变量 ----
_repo_manager: GitRepoManager = None
_logger = None
_sse_sessions: dict = {}


def _get_config() -> Config:
    return Config.load()


def _get_mcp_base_url(request: Request, cfg: Config) -> str:
    """生成客户端可访问的 MCP 基础地址，兼容反向代理终止 HTTPS。"""
    configured_url = (cfg.server.public_base_url or "").strip().rstrip("/")
    if configured_url:
        return configured_url

    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",", 1)[0].strip()
    scheme = forwarded_proto or request.url.scheme
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}".rstrip("/")


def _to_mcp_tool_result(result) -> dict:
    """把内部工具结果转换为 MCP tools/call 标准内容格式。"""
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        return result
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, default=str),
        }]
    }


# ---- 应用生命周期 ----

def create_app() -> FastAPI:
    global _repo_manager, _logger

    cfg = _get_config()
    _logger = get_logger("server", cfg.logging.dir)

    # 初始化仓库管理器
    _repo_manager = GitRepoManager(cfg.git_storage)

    # 初始化管理数据库
    admin_db_url = cfg.get_admin_db_url()
    engine = create_engine(admin_db_url, pool_pre_ping=True)
    ensure_schema(engine)
    from .admin.models import initialize_default_llm_configs
    initialize_default_llm_configs(engine)

    try:
        create_default_admin(engine, master_key=cfg.security.master_key)
    except Exception as e:
        _logger.warning(f"创建默认管理员跳过: {e}")

    # 权限检查器
    perm_checker = MCPPermissionChecker(engine)
    ip_checker = IPWhitelistChecker(engine)
    auth_service = AuthService(
        master_key=cfg.security.master_key,
        jwt_secret=cfg.security.jwt_secret,
        session_timeout=cfg.security.session_timeout
    )

    app = FastAPI(title="Git MCP Server", version="0.1.0")

    # ---- 挂载静态文件 (前端编译结果) ----
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/admin/_app", StaticFiles(directory=os.path.join(static_dir, "_app")), name="sveltekit_app")
        _logger.info(f"Mounted frontend static: {static_dir}")

    # 挂载管理后台 API (必须在静态文件挂载之后, 确保 API 优先匹配)
    admin_router = build_admin_router(cfg, repo_manager=_repo_manager)
    app.include_router(admin_router)

    # ---- 通用路由 ----

    @app.get("/", response_class=RedirectResponse)
    async def root():
        return RedirectResponse(url="/admin/login")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "git_mcp_server"}

    # ---- MCP SSE 端点 ----

    @app.post("/mcp/query")
    @app.post("/mcp/message")
    @app.post("/mcp/sse")
    async def mcp_query(request: Request, x_access_key: str = Header(None, alias="X-Access-Key"),
                        session_id: str = Query(None)):
        """MCP JSON-RPC 查询端点"""
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        req_id = body.get("id")

        # 验证 access key
        session = _sse_sessions.get(session_id) if session_id else None
        access_key = x_access_key or body.get("access_key")
        if not access_key and session:
            access_key = session["access_key"]
        if not access_key:
            return JSONResponse({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32600, "message": "缺少 X-Access-Key"}
            }, status_code=400)

        # 检查 IP 白名单
        client_ip = get_client_ip(request)
        key_info = _get_key_info(engine, access_key)
        if not key_info:
            return JSONResponse({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": "无效或已禁用的访问密钥"}
            }, status_code=401)
        if not ip_checker.is_allowed(key_info["id"], client_ip):
            return JSONResponse({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32602, "message": f"IP {client_ip} 不在白名单中"}
            }, status_code=403)

        # 处理消息，统一生成 JSON-RPC 响应
        response_dict = None
        try:
            if method == "initialize":
                client_protocol_version = params.get("protocolVersion", "2024-11-05")
                result = {
                    "protocolVersion": client_protocol_version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "git-mcp-server",
                        "version": "1.0.0"
                    }
                }
            elif method in ("initialized", "notifications/initialized"):
                result = None
            elif method in ("ping", "notifications/ping"):
                result = {}
            elif method == "resources/list":
                result = {"resources": []}
            elif method == "resources/templates/list":
                result = {"resourceTemplates": []}
            elif method == "prompts/list":
                result = {"prompts": []}
            elif method == "roots/list":
                result = {"roots": []}
            elif method.startswith("notifications/"):
                result = None
            elif method == "tools/list":
                result = {"tools": [t.to_dict() for t in MCP_TOOLS]}
            elif method == "tools/call":
                result = _to_mcp_tool_result(
                    await _handle_mcp_tool(
                        engine, cfg, access_key, params.get("name"),
                        params.get("arguments", {}), client_ip
                    )
                )
            else:
                return JSONResponse({
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"未知方法: {method}"}
                })
            response_dict = {"jsonrpc": "2.0", "id": req_id, "result": result}
        except HTTPException as e:
            response_dict = {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": e.status_code, "message": e.detail}
            }
        except Exception as e:
            _logger.error(f"MCP 错误: {e}")
            response_dict = {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32603, "message": str(e)}
            }

        # SSE 传输模式下，通过流返回响应
        # MCP 通知没有 id，不需要 JSON-RPC 响应。
        if req_id is None:
            return Response(status_code=202)

        if session:
            await session["queue"].put(response_dict)
            return JSONResponse(response_dict)

        return JSONResponse(response_dict)

    @app.get("/mcp/sse")
    async def mcp_sse(request: Request, x_access_key: str = Header(None, alias="X-Access-Key")):
        """MCP SSE 端点（兼容 IDE 集成）"""
        access_key = x_access_key
        if not access_key:
            raise HTTPException(status_code=400, detail="缺少 X-Access-Key")

        # 校验 access key 权限
        key_info = _get_key_info(engine, access_key)
        if not key_info:
            raise HTTPException(status_code=401, detail="无效或已禁用的访问密钥")

        client_ip = get_client_ip(request)
        if not ip_checker.is_allowed(key_info["id"], client_ip):
            raise HTTPException(status_code=403, detail=f"IP {client_ip} 不在白名单中")

        session_id = uuid.uuid4().hex
        queue = asyncio.Queue()
        _sse_sessions[session_id] = {
            "queue": queue,
            "access_key": access_key,
        }

        base_url = _get_mcp_base_url(request, cfg)
        endpoint_url = f"{base_url}/mcp/message?session_id={session_id}"

        async def event_stream():
            try:
                # 发送 endpoint 事件，告知客户端消息 POST 地址
                yield f"event: endpoint\ndata: {endpoint_url}\n\n"
                while True:
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                _sse_sessions.pop(session_id, None)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.head("/mcp/sse")
    async def mcp_sse_head():
        """兼容客户端建立 SSE 连接前的 HEAD 探测。"""
        return Response(status_code=200)

    # ---- 前端 SPA 回退 ----

    @app.get("/admin/{path:path}")
    async def spa_fallback(path: str):
        """SPA 回退：非 API 路径返回前端 index.html"""
        # 跳过 API 路径
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        # static 根目录下的静态文件优先直接返回（favicon、logo 等）
        file_path = os.path.join(static_dir, path)
        if path and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        return HTMLResponse("<h1>前端未构建，请运行 cd frontend && npm run build</h1>")

    @app.get("/admin")
    async def admin_index():
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        return HTMLResponse("<h1>前端未构建</h1>")

    return app


# ---- 工具处理 ----

def _get_key_info(engine, access_key: str) -> dict:
    """根据 access_key 获取密钥信息"""
    from sqlalchemy import Table, MetaData, select
    from sqlalchemy.orm import Session
    meta = MetaData()
    access_keys = Table("access_keys", meta, autoload_with=engine)
    with Session(engine) as session:
        row = session.execute(
            select(access_keys).where(
                access_keys.c.ak == access_key,
                access_keys.c.enabled == True  # noqa: E712
            )
        ).mappings().first()
        return dict(row) if row else None


def _get_repo_credential(engine, repo_id: int) -> tuple:
    """获取仓库的凭据信息（解密后）"""
    cfg = _get_config()
    from sqlalchemy import Table, MetaData, select
    from sqlalchemy.orm import Session
    meta = MetaData()
    repos = Table("git_repos", meta, autoload_with=engine)
    creds = Table("git_credentials", meta, autoload_with=engine)
    with Session(engine) as session:
        repo = session.execute(
            select(repos).where(repos.c.id == repo_id)
        ).mappings().first()
        if not repo:
            return None, None
        if repo.get("credential_id"):
            cred = session.execute(
                select(creds).where(creds.c.id == repo["credential_id"])
            ).mappings().first()
            if cred:
                username = decrypt_text(cred.get("username_enc") or "", cfg.security.master_key)
                password = decrypt_text(cred.get("password_enc") or "", cfg.security.master_key)
                return username or None, password or None
    return None, None


async def _handle_mcp_tool(engine, cfg: Config, access_key: str,
                            tool_name: str, arguments: dict,
                            client_ip: str) -> dict:
    """处理 MCP 工具调用"""
    from sqlalchemy import Table, MetaData, select
    from sqlalchemy.orm import Session
    meta = MetaData()
    repos_table = Table("git_repos", meta, autoload_with=engine)
    audit_logs = Table("audit_logs", meta, autoload_with=engine)

    perm_checker = MCPPermissionChecker(engine)

    t0 = time.time()
    result = None
    status = "success"
    error_msg = None
    repo_id = arguments.get("repo_id")
    repo_name = None
    target = None

    if repo_id:
        _logger.info(f"MCP 工具调用: {tool_name}, repo_id={repo_id}, access_key={access_key[:8]}...")

    try:
        if tool_name == "list_repos":
            result = await _handle_list_repos(engine, access_key, arguments)

        elif tool_name == "list_branches":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_list_branches(engine, cfg, repo_id)
            target = f"branches (repo_id={repo_id})"

        elif tool_name == "list_tags":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_list_tags(engine, cfg, repo_id)
            target = f"tags (repo_id={repo_id})"

        elif tool_name == "list_tree":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_list_tree(engine, cfg, repo_id, arguments)
            target = arguments.get("path", "/")

        elif tool_name == "read_file":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_read_file(engine, cfg, repo_id, arguments)
            target = arguments.get("path", "")

        elif tool_name == "git_log":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_git_log(engine, cfg, repo_id, arguments)
            target = f"log (repo_id={repo_id})"

        elif tool_name == "git_show":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_git_show(engine, cfg, repo_id, arguments)
            target = arguments.get("commit_sha", "")

        elif tool_name == "git_diff":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_git_diff(engine, cfg, repo_id, arguments)
            target = f"{arguments.get('ref_a', '')}..{arguments.get('ref_b', '')}"

        elif tool_name == "git_blame":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_git_blame(engine, cfg, repo_id, arguments)
            target = arguments.get("path", "")

        elif tool_name == "git_grep":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_git_grep(engine, cfg, repo_id, arguments)
            target = arguments.get("pattern", "")

        elif tool_name == "analyze_code":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_analyze_code(engine, cfg, repo_id, arguments, access_key)
            target = arguments.get("path", "")

        elif tool_name == "review_diff":
            perm_checker.check_permission(access_key, repo_id)
            result = await _handle_review_diff(engine, cfg, repo_id, arguments, access_key)
            target = f"{arguments.get('ref_a', '')}..{arguments.get('ref_b', '')}"

        else:
            raise HTTPException(status_code=400, detail=f"未知工具: {tool_name}")

    except HTTPException:
        status = "denied"
        raise
    except Exception as e:
        status = "error"
        error_msg = str(e)
        _logger.error(f"工具 {tool_name} 执行失败: {e}")
        raise

    finally:
        # 记录审计日志
        duration_ms = int((time.time() - t0) * 1000)
        try:
            if repo_id:
                with Session(engine) as session:
                    repo_row = session.execute(
                        select(repos_table).where(repos_table.c.id == repo_id)
                    ).mappings().first()
                    if repo_row:
                        repo_name = repo_row["name"]
        except Exception:
            pass

        _log_audit(engine, audit_logs, access_key, client_ip, repo_id,
                   repo_name, tool_name, target, duration_ms, status, error_msg)

    return result


# ---- 日志 ----

def _log_audit(engine, audit_logs, access_key: str, client_ip: str,
               repo_id: int, repo_name: str, operation: str,
               target: str, duration_ms: int, status: str, error_msg: str):
    """写入审计日志"""
    try:
        with Session(engine) as session:
            session.execute(
                insert(audit_logs).values(
                    access_key=access_key,
                    client_ip=client_ip,
                    repo_id=repo_id,
                    repo_name=repo_name,
                    operation=operation,
                    target=str(target)[:512] if target else None,
                    duration_ms=duration_ms,
                    status=status,
                    error_message=error_msg[:1000] if error_msg else None,
                )
            )
            session.commit()
    except Exception as e:
        _logger.error(f"审计日志写入失败: {e}")


# ---- 工具处理函数 ----

def _run_git_sync(fn, *args, **kwargs):
    """将同步 Git 操作放入线程池执行，避免阻塞事件循环"""
    return asyncio.to_thread(fn, *args, **kwargs)

async def _handle_list_repos(engine, access_key: str, arguments: dict) -> dict:
    """列出当前 Key 可访问的仓库"""
    from sqlalchemy import Table, MetaData, select, and_
    from sqlalchemy.orm import Session
    meta = MetaData()
    access_keys = Table("access_keys", meta, autoload_with=engine)
    permissions = Table("git_permissions", meta, autoload_with=engine)
    repos = Table("git_repos", meta, autoload_with=engine)
    search = arguments.get("search", "")

    with Session(engine) as session:
        key_row = session.execute(
            select(access_keys).where(
                access_keys.c.ak == access_key,
                access_keys.c.enabled == True  # noqa: E712
            )
        ).mappings().first()
        if not key_row:
            raise HTTPException(status_code=401, detail="无效密钥")

        key_id = key_row["id"]
        stmt = select(
            repos.c.id, repos.c.name, repos.c.url,
            repos.c.main_branch, repos.c.description,
            repos.c.enabled, repos.c.allow_write, repos.c.allow_push,
            permissions.c.access_level,
            permissions.c.branch_pattern, permissions.c.path_pattern
        ).join(
            permissions,
            and_(
                permissions.c.repo_id == repos.c.id,
                permissions.c.key_id == key_id
            )
        ).where(repos.c.enabled == True)  # noqa: E712

        if search:
            stmt = stmt.where(repos.c.name.ilike(f"%{search}%"))

        rows = session.execute(stmt).mappings().all()

    return {
        "repos": [
            {
                "id": r["id"],
                "name": r["name"],
                "url": r["url"],
                "main_branch": r["main_branch"],
                "description": r["description"],
                "access_level": r["access_level"],
                "branch_pattern": r["branch_pattern"],
                "path_pattern": r["path_pattern"],
            }
            for r in rows
        ]
    }


async def _handle_list_branches(engine, cfg: Config, repo_id: int) -> dict:
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)
    branches = await _run_git_sync(git_ops.list_branches, repo)
    return {"branches": branches}


async def _handle_list_tags(engine, cfg: Config, repo_id: int) -> dict:
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)
    tags = await _run_git_sync(git_ops.list_tags, repo)
    return {"tags": tags}


async def _handle_list_tree(engine, cfg: Config, repo_id: int,
                             arguments: dict) -> dict:
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)
    items = await _run_git_sync(git_ops.list_tree,
        repo,
        path=arguments.get("path", ""),
        ref=arguments.get("ref", "HEAD"),
        recursive=arguments.get("recursive", True),
    )
    _logger.info(f"列出目录: repo={repo_info['name']}, path={arguments.get('path', '/')}, "
                 f"ref={arguments.get('ref', 'HEAD')}, items={len(items)}")
    return {"tree": items}


async def _handle_read_file(engine, cfg: Config, repo_id: int,
                             arguments: dict) -> dict:
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)
    result = await _run_git_sync(git_ops.read_file,
        repo,
        path=arguments["path"],
        ref=arguments.get("ref", "HEAD"),
        start_line=arguments.get("start_line"),
        end_line=arguments.get("end_line"),
    )
    _logger.info(f"读取文件: repo={repo_info['name']}, path={arguments['path']}, "
                 f"ref={arguments.get('ref', 'HEAD')}, size={result.get('size', 0)} bytes, "
                 f"lines={result.get('total_lines', 0)}")
    return result


async def _handle_git_log(engine, cfg: Config, repo_id: int,
                           arguments: dict) -> dict:
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)
    commits = await _run_git_sync(git_ops.git_log,
        repo,
        ref=arguments.get("ref", "HEAD"),
        path=arguments.get("path"),
        max_count=arguments.get("max_count", 50),
        since=arguments.get("since"),
        until=arguments.get("until"),
    )
    return {"commits": commits}


async def _handle_git_show(engine, cfg: Config, repo_id: int,
                            arguments: dict) -> dict:
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)
    return await _run_git_sync(git_ops.git_show, repo, commit_sha=arguments["commit_sha"])


async def _handle_git_diff(engine, cfg: Config, repo_id: int,
                             arguments: dict) -> dict:
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)
    return await _run_git_sync(git_ops.git_diff,
        repo,
        ref_a=arguments["ref_a"],
        ref_b=arguments["ref_b"],
        path=arguments.get("path"),
    )


async def _handle_git_blame(engine, cfg: Config, repo_id: int,
                             arguments: dict) -> dict:
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)
    lines = await _run_git_sync(git_ops.git_blame,
        repo,
        path=arguments["path"],
        ref=arguments.get("ref", "HEAD"),
        start_line=arguments.get("start_line"),
        end_line=arguments.get("end_line"),
    )
    return {"lines": lines}


async def _handle_git_grep(engine, cfg: Config, repo_id: int,
                            arguments: dict) -> dict:
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)
    matches = await _run_git_sync(git_ops.git_grep,
        repo,
        pattern=arguments["pattern"],
        path=arguments.get("path"),
        ref=arguments.get("ref", "HEAD"),
        ignore_case=arguments.get("ignore_case", False),
    )
    return {"matches": matches}


async def _handle_analyze_code(engine, cfg: Config, repo_id: int,
                                arguments: dict, access_key: str) -> dict:
    """使用 LLM 分析代码"""
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)

    file_info = await _run_git_sync(git_ops.read_file,
        repo, path=arguments["path"],
        ref=arguments.get("ref", "HEAD")
    )
    question = arguments["question"]

    # 获取激活的 LLM 配置
    llm_cfg = _get_active_llm(engine, cfg)
    if not llm_cfg:
        raise HTTPException(status_code=500, detail="未配置大模型")

    analysis = await _call_llm(llm_cfg, file_info["content"], question,
                                engine, access_key, "analyze_code", repo_id)
    return {"analysis": analysis, "file": file_info["path"],
            "ref": file_info["ref"]}


async def _handle_review_diff(engine, cfg: Config, repo_id: int,
                               arguments: dict, access_key: str) -> dict:
    """使用 LLM 审查代码差异"""
    from .gitops import git_operations as git_ops
    repo_info = _get_repo_info(engine, repo_id)
    username, password = _get_repo_credential(engine, repo_id)
    repo = await _run_git_sync(_repo_manager.get_repo, repo_id, repo_info["name"],
                                   repo_info["url"], username, password)

    diff_info = await _run_git_sync(git_ops.git_diff,
        repo, ref_a=arguments["ref_a"],
        ref_b=arguments["ref_b"], path=arguments.get("path")
    )

    diff_text = "\n".join(
        f"--- {d['old_path']}\n+++ {d['new_path']}\n{d['diff']}"
        for d in diff_info["diffs"]
    )

    llm_cfg = _get_active_llm(engine, cfg)
    if not llm_cfg:
        raise HTTPException(status_code=500, detail="未配置大模型")

    review = await _call_llm(
        llm_cfg, diff_text,
        "请审查以上代码差异，指出潜在问题、改进建议和安全风险。",
        engine, access_key, "review_diff", repo_id
    )
    return {"review": review, "stats": diff_info}


def _get_repo_info(engine, repo_id: int) -> dict:
    """获取仓库基本信息"""
    from sqlalchemy import Table, MetaData, select
    from sqlalchemy.orm import Session
    meta = MetaData()
    repos = Table("git_repos", meta, autoload_with=engine)
    with Session(engine) as session:
        row = session.execute(
            select(repos).where(repos.c.id == repo_id)
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail=f"仓库 ID {repo_id} 不存在")
        if not row["enabled"]:
            raise HTTPException(status_code=403, detail=f"仓库 {row['name']} 已禁用")
        return dict(row)


def _get_active_llm(engine, cfg: Config) -> dict:
    """获取当前激活的 LLM 配置"""
    from sqlalchemy import Table, MetaData, select
    from sqlalchemy.orm import Session
    meta = MetaData()
    llm_configs = Table("llm_configs", meta, autoload_with=engine)
    with Session(engine) as session:
        row = session.execute(
            select(llm_configs).where(llm_configs.c.is_active == True)  # noqa: E712
        ).mappings().first()
        if not row:
            return None
        api_key = decrypt_text(row.get("api_key_enc") or "", cfg.security.master_key)
        return {
            "id": row["id"],
            "provider": row["provider"],
            "base_url": row["base_url"],
            "api_key": api_key,
            "model_name": row["model_name"],
        }


async def _call_llm(llm_cfg: dict, code: str, question: str,
                    engine, access_key: str, tool_name: str,
                    repo_id: int = None) -> str:
    """调用大模型并记录日志"""
    from sqlalchemy import Table, MetaData, insert
    from sqlalchemy.orm import Session
    import httpx

    prompt = f"""你是一个资深代码审查专家。请分析以下代码并回答问题。

## 代码
```
{code[:8000]}
```

## 问题
{question}

请给出详细分析："""

    t0 = time.time()
    status = "success"
    error_msg = None
    prompt_tokens = 0
    completion_tokens = 0

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{llm_cfg['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {llm_cfg['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": llm_cfg["model_name"],
                    "messages": [
                        {"role": "system", "content": "你是一个资深代码审查专家。"},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 4096,
                }
            )
            if resp.status_code != 200:
                raise Exception(f"LLM API 错误: {resp.status_code} {resp.text}")

            data = resp.json()
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            content = data["choices"][0]["message"]["content"]

        return content

    except Exception as e:
        status = "error"
        error_msg = str(e)
        raise

    finally:
        duration_ms = int((time.time() - t0) * 1000)
        try:
            meta = MetaData()
            llm_call_logs = Table("llm_call_logs", meta, autoload_with=engine)
            with Session(engine) as session:
                session.execute(
                    insert(llm_call_logs).values(
                        access_key=access_key,
                        tool_name=tool_name,
                        repo_id=repo_id,
                        model_name=llm_cfg["model_name"],
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                        duration_ms=duration_ms,
                        status=status,
                        error_message=error_msg[:1000] if error_msg else None,
                    )
                )
                session.commit()
        except Exception as e:
            _logger.error(f"LLM 日志写入失败: {e}")


# ---- 入口 ----

if __name__ == "__main__":
    import uvicorn
    cfg = _get_config()
    app = create_app()
    uvicorn.run(app, host=cfg.server.host, port=cfg.server.port)

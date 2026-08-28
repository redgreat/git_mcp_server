"""
管理后台 API 路由
"""
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, select, insert, update, delete, text, Table, MetaData
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import os
import secrets

from ..config import Config
from ..logging_utils import get_logger
from .models import ensure_schema
from .auth import AuthService
from ..security.secret import encrypt_text, decrypt_text
from ..security.ip_whitelist import IPWhitelistChecker
from ..security.client_ip import get_client_ip


# ============ 请求模型 ============

class LoginRequest(BaseModel):
    username: str
    password: str


class CreateKeyRequest(BaseModel):
    ak: Optional[str] = None
    description: str = ""
    enabled: bool = True


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = ""
    role: str = "user"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str


class CreateRepoRequest(BaseModel):
    name: str
    url: str
    main_branch: str = "main"
    credential_id: Optional[int] = None
    enabled: bool = True
    allow_write: bool = False
    allow_push: bool = False
    description: str = ""


class UpdateRepoRequest(BaseModel):
    url: Optional[str] = None
    main_branch: Optional[str] = None
    credential_id: Optional[int] = None
    enabled: Optional[bool] = None
    allow_write: Optional[bool] = None
    allow_push: Optional[bool] = None
    description: Optional[str] = None


class CreateCredentialRequest(BaseModel):
    name: str
    auth_type: str = "https"
    username: Optional[str] = None
    password: Optional[str] = None
    ssh_key: Optional[str] = None
    description: str = ""


class UpdateCredentialRequest(BaseModel):
    auth_type: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssh_key: Optional[str] = None
    description: Optional[str] = None


class GrantPermissionRequest(BaseModel):
    key_id: int
    repo_id: int
    access_level: str = "read_only"
    branch_pattern: str = ".*"
    path_pattern: str = ".*"


class SaveIPWhitelistRequest(BaseModel):
    key_id: int
    entries: list = []  # [{"cidr": "192.168.1.0/24", "description": ""}]


class UpdateLLMConfigRequest(BaseModel):
    provider: Optional[str] = None
    base_url: str
    api_key: Optional[str] = None
    model_name: str


# ============ 路由构建 ============

def build_admin_router(cfg: Config, repo_manager=None):
    """创建管理后台路由"""
    router = APIRouter()
    logger = get_logger("admin", cfg.logging.dir)

    admin_db_url = cfg.get_admin_db_url()
    engine = create_engine(admin_db_url, pool_pre_ping=True)
    ensure_schema(engine)
    from .models import initialize_default_llm_configs
    initialize_default_llm_configs(engine)

    # 获取表引用
    from sqlalchemy import MetaData
    meta = MetaData()
    admin_users = Table("admin_users", meta, autoload_with=engine)
    access_keys = Table("access_keys", meta, autoload_with=engine)
    git_repos = Table("git_repos", meta, autoload_with=engine)
    git_credentials = Table("git_credentials", meta, autoload_with=engine)
    git_permissions = Table("git_permissions", meta, autoload_with=engine)
    ip_whitelist = Table("ip_whitelist", meta, autoload_with=engine)
    audit_logs = Table("audit_logs", meta, autoload_with=engine)
    system_logs = Table("system_logs", meta, autoload_with=engine)
    llm_configs = Table("llm_configs", meta, autoload_with=engine)
    llm_call_logs = Table("llm_call_logs", meta, autoload_with=engine)

    auth_service = AuthService(
        master_key=cfg.security.master_key,
        jwt_secret=cfg.security.jwt_secret,
        session_timeout=cfg.security.session_timeout
    )
    ip_checker = IPWhitelistChecker(engine)

    def _get_user(token: str):
        """从 token 获取用户信息"""
        if not token:
            raise HTTPException(status_code=401, detail="未提供认证令牌")
        return auth_service.verify_token(token)

    def _log_system(user: dict, operation: str, resource_type: str,
                    resource_id: int = None, details: dict = None,
                    client_ip: str = "unknown"):
        """记录系统操作日志"""
        try:
            with Session(engine) as session:
                session.execute(
                    insert(system_logs).values(
                        user_id=user.get("sub"),
                        username=user.get("username"),
                        operation=operation,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        details=details,
                        client_ip=client_ip,
                    )
                )
                session.commit()
        except Exception as e:
            logger.error(f"写入系统日志失败: {e}")

    # ========== 认证接口 ==========

    @router.post("/api/auth/login")
    def login(req: LoginRequest):
        return auth_service.login(engine, req.username, req.password)

    @router.post("/api/auth/change-password")
    def change_password(req: ChangePasswordRequest,
                         authorization: str = Header(None)):
        user = _get_user(authorization)
        with Session(engine) as session:
            u = session.execute(
                select(admin_users).where(admin_users.c.id == int(user["sub"]))
            ).mappings().first()
            if not u:
                raise HTTPException(status_code=404, detail="用户不存在")
            if not auth_service.verify_password(req.old_password, u["password_hash"]):
                raise HTTPException(status_code=400, detail="旧密码错误")
            new_hash = auth_service.hash_password(req.new_password)
            session.execute(
                update(admin_users).where(admin_users.c.id == u["id"])
                .values(password_hash=new_hash)
            )
            session.commit()
        return {"ok": True}

    @router.get("/api/auth/me")
    def me(authorization: str = Header(None)):
        return _get_user(authorization)

    # ========== 用户管理 ==========

    @router.get("/api/admin/users")
    def list_users(authorization: str = Header(None)):
        user = _get_user(authorization)
        auth_service.require_admin(user)
        with Session(engine) as session:
            rows = session.execute(
                select(admin_users).order_by(admin_users.c.id)
            ).mappings().all()
        return [{"id": r["id"], "username": r["username"], "email": r["email"],
                 "role": r["role"], "is_active": r["is_active"],
                 "created_at": str(r["created_at"])} for r in rows]

    @router.post("/api/admin/users")
    def create_user(req: CreateUserRequest, authorization: str = Header(None),
                    request: Request = None):
        user = _get_user(authorization)
        auth_service.require_admin(user)
        with Session(engine) as session:
            existing = session.execute(
                select(admin_users).where(admin_users.c.username == req.username)
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="用户名已存在")
            session.execute(
                insert(admin_users).values(
                    username=req.username,
                    password_hash=auth_service.hash_password(req.password),
                    email=req.email,
                    role=req.role,
                    is_active=True,
                )
            )
            session.commit()
        _log_system(user, "create_user", "admin_user", client_ip=get_client_ip(request))
        return {"ok": True}

    @router.put("/api/admin/users/{user_id}")
    def update_user(user_id: int, req: UpdateUserRequest,
                    authorization: str = Header(None), request: Request = None):
        user = _get_user(authorization)
        auth_service.require_admin(user)
        vals = {}
        if req.role is not None:
            vals["role"] = req.role
        if req.is_active is not None:
            vals["is_active"] = req.is_active
        if vals:
            with Session(engine) as session:
                session.execute(
                    update(admin_users).where(admin_users.c.id == user_id).values(**vals)
                )
                session.commit()
        _log_system(user, "update_user", "admin_user", user_id, vals,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    @router.put("/api/admin/users/{user_id}/reset-password")
    def reset_password(user_id: int, req: ResetPasswordRequest,
                       authorization: str = Header(None), request: Request = None):
        user = _get_user(authorization)
        auth_service.require_admin(user)
        with Session(engine) as session:
            session.execute(
                update(admin_users).where(admin_users.c.id == user_id)
                .values(password_hash=auth_service.hash_password(req.new_password))
            )
            session.commit()
        _log_system(user, "reset_password", "admin_user", user_id,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    # ========== Access Key 管理 ==========

    @router.get("/api/admin/keys")
    def list_keys(authorization: str = Header(None)):
        _get_user(authorization)
        with Session(engine) as session:
            rows = session.execute(
                select(access_keys).order_by(access_keys.c.id)
            ).mappings().all()
        return [{"id": r["id"], "ak": r["ak"], "description": r["description"],
                 "enabled": r["enabled"], "created_at": str(r["created_at"])}
                for r in rows]

    @router.post("/api/admin/keys")
    def create_key(req: CreateKeyRequest, authorization: str = Header(None),
                   request: Request = None):
        user = _get_user(authorization)
        ak = req.ak or f"git_{secrets.token_hex(16)}"
        with Session(engine) as session:
            result = session.execute(
                insert(access_keys).values(
                    ak=ak,
                    description=req.description,
                    enabled=req.enabled,
                    created_by=int(user["sub"]),
                )
            )
            session.commit()
            key_id = result.inserted_primary_key[0]
        _log_system(user, "create_key", "access_key", key_id,
                    {"ak": ak}, client_ip=get_client_ip(request))
        return {"ok": True, "id": key_id, "ak": ak}

    @router.put("/api/admin/keys/{key_id}")
    def update_key(key_id: int, req: CreateKeyRequest,
                   authorization: str = Header(None), request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            session.execute(
                update(access_keys).where(access_keys.c.id == key_id)
                .values(description=req.description, enabled=req.enabled)
            )
            session.commit()
        _log_system(user, "update_key", "access_key", key_id,
                    {"enabled": req.enabled}, client_ip=get_client_ip(request))
        return {"ok": True}

    @router.delete("/api/admin/keys/{key_id}")
    def delete_key(key_id: int, authorization: str = Header(None),
                   request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            session.execute(delete(access_keys).where(access_keys.c.id == key_id))
            session.execute(delete(git_permissions).where(git_permissions.c.key_id == key_id))
            session.execute(delete(ip_whitelist).where(ip_whitelist.c.key_id == key_id))
            session.commit()
        _log_system(user, "delete_key", "access_key", key_id,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    # ========== Git Credential 管理 ==========

    @router.get("/api/admin/credentials")
    def list_credentials(authorization: str = Header(None)):
        _get_user(authorization)
        with Session(engine) as session:
            rows = session.execute(
                select(git_credentials).order_by(git_credentials.c.id)
            ).mappings().all()
        return [{"id": r["id"], "name": r["name"], "auth_type": r["auth_type"],
                 "description": r["description"],
                 "username": decrypt_text(r.get("username_enc") or "", cfg.security.master_key),
                 "has_username": bool(r.get("username_enc")),
                 "has_password": bool(r.get("password_enc")),
                 "has_ssh_key": bool(r.get("ssh_key_enc")),
                 "created_at": str(r["created_at"])}
                for r in rows]

    @router.post("/api/admin/credentials")
    def create_credential(req: CreateCredentialRequest,
                          authorization: str = Header(None),
                          request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            result = session.execute(
                insert(git_credentials).values(
                    name=req.name,
                    auth_type=req.auth_type,
                    username_enc=encrypt_text(req.username or "", cfg.security.master_key),
                    password_enc=encrypt_text(req.password or "", cfg.security.master_key),
                    ssh_key_enc=encrypt_text(req.ssh_key or "", cfg.security.master_key),
                    description=req.description,
                )
            )
            session.commit()
            cred_id = result.inserted_primary_key[0]
        _log_system(user, "create_credential", "credential", cred_id,
                    {"name": req.name, "auth_type": req.auth_type},
                    client_ip=get_client_ip(request))
        return {"ok": True, "id": cred_id}

    @router.put("/api/admin/credentials/{cred_id}")
    def update_credential(cred_id: int, req: UpdateCredentialRequest,
                          authorization: str = Header(None),
                          request: Request = None):
        user = _get_user(authorization)
        vals = {}
        if req.auth_type is not None:
            vals["auth_type"] = req.auth_type
        if req.username is not None:
            vals["username_enc"] = encrypt_text(req.username, cfg.security.master_key)
        if req.password is not None:
            vals["password_enc"] = encrypt_text(req.password, cfg.security.master_key)
        if req.ssh_key is not None:
            vals["ssh_key_enc"] = encrypt_text(req.ssh_key, cfg.security.master_key)
        if req.description is not None:
            vals["description"] = req.description
        if vals:
            with Session(engine) as session:
                session.execute(
                    update(git_credentials).where(git_credentials.c.id == cred_id).values(**vals)
                )
                session.commit()
        _log_system(user, "update_credential", "credential", cred_id,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    @router.delete("/api/admin/credentials/{cred_id}")
    def delete_credential(cred_id: int, authorization: str = Header(None),
                          request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            session.execute(delete(git_credentials).where(git_credentials.c.id == cred_id))
            session.commit()
        _log_system(user, "delete_credential", "credential", cred_id,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    # ========== Git Repo 管理 ==========

    @router.get("/api/admin/repos")
    def list_repos(authorization: str = Header(None)):
        _get_user(authorization)
        with Session(engine) as session:
            rows = session.execute(
                select(git_repos).order_by(git_repos.c.id)
            ).mappings().all()
        return [{"id": r["id"], "name": r["name"], "url": r["url"],
                 "main_branch": r["main_branch"],
                 "credential_id": r["credential_id"],
                 "enabled": r["enabled"],
                 "allow_write": r["allow_write"],
                 "allow_push": r["allow_push"],
                 "description": r["description"],
                 "last_fetched_at": str(r["last_fetched_at"]) if r.get("last_fetched_at") else None,
                 "created_at": str(r["created_at"])}
                for r in rows]

    @router.post("/api/admin/repos")
    def create_repo(req: CreateRepoRequest, authorization: str = Header(None),
                    request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            result = session.execute(
                insert(git_repos).values(
                    name=req.name,
                    url=req.url,
                    main_branch=req.main_branch,
                    credential_id=req.credential_id,
                    enabled=req.enabled,
                    allow_write=req.allow_write,
                    allow_push=req.allow_push,
                    description=req.description,
                )
            )
            session.commit()
            repo_id = result.inserted_primary_key[0]
        _log_system(user, "create_repo", "repo", repo_id,
                    {"name": req.name, "url": req.url},
                    client_ip=get_client_ip(request))
        return {"ok": True, "id": repo_id}

    @router.put("/api/admin/repos/{repo_id}")
    def update_repo(repo_id: int, req: UpdateRepoRequest,
                    authorization: str = Header(None), request: Request = None):
        user = _get_user(authorization)
        vals = {}
        for k in ["url", "main_branch", "credential_id", "enabled",
                   "allow_write", "allow_push", "description"]:
            v = getattr(req, k, None)
            if v is not None:
                vals[k] = v
        if vals:
            with Session(engine) as session:
                session.execute(
                    update(git_repos).where(git_repos.c.id == repo_id).values(**vals)
                )
                session.commit()
        _log_system(user, "update_repo", "repo", repo_id, vals,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    @router.delete("/api/admin/repos/{repo_id}")
    def delete_repo(repo_id: int, authorization: str = Header(None),
                    request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            session.execute(delete(git_repos).where(git_repos.c.id == repo_id))
            session.execute(delete(git_permissions).where(git_permissions.c.repo_id == repo_id))
            session.commit()
        _log_system(user, "delete_repo", "repo", repo_id,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    @router.post("/api/admin/repos/{repo_id}/fetch")
    def fetch_repo(repo_id: int, authorization: str = Header(None),
                   request: Request = None):
        """手动拉取仓库最新代码（首次会触发克隆）"""
        from ..server import _get_repo_credential
        from sqlalchemy import func as sa_func

        if repo_manager is None:
            raise HTTPException(status_code=500, detail="仓库管理器未初始化")

        user = _get_user(authorization)
        with Session(engine) as session:
            row = session.execute(
                select(git_repos).where(git_repos.c.id == repo_id)
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="仓库不存在")
            repo_name = row["name"]
            repo_url = row["url"]

        username, password = _get_repo_credential(engine, repo_id)

        try:
            status = repo_manager.get_repo_status(repo_id)
            if status:
                # 已缓存：强制 fetch 并统计
                result = repo_manager.fetch_and_report(repo_id, username, password)
                if result["error"]:
                    raise HTTPException(status_code=500, detail=f"拉取失败: {result['error']}")
                message = f"拉取完成：{result['fetched']} 个引用，{result['updated']} 个有更新"
                details = result.get("details", [])
            else:
                # 未缓存：触发首次克隆（等价于拉到最新）
                repo_manager.get_repo(repo_id, repo_name, repo_url, username, password)
                message = "首次克隆完成，已获取最新代码"
                details = []
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"拉取失败: {e}")

        with Session(engine) as session:
            session.execute(
                update(git_repos).where(git_repos.c.id == repo_id)
                .values(last_fetched_at=sa_func.now())
            )
            session.commit()

        _log_system(user, "fetch_repo", "repo", repo_id,
                    {"name": repo_name}, client_ip=get_client_ip(request))
        return {"ok": True, "message": message, "details": details}

    # ========== 权限分配 ==========

    @router.get("/api/admin/permissions")
    def list_permissions(key_id: Optional[int] = None,
                         repo_id: Optional[int] = None,
                         authorization: str = Header(None)):
        _get_user(authorization)
        with Session(engine) as session:
            stmt = select(git_permissions)
            if key_id:
                stmt = stmt.where(git_permissions.c.key_id == key_id)
            if repo_id:
                stmt = stmt.where(git_permissions.c.repo_id == repo_id)
            rows = session.execute(stmt.order_by(git_permissions.c.id)).mappings().all()
        return [{"id": r["id"], "key_id": r["key_id"], "repo_id": r["repo_id"],
                 "access_level": r["access_level"],
                 "branch_pattern": r["branch_pattern"],
                 "path_pattern": r["path_pattern"],
                 "created_at": str(r["created_at"])}
                for r in rows]

    @router.post("/api/admin/permissions")
    def grant_permission(req: GrantPermissionRequest,
                         authorization: str = Header(None),
                         request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            # 检查是否已存在
            existing = session.execute(
                select(git_permissions).where(
                    git_permissions.c.key_id == req.key_id,
                    git_permissions.c.repo_id == req.repo_id
                )
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="该 Key 已拥有此仓库的权限")

            result = session.execute(
                insert(git_permissions).values(
                    key_id=req.key_id,
                    repo_id=req.repo_id,
                    access_level=req.access_level,
                    branch_pattern=req.branch_pattern,
                    path_pattern=req.path_pattern,
                )
            )
            session.commit()
            perm_id = result.inserted_primary_key[0]
        _log_system(user, "grant_permission", "permission", perm_id,
                    {"key_id": req.key_id, "repo_id": req.repo_id,
                     "access_level": req.access_level},
                    client_ip=get_client_ip(request))
        return {"ok": True, "id": perm_id}

    @router.put("/api/admin/permissions/{perm_id}")
    def update_permission(perm_id: int, req: GrantPermissionRequest,
                          authorization: str = Header(None),
                          request: Request = None):
        user = _get_user(authorization)
        vals = {}
        if req.access_level is not None:
            vals["access_level"] = req.access_level
        if req.branch_pattern is not None:
            vals["branch_pattern"] = req.branch_pattern
        if req.path_pattern is not None:
            vals["path_pattern"] = req.path_pattern
        if vals:
            with Session(engine) as session:
                session.execute(
                    update(git_permissions).where(git_permissions.c.id == perm_id).values(**vals)
                )
                session.commit()
        _log_system(user, "update_permission", "permission", perm_id, vals,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    @router.delete("/api/admin/permissions/{perm_id}")
    def revoke_permission(perm_id: int, authorization: str = Header(None),
                          request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            session.execute(delete(git_permissions).where(git_permissions.c.id == perm_id))
            session.commit()
        _log_system(user, "revoke_permission", "permission", perm_id,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    # ========== IP 白名单 ==========

    @router.get("/api/admin/whitelist/{key_id}")
    def get_whitelist(key_id: int, authorization: str = Header(None)):
        _get_user(authorization)
        with Session(engine) as session:
            rows = session.execute(
                select(ip_whitelist).where(ip_whitelist.c.key_id == key_id)
            ).mappings().all()
        return [{"id": r["id"], "cidr": r["cidr"], "description": r["description"],
                 "created_at": str(r["created_at"])} for r in rows]

    @router.post("/api/admin/whitelist")
    def save_whitelist(req: SaveIPWhitelistRequest,
                       authorization: str = Header(None),
                       request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            # 清除旧的白名单
            session.execute(delete(ip_whitelist).where(ip_whitelist.c.key_id == req.key_id))
            # 插入新的
            for entry in req.entries:
                session.execute(
                    insert(ip_whitelist).values(
                        key_id=req.key_id,
                        cidr=entry["cidr"],
                        description=entry.get("description", ""),
                    )
                )
            session.commit()
        _log_system(user, "update_whitelist", "ip_whitelist", req.key_id,
                    {"entries": req.entries}, client_ip=get_client_ip(request))
        return {"ok": True}

    # ========== 审计日志查询 ==========

    @router.get("/api/admin/audit-logs")
    def list_audit_logs(access_key: Optional[str] = None,
                        repo_id: Optional[int] = None,
                        operation: Optional[str] = None,
                        status: Optional[str] = None,
                        limit: int = 100,
                        authorization: str = Header(None)):
        _get_user(authorization)
        with Session(engine) as session:
            stmt = select(audit_logs).order_by(audit_logs.c.timestamp.desc()).limit(min(limit, 500))
            if access_key:
                stmt = stmt.where(audit_logs.c.access_key == access_key)
            if repo_id:
                stmt = stmt.where(audit_logs.c.repo_id == repo_id)
            if operation:
                stmt = stmt.where(audit_logs.c.operation == operation)
            if status:
                stmt = stmt.where(audit_logs.c.status == status)
            rows = session.execute(stmt).mappings().all()
        return [{"id": r["id"], "timestamp": str(r["timestamp"]),
                 "access_key": r["access_key"], "client_ip": r["client_ip"],
                 "repo_id": r["repo_id"], "repo_name": r.get("repo_name"),
                 "operation": r["operation"], "target": r["target"],
                 "duration_ms": r["duration_ms"], "status": r["status"],
                 "error_message": r["error_message"]}
                for r in rows]

    # ========== 系统操作日志查询 ==========

    @router.get("/api/admin/system-logs")
    def list_system_logs(limit: int = 100, authorization: str = Header(None)):
        user = _get_user(authorization)
        auth_service.require_admin(user)
        with Session(engine) as session:
            rows = session.execute(
                select(system_logs).order_by(system_logs.c.timestamp.desc()).limit(min(limit, 500))
            ).mappings().all()
        return [{"id": r["id"], "timestamp": str(r["timestamp"]),
                 "username": r["username"], "operation": r["operation"],
                 "resource_type": r["resource_type"], "resource_id": r["resource_id"],
                 "details": str(r.get("details")) if r.get("details") else None,
                 "client_ip": r["client_ip"]}
                for r in rows]

    # ========== LLM 配置管理 ==========

    @router.get("/api/admin/llm-configs")
    def list_llm_configs(authorization: str = Header(None)):
        _get_user(authorization)
        with Session(engine) as session:
            rows = session.execute(
                select(llm_configs).order_by(llm_configs.c.id)
            ).mappings().all()
        return [{"id": r["id"], "provider": r["provider"],
                 "base_url": r["base_url"], "model_name": r["model_name"],
                 "is_active": r["is_active"],
                 "has_api_key": bool(r.get("api_key_enc"))}
                for r in rows]

    @router.put("/api/admin/llm-configs/{config_id}")
    def update_llm_config(config_id: int, req: UpdateLLMConfigRequest,
                          authorization: str = Header(None),
                          request: Request = None):
        user = _get_user(authorization)
        vals = {"base_url": req.base_url, "model_name": req.model_name}
        if req.provider:
            vals["provider"] = req.provider
        if req.api_key:
            vals["api_key_enc"] = encrypt_text(req.api_key, cfg.security.master_key)
        with Session(engine) as session:
            # 换提供商时检查重名
            if req.provider:
                dup = session.execute(
                    select(llm_configs).where(
                        llm_configs.c.provider == req.provider,
                        llm_configs.c.id != config_id
                    )
                ).first()
                if dup:
                    raise HTTPException(status_code=400, detail=f"提供商 {req.provider} 已存在")
            session.execute(
                update(llm_configs).where(llm_configs.c.id == config_id).values(**vals)
            )
            session.commit()
        _log_system(user, "update_llm", "llm_config", config_id,
                    {"model_name": req.model_name},
                    client_ip=get_client_ip(request))
        return {"ok": True}

    @router.post("/api/admin/llm-configs")
    def create_llm_config(req: UpdateLLMConfigRequest,
                          authorization: str = Header(None),
                          request: Request = None):
        user = _get_user(authorization)
        if not req.provider:
            raise HTTPException(status_code=400, detail="请选择模型提供商")
        vals = {"provider": req.provider, "base_url": req.base_url, "model_name": req.model_name}
        if req.api_key:
            vals["api_key_enc"] = encrypt_text(req.api_key, cfg.security.master_key)
        with Session(engine) as session:
            existing = session.execute(
                select(llm_configs).where(llm_configs.c.provider == req.provider)
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"提供商 {req.provider} 已存在，可直接编辑")
            result = session.execute(insert(llm_configs).values(**vals))
            session.commit()
            config_id = result.inserted_primary_key[0]
        _log_system(user, "create_llm", "llm_config", config_id,
                    {"provider": req.provider, "model_name": req.model_name},
                    client_ip=get_client_ip(request))
        return {"ok": True, "id": config_id}

    @router.delete("/api/admin/llm-configs/{config_id}")
    def delete_llm_config(config_id: int, authorization: str = Header(None),
                          request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            row = session.execute(
                select(llm_configs).where(llm_configs.c.id == config_id)
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="配置不存在")
            if row["is_active"]:
                raise HTTPException(status_code=400, detail="请先激活其他配置后再删除当前配置")
            session.execute(delete(llm_configs).where(llm_configs.c.id == config_id))
            session.commit()
        _log_system(user, "delete_llm", "llm_config", config_id,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    @router.post("/api/admin/llm-configs/{config_id}/activate")
    def activate_llm_config(config_id: int, authorization: str = Header(None),
                            request: Request = None):
        user = _get_user(authorization)
        with Session(engine) as session:
            # 先全部停用
            session.execute(update(llm_configs).values(is_active=False))
            # 激活选中
            session.execute(
                update(llm_configs).where(llm_configs.c.id == config_id)
                .values(is_active=True)
            )
            session.commit()
        _log_system(user, "activate_llm", "llm_config", config_id,
                    client_ip=get_client_ip(request))
        return {"ok": True}

    # ========== LLM 调用日志查询 ==========

    @router.get("/api/admin/llm-logs")
    def list_llm_logs(access_key: Optional[str] = None,
                      limit: int = 100,
                      authorization: str = Header(None)):
        _get_user(authorization)
        with Session(engine) as session:
            stmt = select(llm_call_logs).order_by(
                llm_call_logs.c.timestamp.desc()
            ).limit(min(limit, 500))
            if access_key:
                stmt = stmt.where(llm_call_logs.c.access_key == access_key)
            rows = session.execute(stmt).mappings().all()
        return [{"id": r["id"], "timestamp": str(r["timestamp"]),
                 "access_key": r["access_key"], "tool_name": r["tool_name"],
                 "model_name": r["model_name"],
                 "prompt_tokens": r["prompt_tokens"],
                 "completion_tokens": r["completion_tokens"],
                 "total_tokens": r["total_tokens"],
                 "duration_ms": r["duration_ms"],
                 "status": r["status"]}
                for r in rows]

    # ========== 版本信息 ==========

    @router.get("/api/version")
    def version():
        """返回当前应用版本号"""
        # 优先从版本文件读取（Docker 构建时注入）
        version_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'version.txt')
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                ver = f.read().strip()
                if ver:
                    return {"version": ver}
        # 备选：从环境变量或默认值
        return {"version": os.getenv("APP_VERSION", "v0.1.0")}

    # ========== 仪表盘 ==========

    @router.get("/api/admin/dashboard")
    def dashboard(authorization: str = Header(None)):
        _get_user(authorization)
        with Session(engine) as session:
            total_keys = session.execute(
                select(access_keys.c.id)
            ).fetchall()
            total_repos = session.execute(
                select(git_repos.c.id)
            ).fetchall()
            total_users = session.execute(
                select(admin_users.c.id)
            ).fetchall()
            recent_ops = session.execute(
                select(audit_logs).order_by(
                    audit_logs.c.timestamp.desc()
                ).limit(10)
            ).mappings().all()

        return {
            "total_keys": len(total_keys),
            "total_repos": len(total_repos),
            "total_users": len(total_users),
            "recent_operations": [
                {"timestamp": str(r["timestamp"]),
                 "access_key": r["access_key"],
                 "operation": r["operation"],
                 "target": r["target"],
                 "status": r["status"]}
                for r in recent_ops
            ],
        }

    return router

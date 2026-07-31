"""
管理数据库表结构定义（PostgreSQL）
"""
from sqlalchemy import (
    Table, Column, Integer, String, Boolean, ForeignKey, MetaData,
    Text, DateTime, BigInteger, JSON
)
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func


def ensure_schema(engine: Engine):
    """初始化管理数据库表结构"""
    meta = MetaData()

    # === 用户表（Web管理端登录） ===
    Table(
        "admin_users", meta,
        Column("id", Integer, primary_key=True, comment="用户ID"),
        Column("username", String(100), nullable=False, unique=True, comment="登录用户名"),
        Column("password_hash", String(255), nullable=False, comment="密码哈希值(bcrypt+pepper)"),
        Column("email", String(255), nullable=True, comment="邮箱地址"),
        Column("role", String(20), nullable=False, server_default="user",
               index=True, comment="角色: admin=管理员, user=普通用户"),
        Column("is_active", Boolean, default=True, index=True, comment="账号是否启用"),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), comment="创建时间"),
        Column("updated_at", DateTime(timezone=True), onupdate=func.now(), comment="最后更新时间"),
    )

    # === 访问密钥表 ===
    Table(
        "access_keys", meta,
        Column("id", Integer, primary_key=True, comment="密钥ID"),
        Column("ak", String(128), nullable=False, unique=True, comment="访问密钥(Access Key)"),
        Column("description", String(255), nullable=True, comment="密钥描述"),
        Column("enabled", Boolean, default=True, index=True, comment="是否启用"),
        Column("created_by", Integer, ForeignKey("admin_users.id"), nullable=True, index=True),  # noqa: E712
        Column("created_at", DateTime(timezone=True), server_default=func.now(), comment="创建时间"),
    )

    # === Git 仓库凭据表 ===
    Table(
        "git_credentials", meta,
        Column("id", Integer, primary_key=True, comment="凭据ID"),
        Column("name", String(100), nullable=False, unique=True, comment="凭据名称"),
        Column("auth_type", String(20), nullable=False, server_default="https",
               comment="认证方式: https / ssh"),
        Column("username_enc", Text, nullable=True, comment="加密的用户名"),
        Column("password_enc", Text, nullable=True, comment="加密的密码/Token"),
        Column("ssh_key_enc", Text, nullable=True, comment="加密的SSH私钥"),
        Column("description", String(255), nullable=True, comment="凭据描述"),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), comment="创建时间"),
        Column("updated_at", DateTime(timezone=True), onupdate=func.now(), comment="最后更新时间"),
    )

    # === Git 仓库配置表 ===
    Table(
        "git_repos", meta,
        Column("id", Integer, primary_key=True, comment="仓库ID"),
        Column("name", String(100), nullable=False, unique=True, comment="仓库唯一标识"),
        Column("url", String(512), nullable=False, comment="Git clone 地址"),
        Column("main_branch", String(100), nullable=False, server_default="main",
               comment="主分支（发布正式环境时推送的分支）"),
        Column("credential_id", Integer, ForeignKey("git_credentials.id", ondelete="SET NULL"),
               nullable=True, index=True, comment="关联凭据ID"),
        Column("enabled", Boolean, default=True, index=True, comment="是否启用"),
        Column("allow_write", Boolean, default=False, comment="是否允许写操作（默认只读）"),
        Column("allow_push", Boolean, default=False, comment="是否允许推送（默认禁止）"),
        Column("description", String(512), nullable=True, comment="仓库描述"),
        Column("last_fetched_at", DateTime(timezone=True), nullable=True, comment="最后fetch时间"),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), comment="创建时间"),
        Column("updated_at", DateTime(timezone=True), onupdate=func.now(), comment="最后更新时间"),
    )

    # === 权限表（Access Key → Git Repo） ===
    Table(
        "git_permissions", meta,
        Column("id", Integer, primary_key=True, comment="权限ID"),
        Column("key_id", Integer, ForeignKey("access_keys.id", ondelete="CASCADE"),
               nullable=False, index=True, comment="访问密钥ID"),
        Column("repo_id", Integer, ForeignKey("git_repos.id", ondelete="CASCADE"),
               nullable=False, index=True, comment="Git仓库ID"),
        Column("access_level", String(20), nullable=False, server_default="read_only",
               comment="访问级别: read_only / read_write / admin"),
        Column("branch_pattern", String(255), nullable=True, server_default=".*",
               comment="允许访问的分支正则表达式"),
        Column("path_pattern", String(512), nullable=True, server_default=".*",
               comment="允许访问的路径正则表达式"),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), comment="创建时间"),
    )

    # === IP白名单表 ===
    Table(
        "ip_whitelist", meta,
        Column("id", Integer, primary_key=True, comment="白名单ID"),
        Column("key_id", Integer, ForeignKey("access_keys.id", ondelete="CASCADE"),
               nullable=False, index=True, comment="访问密钥ID"),
        Column("cidr", String(64), nullable=False, comment="IP地址或CIDR网段"),
        Column("description", String(255), nullable=True, comment="白名单描述"),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), comment="创建时间"),
    )

    # === MCP 审计日志表 ===
    Table(
        "audit_logs", meta,
        Column("id", BigInteger, primary_key=True, comment="日志ID"),
        Column("timestamp", DateTime(timezone=True), server_default=func.now(), index=True, comment="操作时间"),
        Column("access_key", String(128), nullable=True, index=True, comment="访问密钥"),
        Column("client_ip", String(45), nullable=True, index=True, comment="客户端IP地址"),
        Column("repo_id", Integer, ForeignKey("git_repos.id", ondelete="SET NULL"),
               nullable=True, index=True, comment="Git仓库ID"),
        Column("repo_name", String(100), nullable=True, comment="仓库名称（冗余，方便查询）"),
        Column("operation", String(50), nullable=False, index=True,
               comment="操作类型: read_file/list_tree/log/diff/blame/grep/show"),
        Column("target", String(512), nullable=True, comment="操作目标（文件路径/分支/commit SHA等）"),
        Column("duration_ms", Integer, nullable=True, comment="执行耗时(毫秒)"),
        Column("status", String(20), nullable=False, index=True, comment="执行状态: success/denied/error"),
        Column("error_message", Text, nullable=True, comment="错误信息"),
        Column("metadata", JSON, nullable=True, comment="额外元数据"),
    )

    # === 系统操作日志表 ===
    Table(
        "system_logs", meta,
        Column("id", BigInteger, primary_key=True, comment="日志ID"),
        Column("timestamp", DateTime(timezone=True), server_default=func.now(), index=True, comment="操作时间"),
        Column("user_id", Integer, ForeignKey("admin_users.id"), nullable=True, index=True),  # noqa: E712
        Column("username", String(100), nullable=True, comment="操作用户名"),
        Column("operation", String(50), nullable=False, index=True,
               comment="操作类型: create_key/delete_key/update_repo等"),
        Column("resource_type", String(50), nullable=False, index=True,
               comment="资源类型: access_key/permission/repo/credential"),
        Column("resource_id", Integer, nullable=True, comment="资源ID"),
        Column("details", JSON, nullable=True, comment="操作详情(JSON格式)"),
        Column("client_ip", String(45), nullable=True, comment="客户端IP地址"),
    )

    # === 会话表 ===
    Table(
        "sessions", meta,
        Column("id", Integer, primary_key=True, comment="会话ID"),
        Column("user_id", Integer, ForeignKey("admin_users.id"), nullable=False, index=True),  # noqa: E712
        Column("token_jti", String(255), nullable=False, unique=True, index=True, comment="JWT Token唯一标识"),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), comment="创建时间"),
        Column("expires_at", DateTime(timezone=True), nullable=False, index=True, comment="过期时间"),
        Column("revoked", Boolean, default=False, index=True, comment="是否已撤销"),
    )

    # === 大模型配置表 ===
    Table(
        "llm_configs", meta,
        Column("id", Integer, primary_key=True, comment="配置ID"),
        Column("provider", String(50), nullable=False, unique=True, comment="提供商"),
        Column("base_url", String(255), nullable=True, comment="API Base URL"),
        Column("api_key_enc", Text, nullable=True, comment="加密存储的API Key"),
        Column("model_name", String(100), nullable=False, comment="模型名称"),
        Column("is_active", Boolean, default=False, comment="是否激活"),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), comment="创建时间"),
        Column("updated_at", DateTime(timezone=True), onupdate=func.now(), comment="最后更新时间"),
    )

    # === 大模型调用日志表 ===
    Table(
        "llm_call_logs", meta,
        Column("id", BigInteger, primary_key=True, comment="日志ID"),
        Column("timestamp", DateTime(timezone=True), server_default=func.now(), index=True, comment="调用时间"),
        Column("access_key", String(128), nullable=True, index=True, comment="访问密钥"),
        Column("tool_name", String(100), nullable=True, index=True, comment="工具名"),
        Column("repo_id", Integer, nullable=True, index=True, comment="关联仓库ID"),
        Column("model_name", String(100), nullable=False, comment="模型名称"),
        Column("prompt_tokens", Integer, nullable=False, server_default="0", comment="输入Token"),
        Column("completion_tokens", Integer, nullable=False, server_default="0", comment="输出Token"),
        Column("total_tokens", Integer, nullable=False, server_default="0", index=True, comment="总Token"),
        Column("duration_ms", Integer, nullable=True, comment="耗时(毫秒)"),
        Column("status", String(20), nullable=False, index=True, comment="success / error"),
        Column("error_message", Text, nullable=True, comment="失败原因"),
    )

    meta.create_all(engine)


def create_default_admin(engine: Engine, master_key: str = None,
                         username: str = "admin", password: str = "admin123"):
    """创建默认管理员账号"""
    from sqlalchemy import Table, MetaData, select, insert
    from sqlalchemy.orm import Session
    import bcrypt
    import hmac
    import hashlib

    if master_key is None:
        try:
            from config import Config
            cfg = Config.load()
            master_key = cfg.security.master_key
        except Exception:
            raise ValueError("无法获取 master_key，密码加盐失败")

    meta = MetaData()
    admin_users = Table("admin_users", meta, autoload_with=engine)

    with Session(engine) as session:
        existing = session.execute(
            select(admin_users).where(admin_users.c.username == username)
        ).first()

        if not existing:
            peppered = hmac.new(
                master_key.encode('utf-8'),
                password.encode('utf-8'),
                hashlib.sha256
            ).digest()
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(peppered, salt)

            session.execute(
                insert(admin_users).values(
                    username=username,
                    password_hash=hashed.decode('utf-8'),
                    email=f"{username}@localhost",
                    role="admin",
                    is_active=True
                )
            )
            session.commit()
            print(f"[+] 创建默认管理员: {username}")
        else:
            print(f"[!] 管理员已存在: {username}")


def initialize_default_llm_configs(engine: Engine):
    """初始化默认的大模型配置"""
    from sqlalchemy import Table, MetaData, select, insert, update
    from sqlalchemy.orm import Session

    meta = MetaData()
    llm_configs = Table("llm_configs", meta, autoload_with=engine)

    defaults = [
        {"provider": "deepseek", "base_url": "https://api.deepseek.com",
         "model_name": "deepseek-v4-pro", "is_active": False},
        {"provider": "qwen", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
         "model_name": "qwen3.5-max", "is_active": False},
        {"provider": "kimi", "base_url": "https://api.moonshot.cn/v1",
         "model_name": "kimi-k3", "is_active": False},
        {"provider": "zhipu", "base_url": "https://open.bigmodel.cn/api/paas/v4",
         "model_name": "glm-5.2", "is_active": False},
        {"provider": "doubao", "base_url": "https://ark.cn-beijing.volces.com/api/v3",
         "model_name": "doubao-seed-1-6", "is_active": False},
        {"provider": "wenxin", "base_url": "https://qianfan.baidubce.com/v2",
         "model_name": "ernie-4.0-8k", "is_active": False},
        {"provider": "hunyuan", "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
         "model_name": "hunyuan-pro", "is_active": False},
        {"provider": "minimax", "base_url": "https://api.minimax.chat/v1",
         "model_name": "MiniMax-M3", "is_active": False},
    ]

    # 已废弃/过旧的历史模型名，自动迁移到新默认模型
    DEPRECATED_MODELS = {
        "deepseek-coder", "deepseek-chat", "deepseek-reasoner",
        "gpt-4o", "claude-3-5-sonnet-20241022",
        "glm-4.7", "glm-4.6", "glm-4.5",
        "qwen-max", "qwen-plus", "qwen-turbo",
        "MiniMax-Text-01",
    }

    with Session(engine) as session:
        for d in defaults:
            existing = session.execute(
                select(llm_configs).where(llm_configs.c.provider == d["provider"])
            ).mappings().first()
            if not existing:
                session.execute(insert(llm_configs).values(**d))
                print(f"[+] 创建默认 LLM 配置: {d['provider']}")
            elif existing["model_name"] in DEPRECATED_MODELS:
                session.execute(
                    update(llm_configs)
                    .where(llm_configs.c.id == existing["id"])
                    .values(model_name=d["model_name"])
                )
                print(f"[~] 迁移历史模型: {d['provider']} {existing['model_name']} -> {d['model_name']}")
        session.commit()

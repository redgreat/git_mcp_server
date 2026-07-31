"""
Schema 缓存 - 预加载管理数据库表引用
"""
from sqlalchemy import Table, MetaData
from sqlalchemy.engine import Engine
from dataclasses import dataclass


@dataclass
class AdminTables:
    admin_users: Table
    access_keys: Table
    git_repos: Table
    git_credentials: Table
    git_permissions: Table
    ip_whitelist: Table
    audit_logs: Table
    system_logs: Table
    sessions: Table
    llm_configs: Table
    llm_call_logs: Table


def get_admin_tables(engine: Engine) -> AdminTables:
    """预加载所有管理表"""
    meta = MetaData()
    return AdminTables(
        admin_users=Table("admin_users", meta, autoload_with=engine),
        access_keys=Table("access_keys", meta, autoload_with=engine),
        git_repos=Table("git_repos", meta, autoload_with=engine),
        git_credentials=Table("git_credentials", meta, autoload_with=engine),
        git_permissions=Table("git_permissions", meta, autoload_with=engine),
        ip_whitelist=Table("ip_whitelist", meta, autoload_with=engine),
        audit_logs=Table("audit_logs", meta, autoload_with=engine),
        system_logs=Table("system_logs", meta, autoload_with=engine),
        sessions=Table("sessions", meta, autoload_with=engine),
        llm_configs=Table("llm_configs", meta, autoload_with=engine),
        llm_call_logs=Table("llm_call_logs", meta, autoload_with=engine),
    )

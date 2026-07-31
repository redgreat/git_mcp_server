"""
git_mcp_server 配置管理
"""
import os
import yaml
from dataclasses import dataclass
from typing import Optional


@dataclass
class ServerConfig:
    """服务配置"""
    host: str
    port: int
    public_base_url: Optional[str] = None


@dataclass
class SecurityConfig:
    """安全配置"""
    master_key: str
    jwt_secret: str
    session_timeout: int


@dataclass
class AdminDatabaseConfig:
    """管理数据库配置（PostgreSQL）"""
    host: str
    port: int
    database: str
    username: str
    password: str
    sslmode: str = "disable"
    timezone: str = "Asia/Shanghai"
    pool_size: int = 10
    max_overflow: int = 20


@dataclass
class GitStorageConfig:
    """Git 本地存储配置"""
    base_dir: str = "/data/git_repos"
    cache_ttl: int = 86400
    fetch_interval: int = 300
    max_fetch_workers: int = 5


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str
    dir: str
    audit_to_database: bool
    audit_to_file: bool


@dataclass
class ObjectStorageConfig:
    provider: str = "ali-oss"
    endpoint: Optional[str] = None
    bucket: Optional[str] = None
    access_key_id: Optional[str] = None
    access_key_secret: Optional[str] = None
    region: Optional[str] = None
    path_prefix: Optional[str] = None
    public_base_url: Optional[str] = None
    enabled: bool = False
    request_timeout_seconds: int = 30


@dataclass
class Config:
    """应用配置"""
    server: ServerConfig
    security: SecurityConfig
    admin_database: AdminDatabaseConfig
    git_storage: GitStorageConfig
    logging: LoggingConfig
    object_storage: Optional[ObjectStorageConfig] = None

    @staticmethod
    def load(config_path: Optional[str] = None) -> "Config":
        if config_path is None:
            config_path = os.getenv("CONFIG_PATH", "config/config.yml")

        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"配置文件不存在: {config_path}\n"
                f"请复制 config/config.yml.example 到 config/config.yml 并修改配置"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        cfg = Config(
            server=ServerConfig(**data['server']),
            security=SecurityConfig(**data['security']),
            admin_database=AdminDatabaseConfig(**data['admin_database']),
            git_storage=GitStorageConfig(**data.get('git_storage', {})),
            logging=LoggingConfig(**data['logging'])
        )
        # 支持环境变量覆盖数据库连接（用于 Docker 环境）
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        if db_host:
            cfg.admin_database.host = db_host
        if db_port:
            cfg.admin_database.port = int(db_port)
        if 'object_storage' in data and data['object_storage']:
            cfg.object_storage = ObjectStorageConfig(**data['object_storage'])
        return cfg

    def get_admin_db_url(self) -> str:
        db = self.admin_database
        url = f"postgresql+psycopg2://{db.username}:{db.password}@{db.host}:{db.port}/{db.database}"
        if db.sslmode:
            url += f"?sslmode={db.sslmode}"
        return url

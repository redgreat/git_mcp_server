"""
MCP 权限检查模块
"""
from sqlalchemy import Table, MetaData, select, and_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from fastapi import HTTPException


class MCPPermissionChecker:
    """MCP 权限检查器"""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.meta = MetaData()
        self.access_keys = Table("access_keys", self.meta, autoload_with=engine)
        self.permissions = Table("git_permissions", self.meta, autoload_with=engine)

    def check_permission(
        self,
        access_key: str,
        repo_id: int,
        require_write: bool = False,
    ) -> dict:
        """检查 MCP 调用权限

        Args:
            access_key: 访问密钥
            repo_id: 仓库 ID
            require_write: 是否需要写权限

        Returns:
            权限信息字典

        Raises:
            HTTPException: 权限不足
        """
        with Session(self.engine) as session:
            # 查找 access_key
            key_row = session.execute(
                select(self.access_keys).where(
                    self.access_keys.c.ak == access_key,
                    self.access_keys.c.enabled == True  # noqa: E712
                )
            ).mappings().first()

            if not key_row:
                raise HTTPException(status_code=401, detail="无效或已禁用的访问密钥")

            key_id = key_row['id']

            # 查找权限
            perm = session.execute(
                select(self.permissions).where(
                    and_(
                        self.permissions.c.key_id == key_id,
                        self.permissions.c.repo_id == repo_id
                    )
                )
            ).mappings().first()

            if not perm:
                raise HTTPException(
                    status_code=403,
                    detail=f"访问密钥无权访问仓库 ID {repo_id}"
                )

            # 检查写权限
            if require_write and perm['access_level'] not in ('read_write', 'admin'):
                raise HTTPException(
                    status_code=403,
                    detail="该访问密钥无写权限"
                )

            return dict(perm)

"""
IP 白名单检查
"""
import ipaddress
from sqlalchemy.engine import Engine
from sqlalchemy import Table, MetaData, select
from sqlalchemy.orm import Session


class IPWhitelistChecker:
    """IP白名单检查器"""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.meta = MetaData()
        self.whitelist = Table("ip_whitelist", self.meta, autoload_with=engine)

    def is_allowed(self, key_id: int, client_ip: str) -> bool:
        """检查 client_ip 是否在白名单中

        如果白名单为空，则允许所有IP。
        """
        with Session(self.engine) as session:
            rows = session.execute(
                select(self.whitelist).where(
                    self.whitelist.c.key_id == key_id
                )
            ).mappings().all()

        if not rows:
            return True  # 无白名单 = 全部放行

        client = ipaddress.ip_address(client_ip)
        for row in rows:
            network = ipaddress.ip_network(row['cidr'], strict=False)
            if client in network:
                return True

        return False

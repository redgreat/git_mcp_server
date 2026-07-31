"""
确保只有一个 LLM 配置处于激活状态
"""
from sqlalchemy.engine import Engine
from sqlalchemy import Table, MetaData, select
from sqlalchemy.orm import Session


def ensure_single_llm_active(engine: Engine):
    """确保只有一个 llm_config 激活
    如果没有任何激活的，也保持现状交给管理员手动激活
    """
    meta = MetaData()
    llm_configs = Table("llm_configs", meta, autoload_with=engine)

    with Session(engine) as session:
        rows = session.execute(
            select(llm_configs).where(
                llm_configs.c.is_active == True  # noqa: E712
            )
        ).mappings().all()

        # 如果有多个激活，保留第一个
        if len(rows) > 1:
            from sqlalchemy import update
            for row in rows[1:]:
                session.execute(
                    update(llm_configs)
                    .where(llm_configs.c.id == row["id"])
                    .values(is_active=False)
                )
            session.commit()

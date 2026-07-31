"""
测试脚本 - 数据库 Schema 初始化
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import create_engine, inspect, text


def test_db_schema():
    from config import Config
    cfg = Config.load()

    engine = create_engine(cfg.get_admin_db_url(), pool_pre_ping=True)

    # 1. 测试连接
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅ 数据库连接成功")

    # 2. 初始化 Schema
    from admin.models import ensure_schema
    ensure_schema(engine)
    print("✅ Schema 初始化完成")

    # 3. 验证表结构
    insp = inspect(engine)
    tables = sorted(insp.get_table_names())
    expected = [
        "access_keys", "admin_users", "audit_logs",
        "git_credentials", "git_permissions", "git_repos",
        "ip_whitelist", "llm_call_logs", "llm_configs",
        "sessions", "system_logs",
    ]

    print(f"\n📋 数据库表 ({len(tables)} 张):")
    for t in tables:
        cols = insp.get_columns(t)
        print(f"   {t}: {len(cols)} 列")

    missing = [e for e in expected if e not in tables]
    if missing:
        print(f"\n❌ 缺少表: {missing}")
        return False

    # 4. 创建默认管理员
    from admin.models import create_default_admin, initialize_default_llm_configs
    create_default_admin(engine, master_key=cfg.security.master_key)
    initialize_default_llm_configs(engine)
    print("✅ 默认管理员和 LLM 配置已创建")

    engine.dispose()
    print("\n🎉 数据库测试全部通过！")
    return True


if __name__ == "__main__":
    try:
        test_db_schema()
    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

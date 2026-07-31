"""
测试脚本 - 配置加载
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_config():
    from config import Config
    cfg = Config.load()
    print(f"✅ 配置加载成功")
    print(f"   Server: {cfg.server.host}:{cfg.server.port}")
    print(f"   Admin DB: {cfg.admin_database.host}:{cfg.admin_database.port}/{cfg.admin_database.database}")
    print(f"   Git Storage: {cfg.git_storage.base_dir}")
    print(f"   Security: session_timeout={cfg.security.session_timeout}s")
    print(f"   Admin DB URL: {cfg.get_admin_db_url()[:60]}...")
    return True


if __name__ == "__main__":
    try:
        test_config()
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        sys.exit(1)
